"""Integração e-SUS APS (PEC): visitas de ACS/ACE e cadastro de domicílios.

Uma única função de sincronização por processo de negócio (``sincronizar``), executada
de forma síncrona (botão) ou assíncrona (thread em segundo plano / agendamento).
Os dois modos de conexão usam a MESMA consulta SQL sobre as tabelas do PEC
(``tb_fat_visita_domiciliar``, ``tb_fat_cad_domiciliar`` e dimensões ``tb_dim_*``):

* ``pec``: PostgreSQL do PEC do município, em transação somente leitura;
* ``simulado``: conjunto de exemplo no layout do PEC, no schema ``esus_sim`` do banco
  local (PostgreSQL) ou nas próprias tabelas do banco (SQLite, usado nos testes).
"""

import hashlib
import math
import random
import secrets
import threading
import uuid
from datetime import date, datetime, time, timedelta

import sqlalchemy as sa
from flask import current_app
from sqlalchemy.pool import NullPool

from app.extensions import db
from app.shared.mail import decifrar

PROCESSOS = ("domicilios", "visitas")
CBO = {"515105": "ACS", "515140": "ACE"}
JANELA_DIAS = 90
SIM_SCHEMA = "esus_sim"
EXECUCAO_TRAVADA = timedelta(minutes=30)
DESFECHOS = {"visita realizada": "realizada", "visita recusada": "recusada", "ausente": "ausente"}
MOTIVOS = (  # coluna do PEC -> rótulo da Ficha de Visita Domiciliar e Territorial
    ("st_mot_vis_cad_att", "Cadastramento/atualização"),
    ("st_mot_vis_visita_periodica", "Visita periódica"),
    ("st_mot_vis_busca_ativa", "Busca ativa"),
    ("st_mot_vis_acompanhamento", "Acompanhamento"),
    ("st_mot_vis_egresso_internacao", "Egresso de internação"),
    ("st_mot_vis_ctrl_ambnte_vetor", "Controle de ambientes/vetores (Aedes)"),
    ("st_mot_vis_convte_atvidd_cltva", "Convite para atividades coletivas"),
    ("st_mot_vis_orintacao_prevncao", "Orientação/prevenção"),
    ("st_mot_vis_outros", "Outros"),
    ("st_ctrl_amb_vet_acao_educativa", "Vetor: ação educativa"),
    ("st_ctrl_amb_vet_imovel_foco", "Vetor: imóvel com foco"),
    ("st_ctrl_amb_vet_acao_mecanica", "Vetor: ação mecânica"),
    ("st_ctrl_amb_vet_tratamnt_focal", "Vetor: tratamento focal"),
)
MOTIVOS_AEDES = {col for col, _ in MOTIVOS if "vet" in col}


class EsusConfig(db.Model):
    __tablename__ = "integracao_esus_config"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id", ondelete="CASCADE"), nullable=False, unique=True)
    modo = db.Column(db.String(10), nullable=False, default="simulado")  # pec | simulado
    ibge = db.Column(db.String(7))
    host = db.Column(db.String(200))
    porta = db.Column(db.Integer, nullable=False, default=5432)
    base = db.Column(db.String(120))
    usuario = db.Column(db.String(120))
    senha_cifrada = db.Column(db.Text)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    intervalo_min = db.Column(db.Integer, nullable=False, default=0)  # 0 = sem agendamento
    token_hash = db.Column(db.String(64), unique=True)
    token_prefixo = db.Column(db.String(16))
    token_criado_em = db.Column(db.DateTime)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    atualizado_por_id = db.Column(db.Integer)


class EsusExecucao(db.Model):
    __tablename__ = "integracao_esus_execucoes"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id", ondelete="CASCADE"), nullable=False, index=True)
    processo = db.Column(db.String(20), nullable=False)  # visitas | domicilios
    forma = db.Column(db.String(12), nullable=False)  # sincrona | assincrona | agendada
    modo = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="executando")  # executando | concluida | falhou
    iniciado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    finalizado_em = db.Column(db.DateTime)
    lidos = db.Column(db.Integer, nullable=False, default=0)
    inseridos = db.Column(db.Integer, nullable=False, default=0)
    atualizados = db.Column(db.Integer, nullable=False, default=0)
    removidos = db.Column(db.Integer, nullable=False, default=0)
    erros = db.Column(db.Integer, nullable=False, default=0)
    mensagem = db.Column(db.Text)
    usuario_id = db.Column(db.Integer)


class EsusVisita(db.Model):
    __tablename__ = "integracao_esus_visitas"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id", ondelete="CASCADE"), nullable=False)
    origem = db.Column(db.String(10), nullable=False)
    chave = db.Column(db.String(40), nullable=False)  # co_seq_fat_visita_domiciliar
    ficha_uuid = db.Column(db.String(92))
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5))
    turno = db.Column(db.String(20))
    profissional_cns = db.Column(db.String(15))
    profissional_nome = db.Column(db.String(255), nullable=False)
    cbo = db.Column(db.String(6))
    categoria = db.Column(db.String(3))  # ACS | ACE
    equipe_ine = db.Column(db.String(20))
    equipe_nome = db.Column(db.String(255))
    unidade_cnes = db.Column(db.String(20))
    unidade_nome = db.Column(db.String(255))
    microarea = db.Column(db.String(3))
    domicilio_uuid = db.Column(db.String(92))
    tipo_imovel = db.Column(db.String(120))
    desfecho = db.Column(db.String(15), nullable=False)  # realizada | recusada | ausente | nao_informado
    motivos = db.Column(db.String(500))
    motivo_aedes = db.Column(db.Boolean, nullable=False, default=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sincronizado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    __table_args__ = (db.UniqueConstraint("prefeitura_id", "chave", name="uq_esus_visita_chave"),
                      db.Index("ix_esus_visita_periodo", "prefeitura_id", "data"))


class EsusDomicilio(db.Model):
    __tablename__ = "integracao_esus_domicilios"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id", ondelete="CASCADE"), nullable=False)
    origem = db.Column(db.String(10), nullable=False)
    chave = db.Column(db.String(92), nullable=False)  # nu_uuid_ficha_origem
    microarea = db.Column(db.String(3))
    logradouro = db.Column(db.String(288))
    numero = db.Column(db.String(64))
    bairro = db.Column(db.String(200))
    cep = db.Column(db.String(10))
    tipo_imovel = db.Column(db.String(120))
    moradores = db.Column(db.Integer)
    recusa = db.Column(db.Boolean, nullable=False, default=False)
    profissional_nome = db.Column(db.String(255))
    equipe_ine = db.Column(db.String(20))
    data_cadastro = db.Column(db.Date)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sincronizado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    __table_args__ = (db.UniqueConstraint("prefeitura_id", "chave", name="uq_esus_domicilio_chave"),)


ESUS_TABLES = [EsusConfig.__table__, EsusExecucao.__table__, EsusVisita.__table__, EsusDomicilio.__table__]

# ---------------------------------------------------------------- consultas no layout do PEC
# Mesmos nomes e junções usados no painel de agentes do saude-nest (tb_fat_visita_domiciliar
# + tb_dim_*); SQL portátil (PostgreSQL/SQLite) para servir aos dois modos e aos testes.
SQL_VISITAS = f"""
SELECT vd.co_seq_fat_visita_domiciliar AS chave, vd.nu_uuid_ficha AS ficha_uuid,
       dt.dt_registro AS data, fvd.dt_ficha AS dt_ficha, turno.ds_turno AS turno,
       prof.nu_cns AS profissional_cns, prof.no_profissional AS profissional_nome, cbo.nu_cbo AS cbo,
       equipe.nu_ine AS equipe_ine, equipe.no_equipe AS equipe_nome,
       unds.nu_cnes AS unidade_cnes, unds.no_unidade_saude AS unidade_nome,
       vd.nu_micro_area AS microarea, vd.co_uuid_origem_fcd AS domicilio_uuid,
       imovel.ds_tipo_imovel AS tipo_imovel, df.ds_desfecho_visita AS desfecho,
       {", ".join("vd." + col for col, _ in MOTIVOS)},
       vd.nu_latitude AS latitude, vd.nu_longitude AS longitude
FROM tb_fat_visita_domiciliar vd
JOIN tb_dim_tempo dt ON vd.co_dim_tempo = dt.co_seq_dim_tempo
JOIN tb_dim_profissional prof ON vd.co_dim_profissional = prof.co_seq_dim_profissional
JOIN tb_dim_cbo cbo ON vd.co_dim_cbo = cbo.co_seq_dim_cbo
JOIN tb_dim_municipio mun ON vd.co_dim_municipio = mun.co_seq_dim_municipio
LEFT JOIN tb_dim_equipe equipe ON vd.co_dim_equipe = equipe.co_seq_dim_equipe
LEFT JOIN tb_dim_unidade_saude unds ON vd.co_dim_unidade_saude = unds.co_seq_dim_unidade_saude
LEFT JOIN tb_dim_turno turno ON vd.co_dim_turno = turno.co_seq_dim_turno
LEFT JOIN tb_dim_tipo_imovel imovel ON vd.co_dim_tipo_imovel = imovel.co_seq_dim_tipo_imovel
LEFT JOIN tb_dim_desfecho_visita df ON vd.co_dim_desfecho_visita = df.co_seq_dim_desfecho_visita
LEFT JOIN tb_cds_ficha_visita_domiciliar fvd ON fvd.co_unico_ficha = vd.nu_uuid_ficha
WHERE dt.dt_registro >= :de AND dt.dt_registro <= :ate
  AND cbo.nu_cbo IN ('515105', '515140')
  AND SUBSTR(mun.co_ibge, 1, 6) = :ibge6
  AND prof.no_profissional IS NOT NULL
  AND prof.no_profissional <> 'PROFISSIONAL NÃO CADASTRADO'
ORDER BY vd.co_seq_fat_visita_domiciliar
"""

SQL_DOMICILIOS = """
SELECT COALESCE(cd.nu_uuid_ficha_origem, cd.nu_uuid_ficha) AS chave, cd.nu_micro_area AS microarea,
       cd.no_logradouro AS logradouro, cd.nu_num_logradouro AS numero, cd.no_bairro AS bairro, cd.nu_cep AS cep,
       imovel.ds_tipo_imovel AS tipo_imovel, cd.qt_morador AS moradores, cd.st_recusa_cadastro AS recusa,
       prof.no_profissional AS profissional_nome, equipe.nu_ine AS equipe_ine, dt.dt_registro AS data_cadastro,
       cd.nu_latitude AS latitude, cd.nu_longitude AS longitude
FROM tb_fat_cad_domiciliar cd
JOIN tb_dim_municipio mun ON cd.co_dim_municipio = mun.co_seq_dim_municipio
LEFT JOIN tb_dim_tempo dt ON cd.co_dim_tempo = dt.co_seq_dim_tempo
LEFT JOIN tb_dim_profissional prof ON cd.co_dim_profissional = prof.co_seq_dim_profissional
LEFT JOIN tb_dim_equipe equipe ON cd.co_dim_equipe = equipe.co_seq_dim_equipe
LEFT JOIN tb_dim_tipo_imovel imovel ON cd.co_dim_tipo_imovel = imovel.co_seq_dim_tipo_imovel
WHERE SUBSTR(mun.co_ibge, 1, 6) = :ibge6
  AND cd.co_seq_fat_cad_domiciliar IN (
      SELECT MAX(co_seq_fat_cad_domiciliar) FROM tb_fat_cad_domiciliar
      GROUP BY COALESCE(nu_uuid_ficha_origem, nu_uuid_ficha))
"""

# ---------------------------------------------------------------- conexão
_sim_engines = {}
_sim_lock = threading.Lock()


def sim_engine():
    """Banco do 'PEC simulado': schema esus_sim no PostgreSQL local; no SQLite, o próprio banco."""
    if db.engine.dialect.name != "postgresql":
        return db.engine
    key = repr(db.engine.url)
    with _sim_lock:
        if key not in _sim_engines:
            with db.engine.begin() as conn:
                conn.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SIM_SCHEMA}"))
            _sim_engines[key] = sa.create_engine(db.engine.url, pool_pre_ping=True, pool_size=2, max_overflow=2,
                                                 connect_args={"options": f"-csearch_path={SIM_SCHEMA}"})
        return _sim_engines[key]


def pec_engine(cfg):
    senha = decifrar(cfg.senha_cifrada)
    if senha is None:
        raise ValueError("A senha do PEC não pode ser lida (chave do sistema alterada). Informe a senha novamente.")
    if not (cfg.host and cfg.base and cfg.usuario):
        raise ValueError("Informe host, base e usuário do banco do PEC.")
    url = sa.engine.URL.create("postgresql+psycopg2", username=cfg.usuario, password=senha or None,
                               host=cfg.host, port=cfg.porta or 5432, database=cfg.base)
    return sa.create_engine(url, poolclass=NullPool, connect_args={
        "connect_timeout": 10, "application_name": "ija-integracao-esus",
        "options": "-c default_transaction_read_only=on -c statement_timeout=120000"})


def ler(cfg, processo, de=None, ate=None):
    """Executa a consulta do processo no banco do modo configurado e devolve dicionários."""
    ibge6 = (cfg.ibge or "")[:6]
    if len(ibge6) != 6 or not ibge6.isdigit():
        raise ValueError("Informe o código IBGE do município na configuração da integração.")
    engine = sim_engine() if cfg.modo == "simulado" else pec_engine(cfg)
    try:
        with engine.connect() as conn:
            if processo == "visitas":
                result = conn.execute(sa.text(SQL_VISITAS), {"de": de.isoformat(), "ate": ate.isoformat(), "ibge6": ibge6})
            else:
                result = conn.execute(sa.text(SQL_DOMICILIOS), {"ibge6": ibge6})
            return [dict(row._mapping) for row in result]
    finally:
        if cfg.modo == "pec":
            engine.dispose()


def testar_conexao(cfg):
    engine = sim_engine() if cfg.modo == "simulado" else pec_engine(cfg)
    try:
        with engine.connect() as conn:
            total = conn.execute(sa.text("SELECT COUNT(*) FROM tb_fat_visita_domiciliar")).scalar()
        return int(total or 0)
    finally:
        if cfg.modo == "pec":
            engine.dispose()


# ---------------------------------------------------------------- normalização
def _date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _hour(value):
    if isinstance(value, datetime):
        return value.strftime("%H:%M") if value.time() != time(0) else None
    text = str(value or "")
    return text[11:16] if len(text) >= 16 and text[11:16] != "00:00" else None


def _coord(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high and number != 0 else None


def _flag(value):
    try:
        return int(value or 0) == 1
    except (TypeError, ValueError):
        return False


def normalizar_visita(row):
    data = _date(row.get("data"))
    chave = row.get("chave")
    if data is None or chave is None or not row.get("profissional_nome"):
        raise ValueError("visita sem chave, data ou profissional")
    marcados = [col for col, _ in MOTIVOS if _flag(row.get(col))]
    cbo = str(row.get("cbo") or "").strip()
    return {
        "chave": str(chave), "ficha_uuid": row.get("ficha_uuid"), "data": data, "hora": _hour(row.get("dt_ficha")),
        "turno": row.get("turno"), "profissional_cns": (str(row.get("profissional_cns") or "").strip() or None),
        "profissional_nome": str(row["profissional_nome"]).strip()[:255], "cbo": cbo or None, "categoria": CBO.get(cbo),
        "equipe_ine": row.get("equipe_ine"), "equipe_nome": row.get("equipe_nome"),
        "unidade_cnes": row.get("unidade_cnes"), "unidade_nome": row.get("unidade_nome"),
        "microarea": row.get("microarea"), "domicilio_uuid": row.get("domicilio_uuid"), "tipo_imovel": row.get("tipo_imovel"),
        "desfecho": DESFECHOS.get(str(row.get("desfecho") or "").strip().lower(), "nao_informado"),
        "motivos": "; ".join(label for col, label in MOTIVOS if col in marcados)[:500] or None,
        "motivo_aedes": any(col in MOTIVOS_AEDES for col in marcados),
        "latitude": _coord(row.get("latitude"), -34, 6), "longitude": _coord(row.get("longitude"), -74, -28),
    }


def normalizar_domicilio(row):
    if not row.get("chave"):
        raise ValueError("domicílio sem identificador")
    return {
        "chave": str(row["chave"])[:92], "microarea": row.get("microarea"), "logradouro": row.get("logradouro"),
        "numero": row.get("numero"), "bairro": row.get("bairro"), "cep": (row.get("cep") or None),
        "tipo_imovel": row.get("tipo_imovel"), "moradores": row.get("moradores"), "recusa": _flag(row.get("recusa")),
        "profissional_nome": row.get("profissional_nome"), "equipe_ine": row.get("equipe_ine"),
        "data_cadastro": _date(row.get("data_cadastro")),
        "latitude": _coord(row.get("latitude"), -34, 6), "longitude": _coord(row.get("longitude"), -74, -28),
    }


# ---------------------------------------------------------------- sincronização (uma por processo)
def em_execucao(prefeitura_id):
    limite = datetime.now() - EXECUCAO_TRAVADA
    return db.session.query(EsusExecucao.id).filter(
        EsusExecucao.prefeitura_id == prefeitura_id, EsusExecucao.status == "executando",
        EsusExecucao.iniciado_em >= limite).first() is not None


def sincronizar(prefeitura_id, processo, forma="sincrona", usuario_id=None, hoje=None):
    """Processo de negócio único: lê do PEC (ou simulado) e grava nas tabelas próprias."""
    if processo not in PROCESSOS:
        raise ValueError("Processo desconhecido.")
    cfg = EsusConfig.query.filter_by(prefeitura_id=prefeitura_id).first()
    if cfg is None:
        raise ValueError("Integração e-SUS não configurada para esta prefeitura.")
    execucao = EsusExecucao(prefeitura_id=prefeitura_id, processo=processo, forma=forma, modo=cfg.modo,
                            status="executando", iniciado_em=datetime.now(), usuario_id=usuario_id)
    db.session.add(execucao)
    db.session.commit()
    execucao_id = execucao.id
    try:
        ate = hoje or date.today()
        de = ate - timedelta(days=JANELA_DIAS)
        rows = ler(cfg, processo, de, ate)
        stats = _gravar(cfg, processo, rows, de)
        execucao = db.session.get(EsusExecucao, execucao_id)
        for key, value in stats.items():
            setattr(execucao, key, value)
        execucao.status = "concluida"
        execucao.mensagem = (f"{stats['erros']} registro(s) ignorado(s) por dados incompletos." if stats["erros"] else None)
    except Exception as exc:  # registra a falha na execução; nada parcial é gravado
        db.session.rollback()
        current_app.logger.warning("e-SUS: falha ao sincronizar %s da prefeitura %s: %s", processo, prefeitura_id, exc)
        execucao = db.session.get(EsusExecucao, execucao_id)
        execucao.status = "falhou"
        execucao.erros = (execucao.erros or 0) + 1
        execucao.mensagem = _mensagem(exc)
    execucao.finalizado_em = datetime.now()
    db.session.commit()
    return execucao


def _mensagem(exc):
    if isinstance(exc, ValueError):
        return str(exc)[:1000]
    if isinstance(exc, sa.exc.OperationalError):
        return ("Não foi possível conectar ou consultar o banco do PEC: "
                + str(getattr(exc, "orig", exc)).strip().splitlines()[0][:400])
    if isinstance(exc, sa.exc.ProgrammingError):
        return "Estrutura do banco diferente do esperado (tabela ou coluna do PEC ausente). Gere o conjunto simulado ou confira a versão do PEC."
    return f"Falha inesperada: {type(exc).__name__}."


def _gravar(cfg, processo, rows, de):
    model, normalizar = (EsusVisita, normalizar_visita) if processo == "visitas" else (EsusDomicilio, normalizar_domicilio)
    pid, agora = cfg.prefeitura_id, datetime.now()
    removidos = model.query.filter(model.prefeitura_id == pid, model.origem != cfg.modo).delete(synchronize_session=False)
    escopo = model.query.filter(model.prefeitura_id == pid)
    if processo == "visitas":
        escopo = escopo.filter(model.data >= de)
    existentes = dict(escopo.with_entities(model.chave, model.id))
    novos, atualizados, vistos, erros = [], [], set(), 0
    for row in rows:
        try:
            item = normalizar(row)
        except (ValueError, TypeError, KeyError):
            erros += 1
            continue
        if item["chave"] in vistos:
            continue
        vistos.add(item["chave"])
        item.update(prefeitura_id=pid, origem=cfg.modo, sincronizado_em=agora)
        if item["chave"] in existentes:
            item["id"] = existentes[item["chave"]]
            atualizados.append(item)
        else:
            novos.append(item)
    obsoletos = [i for chave, i in existentes.items() if chave not in vistos]
    for start in range(0, len(obsoletos), 500):
        model.query.filter(model.id.in_(obsoletos[start:start + 500])).delete(synchronize_session=False)
    db.session.bulk_insert_mappings(model, novos)
    db.session.bulk_update_mappings(model, atualizados)
    db.session.commit()
    return {"lidos": len(rows), "inseridos": len(novos), "atualizados": len(atualizados),
            "removidos": removidos + len(obsoletos), "erros": erros}


def sincronizar_tudo(prefeitura_id, forma, usuario_id=None):
    return [sincronizar(prefeitura_id, processo, forma, usuario_id) for processo in PROCESSOS]


def iniciar_em_segundo_plano(prefeitura_id, usuario_id=None, forma="assincrona"):
    """Dispara a sincronização numa thread; as execuções ficam registradas no banco."""
    if em_execucao(prefeitura_id):
        return None
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                sincronizar_tudo(prefeitura_id, forma, usuario_id)
            except Exception:
                app.logger.exception("e-SUS: sincronização em segundo plano falhou (prefeitura %s).", prefeitura_id)
            finally:
                db.session.remove()

    thread = threading.Thread(target=run, name=f"esus-sync-{prefeitura_id}", daemon=True)
    thread.start()
    return thread


def executar_agendadas():
    """Chamado pelo worker: sincroniza as prefeituras com intervalo vencido."""
    agora = datetime.now()
    for cfg in EsusConfig.query.filter(EsusConfig.ativo.is_(True), EsusConfig.intervalo_min > 0).all():
        ultima = db.session.query(sa.func.max(EsusExecucao.iniciado_em)).filter(EsusExecucao.prefeitura_id == cfg.prefeitura_id).scalar()
        if (ultima is None or agora - ultima >= timedelta(minutes=cfg.intervalo_min)) and not em_execucao(cfg.prefeitura_id):
            sincronizar_tudo(cfg.prefeitura_id, "agendada")


def register_worker(app):
    # ponytail: um laço por processo gunicorn; a trava é a execução "executando" no banco.
    lock = threading.Lock()

    def loop(stop):
        while not stop.wait(60):
            with app.app_context():
                try:
                    executar_agendadas()
                except Exception:
                    app.logger.warning("e-SUS: agendamento indisponível (confira a migração e a conexão).")
                finally:
                    db.session.remove()

    @app.before_request
    def start_esus_worker():
        if app.testing or "esus_stop" in app.extensions:
            return
        with lock:
            if "esus_stop" not in app.extensions:
                app.extensions["esus_stop"] = threading.Event()
                threading.Thread(target=loop, args=(app.extensions["esus_stop"],), name="esus-agenda", daemon=True).start()


# ---------------------------------------------------------------- token da API
def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def gerar_token(cfg):
    token = "esus_" + secrets.token_urlsafe(32)
    cfg.token_hash, cfg.token_prefixo, cfg.token_criado_em = _hash(token), token[:12], datetime.now()
    return token


def config_por_token(authorization):
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token.startswith("esus_") or len(token) > 100:
        return None
    return EsusConfig.query.filter_by(token_hash=_hash(token), ativo=True).first()


# ---------------------------------------------------------------- PEC simulado (layout do PEC)
SIM = sa.MetaData()


def _table(name, *columns):
    return sa.Table(name, SIM, *columns)


def _id(name):
    return sa.Column(name, sa.BigInteger, primary_key=True, autoincrement=False)


_S = sa.String
SIM_DIMS = {
    "tb_dim_municipio": _table("tb_dim_municipio", _id("co_seq_dim_municipio"), sa.Column("no_municipio", _S(500)), sa.Column("co_ibge", _S(10)), sa.Column("st_registro_valido", sa.Integer)),
    "tb_dim_profissional": _table("tb_dim_profissional", _id("co_seq_dim_profissional"), sa.Column("nu_cns", _S(15)), sa.Column("no_profissional", _S(255)), sa.Column("st_registro_valido", sa.Integer)),
    "tb_dim_cbo": _table("tb_dim_cbo", _id("co_seq_dim_cbo"), sa.Column("nu_cbo", _S(20)), sa.Column("no_cbo", _S(500)), sa.Column("st_registro_valido", sa.Integer)),
    "tb_dim_equipe": _table("tb_dim_equipe", _id("co_seq_dim_equipe"), sa.Column("nu_ine", _S(20)), sa.Column("no_equipe", _S(255)), sa.Column("st_registro_valido", sa.Integer)),
    "tb_dim_unidade_saude": _table("tb_dim_unidade_saude", _id("co_seq_dim_unidade_saude"), sa.Column("nu_cnes", _S(20)), sa.Column("no_unidade_saude", _S(500)), sa.Column("no_bairro", _S(500)), sa.Column("st_registro_valido", sa.Integer)),
    "tb_dim_tempo": _table("tb_dim_tempo", _id("co_seq_dim_tempo"), sa.Column("dt_registro", sa.Date), sa.Column("nu_dia", sa.SmallInteger), sa.Column("nu_mes", sa.SmallInteger), sa.Column("nu_ano", sa.Integer), sa.Column("ds_dia_semana", _S(100))),
    "tb_dim_turno": _table("tb_dim_turno", _id("co_seq_dim_turno"), sa.Column("nu_identificador", _S(100)), sa.Column("ds_turno", _S(500)), sa.Column("co_ordem", sa.Integer)),
    "tb_dim_desfecho_visita": _table("tb_dim_desfecho_visita", _id("co_seq_dim_desfecho_visita"), sa.Column("nu_identificador", _S(100)), sa.Column("ds_desfecho_visita", _S(500)), sa.Column("co_ordem", sa.Integer)),
    "tb_dim_tipo_imovel": _table("tb_dim_tipo_imovel", _id("co_seq_dim_tipo_imovel"), sa.Column("nu_identificador", _S(100)), sa.Column("ds_tipo_imovel", _S(500)), sa.Column("co_ordem", sa.Integer)),
}
SIM_VISITA = _table(
    "tb_fat_visita_domiciliar", _id("co_seq_fat_visita_domiciliar"), sa.Column("nu_uuid_ficha", _S(92)),
    *[sa.Column(c, sa.BigInteger) for c in ("co_dim_tipo_ficha", "co_dim_municipio", "co_dim_profissional", "co_dim_cbo",
                                            "co_dim_unidade_saude", "co_dim_equipe", "co_dim_tempo", "co_dim_tipo_imovel",
                                            "co_dim_turno", "co_dim_desfecho_visita")],
    sa.Column("nu_micro_area", _S(3)), sa.Column("st_visita_compartilhada", sa.Integer),
    *[sa.Column(col, sa.Integer) for col, _ in MOTIVOS],
    sa.Column("nu_latitude", sa.Float), sa.Column("nu_longitude", sa.Float), sa.Column("co_uuid_origem_fcd", _S(44)))
SIM_FICHA = _table("tb_cds_ficha_visita_domiciliar", _id("co_seq_cds_ficha_visita_dom"), sa.Column("dt_ficha", sa.DateTime),
                   sa.Column("st_ficha", sa.Integer), sa.Column("co_unico_ficha", _S(96), nullable=False),
                   sa.Column("co_cds_prof", sa.BigInteger, nullable=False), sa.Column("ds_versao_ficha", _S(30)))
SIM_DOMICILIO = _table(
    "tb_fat_cad_domiciliar", _id("co_seq_fat_cad_domiciliar"), sa.Column("nu_uuid_ficha", _S(92)), sa.Column("nu_uuid_ficha_origem", _S(92)),
    sa.Column("qt_morador", sa.Integer), sa.Column("nu_comodo", sa.Integer), sa.Column("st_recusa_cadastro", sa.Integer),
    *[sa.Column(c, sa.BigInteger) for c in ("co_dim_tipo_ficha", "co_dim_tipo_imovel", "co_dim_profissional", "co_dim_municipio",
                                            "co_dim_unidade_saude", "co_dim_equipe", "co_dim_tempo", "co_dim_cbo")],
    sa.Column("nu_micro_area", _S(3)), sa.Column("nu_cep", _S(33)), sa.Column("no_logradouro", _S(288)),
    sa.Column("nu_num_logradouro", _S(64)), sa.Column("no_bairro", _S(545)), sa.Column("nu_latitude", sa.Float), sa.Column("nu_longitude", sa.Float))

NOMES_SIM = ("Maria José da Silva", "Josefa Alves de Lima", "Antônio Carlos Ferreira", "Luciana Barbosa Santos",
             "Francisco de Assis Melo", "Rita de Cássia Araújo", "José Roberto Cavalcanti", "Edneide Gomes Pereira",
             "Cícero Batista Torres", "Marta Valéria Souza", "Severino Ramos Lins", "Ana Paula Nascimento")
RUAS_SIM = ("Rua Cardeal Arcoverde", "Rua Barão de Vila Bela", "Av. Ademar de Barros", "Rua Santa Águeda", "Rua do Prado",
            "Rua São Sebastião", "Travessa da Matriz", "Rua Duque de Caxias", "Rua Joaquim Nabuco", "Rua Xucurus")
BAIRROS_SIM = ("Centro", "Prado", "Xucurus", "Baixa Grande", "Mutirão", "Pitanga")
DIAS_SEMANA = ("SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO")


def gerar_simulado(ibge, municipio="", centro=(-8.3558, -36.6978), *, acs=6, ace=2, domicilios=300, visitas=1500,
                   dias=30, hoje=None, seed=None):
    """Recria o PEC simulado (dimensões + fatos) com dados fictícios no layout real."""
    rnd = random.Random(seed)
    hoje = hoje or date.today()
    engine = sim_engine()
    SIM.drop_all(engine)
    SIM.create_all(engine)
    d = SIM_DIMS
    rows = {name: [] for name in list(d) + ["visitas", "fichas", "domicilios"]}
    rows["tb_dim_municipio"].append(dict(co_seq_dim_municipio=1, no_municipio=municipio or "MUNICÍPIO SIMULADO", co_ibge=ibge, st_registro_valido=1))
    rows["tb_dim_cbo"] += [dict(co_seq_dim_cbo=1, nu_cbo="515105", no_cbo="AGENTE COMUNITÁRIO DE SAÚDE", st_registro_valido=1),
                           dict(co_seq_dim_cbo=2, nu_cbo="515140", no_cbo="AGENTE DE COMBATE ÀS ENDEMIAS", st_registro_valido=1)]
    rows["tb_dim_turno"] += [dict(co_seq_dim_turno=i, nu_identificador=k, ds_turno=v, co_ordem=i) for i, (k, v) in enumerate((("M", "Manhã"), ("T", "Tarde"), ("N", "Noite")), 1)]
    rows["tb_dim_desfecho_visita"] += [dict(co_seq_dim_desfecho_visita=i, nu_identificador=str(i), ds_desfecho_visita=v, co_ordem=i)
                                       for i, v in enumerate(("Visita realizada", "Visita recusada", "Ausente"), 1)]
    tipos = ("Domicílio", "Comércio", "Terreno baldio", "Ponto estratégico", "Escola")
    rows["tb_dim_tipo_imovel"] += [dict(co_seq_dim_tipo_imovel=i, nu_identificador=str(i), ds_tipo_imovel=v, co_ordem=i) for i, v in enumerate(tipos, 1)]
    unidades = [("USF Centro (simulada)", "Centro"), ("USF Prado (simulada)", "Prado")]
    for i, (nome, bairro) in enumerate(unidades, 1):
        rows["tb_dim_unidade_saude"].append(dict(co_seq_dim_unidade_saude=i, nu_cnes=f"99{rnd.randrange(10**5):05d}", no_unidade_saude=nome, no_bairro=bairro, st_registro_valido=1))
        rows["tb_dim_equipe"].append(dict(co_seq_dim_equipe=i, nu_ine=f"99{rnd.randrange(10**8):08d}", no_equipe=f"ESF {bairro} {i} (simulada)", st_registro_valido=1))
    profissionais = []  # (id, cbo_id, microarea, equipe/unidade, centro da microárea)
    nomes = rnd.sample(NOMES_SIM, min(len(NOMES_SIM), acs + ace))
    for i in range(acs + ace):
        is_acs = i < acs
        pid = i + 1
        rows["tb_dim_profissional"].append(dict(co_seq_dim_profissional=pid, nu_cns="7" + "".join(rnd.choice("0123456789") for _ in range(14)),
                                                no_profissional=(nomes[i] if i < len(nomes) else f"Agente {pid}").upper(), st_registro_valido=1))
        angle = 2 * math.pi * i / max(acs, 1)
        micro_centro = (centro[0] + 0.008 * math.sin(angle), centro[1] + 0.009 * math.cos(angle))
        profissionais.append(dict(id=pid, cbo=1 if is_acs else 2, micro=f"{i + 1:02d}" if is_acs else None,
                                  equipe=1 if (i < acs / 2 or not is_acs and i % 2 == 0) else 2, centro=micro_centro))
    acs_list = [p for p in profissionais if p["cbo"] == 1] or profissionais
    tempos = set()

    def tempo(dia):
        tempos.add(dia)
        return int(dia.strftime("%Y%m%d"))

    cnes = {u["co_seq_dim_unidade_saude"]: u["nu_cnes"] for u in rows["tb_dim_unidade_saude"]}
    casas = []
    for i in range(domicilios):
        dono = acs_list[i % len(acs_list)]
        lat, lng = dono["centro"][0] + rnd.gauss(0, 0.0014), dono["centro"][1] + rnd.gauss(0, 0.0014)
        ficha = f"{cnes[dono['equipe']]}-{uuid.UUID(int=rnd.getrandbits(128), version=4)}"
        tipo = rnd.choices(range(1, 6), weights=(85, 7, 3, 3, 2))[0]
        bairro = BAIRROS_SIM[(dono["id"] - 1) % len(BAIRROS_SIM)]
        cadastro = hoje - timedelta(days=rnd.randrange(60, 720))
        casa = dict(co_seq_fat_cad_domiciliar=i + 1, nu_uuid_ficha=ficha, nu_uuid_ficha_origem=ficha, qt_morador=rnd.randint(1, 6) if tipo == 1 else 0,
                    nu_comodo=rnd.randint(2, 8), st_recusa_cadastro=1 if rnd.random() < 0.02 else 0, co_dim_tipo_ficha=None, co_dim_tipo_imovel=tipo,
                    co_dim_profissional=dono["id"], co_dim_municipio=1, co_dim_unidade_saude=dono["equipe"], co_dim_equipe=dono["equipe"],
                    co_dim_tempo=tempo(cadastro), co_dim_cbo=1, nu_micro_area=dono["micro"], nu_cep="55200000",
                    no_logradouro=rnd.choice(RUAS_SIM), nu_num_logradouro=str(rnd.randint(1, 980)), no_bairro=bairro,
                    nu_latitude=round(lat, 6), nu_longitude=round(lng, 6))
        rows["domicilios"].append(casa)
        casas.append(casa)
    por_micro = {}
    for casa in casas:
        por_micro.setdefault(casa["nu_micro_area"], []).append(casa)
    # dias úteis anteriores a hoje: nenhuma visita fica com horário no futuro
    dias_uteis = [hoje - timedelta(days=n) for n in range(1, dias + 1) if (hoje - timedelta(days=n)).weekday() < 5] or [hoje - timedelta(days=1)]
    for i in range(visitas):
        prof = rnd.choice(profissionais)
        casa = rnd.choice(por_micro.get(prof["micro"]) or casas)
        dia = rnd.choice(dias_uteis)
        turno = 1 if rnd.random() < 0.7 else 2
        hora = time(7, 30) if turno == 1 else time(13, 0)
        momento = datetime.combine(dia, hora) + timedelta(minutes=rnd.randrange(0, 270 if turno == 1 else 240))
        desfecho = rnd.choices((1, 2, 3), weights=(80, 7, 13))[0]
        motivos = dict.fromkeys((col for col, _ in MOTIVOS), 0)
        if desfecho == 1:
            if prof["cbo"] == 2:  # ACE: rotina de controle vetorial
                motivos.update(st_mot_vis_ctrl_ambnte_vetor=int(rnd.random() < 0.95), st_mot_vis_orintacao_prevncao=int(rnd.random() < 0.4),
                               st_ctrl_amb_vet_acao_educativa=int(rnd.random() < 0.6), st_ctrl_amb_vet_acao_mecanica=int(rnd.random() < 0.5))
                foco = rnd.random() < 0.08
                motivos.update(st_ctrl_amb_vet_imovel_foco=int(foco), st_ctrl_amb_vet_tratamnt_focal=int(foco or rnd.random() < 0.05))
            else:
                motivos.update(st_mot_vis_visita_periodica=int(rnd.random() < 0.5), st_mot_vis_acompanhamento=int(rnd.random() < 0.35),
                               st_mot_vis_cad_att=int(rnd.random() < 0.15), st_mot_vis_busca_ativa=int(rnd.random() < 0.15),
                               st_mot_vis_orintacao_prevncao=int(rnd.random() < 0.25), st_mot_vis_ctrl_ambnte_vetor=int(rnd.random() < 0.18))
                if motivos["st_mot_vis_ctrl_ambnte_vetor"]:
                    motivos["st_ctrl_amb_vet_acao_educativa"] = 1
            if not any(motivos.values()):
                motivos["st_mot_vis_visita_periodica"] = 1
        gps = rnd.random() < 0.95
        ficha = f"{cnes[prof['equipe']]}-{uuid.UUID(int=rnd.getrandbits(128), version=4)}"
        rows["fichas"].append(dict(co_seq_cds_ficha_visita_dom=i + 1, dt_ficha=momento, st_ficha=1, co_unico_ficha=ficha,
                                   co_cds_prof=prof["id"], ds_versao_ficha="7.3.3"))
        rows["visitas"].append(dict(co_seq_fat_visita_domiciliar=i + 1, nu_uuid_ficha=ficha, co_dim_tipo_ficha=None, co_dim_municipio=1,
                                    co_dim_profissional=prof["id"], co_dim_cbo=prof["cbo"], co_dim_unidade_saude=prof["equipe"],
                                    co_dim_equipe=prof["equipe"], co_dim_tempo=tempo(dia), co_dim_tipo_imovel=casa["co_dim_tipo_imovel"],
                                    co_dim_turno=turno, co_dim_desfecho_visita=desfecho, nu_micro_area=casa["nu_micro_area"],
                                    st_visita_compartilhada=0, **motivos,
                                    nu_latitude=round(casa["nu_latitude"] + rnd.gauss(0, 0.00008), 6) if gps else None,
                                    nu_longitude=round(casa["nu_longitude"] + rnd.gauss(0, 0.00008), 6) if gps else None,
                                    co_uuid_origem_fcd=casa["nu_uuid_ficha_origem"]))
    rows["tb_dim_tempo"] = [dict(co_seq_dim_tempo=int(t.strftime("%Y%m%d")), dt_registro=t, nu_dia=t.day, nu_mes=t.month, nu_ano=t.year,
                                 ds_dia_semana=DIAS_SEMANA[t.weekday()]) for t in sorted(tempos)]
    targets = dict(d, visitas=SIM_VISITA, fichas=SIM_FICHA, domicilios=SIM_DOMICILIO)
    with engine.begin() as conn:
        for name, data in rows.items():
            if data:
                conn.execute(targets[name].insert(), data)
    return {"profissionais": acs + ace, "acs": acs, "ace": ace, "domicilios": domicilios, "visitas": visitas, "dias": dias}


def limpar_sincronizados_simulados(prefeitura_id):
    """Ao recriar o conjunto simulado, os registros sincronizados do conjunto anterior deixam de valer."""
    for model in (EsusVisita, EsusDomicilio):
        model.query.filter_by(prefeitura_id=prefeitura_id, origem="simulado").delete(synchronize_session=False)
    db.session.commit()
