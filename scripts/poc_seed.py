"""Base de demonstração da POC CONDOMAR num ambiente (idempotente, pode repetir).

Uso (Shell do Render ou local):
  python scripts/poc_seed.py --prefeitura-id 14 --usuario-demo igor.dac --agente-login agente.pesqueira --agente-senha '...'

Cria: usuário agente de endemias; plano LIRAa liberado com 3 quarteirões atribuídos ao agente;
carga de campo (amostra geolocalizada confirmada → IIP, depósitos, pendentes, mapa de risco);
regras de alerta; relatos de foco e de saúde no bairro Centro (dispara o alerta);
importação SINAN do DATASUS (dona = usuário demo); rastro GPS de hoje para o agente.
"""

import argparse
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from werkzeug.datastructures import MultiDict  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Prefeitura, Usuario  # noqa: E402

QUARTEIROES = [
    ("Q-001", "Centro", "A01", 120, "Entre a Rua Dom Pedro e a Av. Principal", 12),
    ("Q-002", "Centro", "A01", 95, "Ao lado da Praça da Matriz", 10),
    ("Q-003", "Prado", "A02", 80, "Rua do Prado, lado par", 8),
]
DENUNCIAS = [
    ("Aedes", "Imovel Geral", "Caixa d'agua", "Rua Dom Pedro II", "120", "Centro", "-8.3570", "-36.6970", "Caixa d'água destampada no quintal."),
    ("Aedes", "Imovel Geral", "Piscina", "Rua Barão de Vila Bela", "45", "Centro", "-8.3562", "-36.6975", "Piscina abandonada com água parada."),
    ("Aedes", "Imovel Geral", "Terreno com Inservíveis", "Rua Três de Agosto", "300", "Centro", "-8.3580", "-36.6960", "Terreno com pneus e garrafas."),
    ("Culex", "", "Area alagada", "Rua do Prado", "88", "Prado", "-8.3610", "-36.6940", "Alagamento permanente na calçada."),
]
RELATOS = [
    ("Maria das Dores", "87999110001", "Rua Dom Pedro II", "130", "Centro", "Febre alta, dor atrás dos olhos e manchas vermelhas há 3 dias."),
    ("José Carlos", "87999110002", "Rua Barão de Vila Bela", "52", "Centro", "Febre, dor no corpo e enjoo desde ontem."),
]


def log(msg):
    print(f"[poc-seed] {msg}", flush=True)


def ibge_for(app, prefeitura_id):
    import json
    mapping = json.loads(app.config.get("VIGILANCIA_MUNICIPIOS_IBGE") or "{}")
    return mapping.get(str(prefeitura_id))


def seed_agent(args, prefeitura):
    user = Usuario.query.filter_by(login=args.agente_login).first()
    if user is None:
        user = Usuario(login=args.agente_login, nome_uvis=args.agente_nome, tipo_usuario="agente_endemias", prefeitura_id=prefeitura.id)
        user.set_senha(args.agente_senha)
        db.session.add(user)
        db.session.commit()
        log(f"agente criado: {user.login} (id {user.id})")
    else:
        if args.agente_senha:
            user.set_senha(args.agente_senha)
        user.prefeitura_id = prefeitura.id
        user.tipo_usuario = "agente_endemias"
        db.session.commit()
        log(f"agente já existia: {user.login} (id {user.id}), senha/prefeitura atualizadas")
    return user


def seed_plan(prefeitura, agente, demo):
    from app.modules.vigilancia.field_models import CampoLevantamento
    from app.modules.vigilancia.planning_models import CampoPlano, CampoPlanoEstrato, CampoPlanoQuarteirao, CampoQuarteirao
    pid, code = prefeitura.id, f"LIRAA-{date.today():%Y-%m}"
    inicio, fim = date.today().replace(day=1), date.today() + timedelta(days=45)
    for q, bairro, area, imoveis, ref, _ in QUARTEIROES:
        if not db.session.get(CampoQuarteirao, (pid, demo, q)):
            db.session.add(CampoQuarteirao(prefeitura=pid, demo=demo, code=q, bairro=bairro, area=area, imoveis=imoveis,
                                           referencia=ref, geometria=None, atualizado_por="poc-seed", atualizado_em=time.time()))
    if not db.session.get(CampoLevantamento, (pid, demo, code)):
        db.session.add(CampoLevantamento(prefeitura=pid, demo=demo, code=code))
    db.session.flush()
    if not db.session.get(CampoPlano, (pid, demo, code)):
        db.session.add(CampoPlano(prefeitura=pid, demo=demo, code=code, titulo=f"LIRAa {date.today():%B/%Y} · {prefeitura.nome}".replace("Prefeitura de ", ""),
                                  inicio=inicio, fim=fim, responsavel="Coordenação de Endemias", fonte="Base de demonstração POC",
                                  status="LIBERADO", versao=1, historico=[]))
    db.session.flush()
    if not db.session.get(CampoPlanoEstrato, (pid, demo, code, "E1")):
        db.session.add(CampoPlanoEstrato(prefeitura=pid, demo=demo, plano=code, code="E1", imoveis=sum(q[3] for q in QUARTEIROES),
                                         meta=sum(q[5] for q in QUARTEIROES), criterio="Estrato urbano central"))
    db.session.flush()
    for q, bairro, area, imoveis, ref, meta in QUARTEIROES:
        row = db.session.get(CampoPlanoQuarteirao, (pid, demo, code, q))
        if row is None:
            row = CampoPlanoQuarteirao(prefeitura=pid, demo=demo, plano=code, quarteirao=q, estrato="E1", meta=meta,
                                       territorio={"bairro": bairro, "area": area, "imoveis": imoveis, "referencia": ref})
            db.session.add(row)
        row.agente_id = agente.id
    db.session.commit()
    log(f"plano {code} liberado com {len(QUARTEIROES)} quarteirões atribuídos a {agente.login}")
    return code


def seed_field(prefeitura, ibge, actor, demo):
    from app.modules.vigilancia.field_store import FieldStore, FieldConflict, FieldStoreError
    from app.modules.vigilancia.sample import build_geolocated_sample_csv
    content = build_geolocated_sample_csv(prefeitura.id, ibge, date.today() - timedelta(days=10))
    store = FieldStore()
    try:
        batch = store.prepare(content, prefeitura=prefeitura.id, actor=actor, source="Base de demonstração POC",
                              filename="amostra-poc.csv", demo=demo)
        batch = store.confirm(batch["id"], prefeitura=prefeitura.id, actor=actor)
        log(f"carga de campo confirmada: lote {batch['id'][:8]} ({batch.get('status')})")
    except (FieldConflict, FieldStoreError) as exc:
        log(f"carga de campo não repetida: {exc}")


def seed_rules(prefeitura, user, email):
    from app.modules.alertas.models import AlertaRegra
    rules = [
        dict(nome="Focos no Centro", fonte="denuncias", bairro="Centro", janela_dias=7, limiar=2, raio_km=3.0),
        dict(nome="Casos suspeitos no município", fonte="relatos", bairro=None, janela_dias=7, limiar=2, raio_km=5.0),
    ]
    for data in rules:
        if AlertaRegra.query.filter_by(prefeitura_id=prefeitura.id, nome=data["nome"]).first():
            continue
        db.session.add(AlertaRegra(prefeitura_id=prefeitura.id, intervalo_horas=0, notificar_app=True, notificar_push=True,
                                   notificar_email=bool(email), emails=email or None, criado_por_id=user.id, **data))
    db.session.commit()
    log("regras de alerta prontas (Focos no Centro ≥2/7d, Casos suspeitos ≥2/7d)")


def seed_reports(app, prefeitura):
    from app.modules.portal_cidadao.service import criar_denuncia, DenunciaValidationError
    from app.modules.relatos_saude.service import create_report
    from app.models import Denuncia
    cidade = prefeitura.nome.replace("Prefeitura de ", "")
    existing = Denuncia.query.filter_by(prefeitura_id=prefeitura.id, cidadao_nome="Cidadão Demonstração").count()
    if existing >= len(DENUNCIAS):
        log(f"relatos de foco já existiam ({existing})")
    else:
        with app.test_request_context():
            for tipo, imovel, foco, rua, numero, bairro, lat, lng, desc in DENUNCIAS[existing:]:
                form = MultiDict(dict(prefeitura_id=str(prefeitura.id), tipo_visita=tipo, tipo_imovel=imovel, foco=foco, descricao=desc,
                                      logradouro=rua, numero=numero, bairro=bairro, cidade=cidade, uf="PE", latitude=lat, longitude=lng,
                                      nome="Cidadão Demonstração", cpf="529.982.247-25", rg="1234567", telefone="(87) 99999-0000", consentimento="on"))
                try:
                    d = criar_denuncia(form, MultiDict(), ip_origem="127.0.0.1", user_agent="poc-seed")
                    log(f"relato de foco {d.protocolo} ({foco}, {bairro})")
                except DenunciaValidationError as exc:
                    log(f"relato de foco rejeitado: {exc}")
    from app.models import RelatoSaude
    if RelatoSaude.query.filter_by(prefeitura_id=prefeitura.id, cidadao_nome=RELATOS[0][0]).first():
        log("relatos de saúde já existiam")
        return
    with app.test_request_context():
        for nome, tel, rua, numero, bairro, desc in RELATOS:
            form = dict(prefeitura_id=str(prefeitura.id), nome=nome, telefone=tel, logradouro=rua, numero=numero, bairro=bairro,
                        descricao=desc, inicio_sintomas=(date.today() - timedelta(days=3)).isoformat(), consentimento="1")
            row = create_report(form, uuid.uuid4().hex, "poc-seed:" + nome)
            if isinstance(row, dict):
                log(f"relato de saúde rejeitado: {row}")
            else:
                db.session.commit()
                log(f"relato de saúde {row.protocolo} ({nome})")


def seed_sinan(prefeitura, ibge, user):
    from app.modules.vigilancia import sinan_import
    from app.modules.vigilancia.sinan_database import DatabaseStore, BusyError
    from app.modules.vigilancia.sinan_datasus import run
    owner = f"{user.prefeitura_id}:{user.id}"
    store = DatabaseStore(db.engine)
    scope = {"disease": "dengue", "ibge": ibge, "year": date.today().year}
    done = [j for j in store.list(owner, **scope)["jobs"] if j["kind"] == "datasus" and j["status"] == "completed"]
    if done:
        log(f"SINAN DATASUS já importado ({done[0]['count']} notificações)")
        return
    try:
        job_id, _ = store.create(owner, kind="datasus", **scope)
    except BusyError as exc:
        log(f"SINAN: {exc}")
        return
    log("SINAN: baixando o DBC do DATASUS (1 a 3 min)…")
    run(store, job_id, scope)
    job = store.get(job_id, owner)
    log(f"SINAN DATASUS: {job['status']} · {job['count']} notificações · {job['message']}")


def seed_track(agente):
    from app.modules.vigilancia.agent_tracking import AgentePosicao
    today = datetime.combine(date.today(), datetime.min.time())
    if AgentePosicao.query.filter(AgentePosicao.usuario_id == agente.id, AgentePosicao.registrado_em >= today).count():
        log("rastro de hoje já existia")
        return
    base = datetime.now().replace(hour=8, minute=5, second=0, microsecond=0)
    path = [(-8.3558, -36.6978), (-8.3562, -36.6971), (-8.3567, -36.6965), (-8.3573, -36.6961), (-8.3579, -36.6957),
            (-8.3584, -36.6950), (-8.3590, -36.6946), (-8.3596, -36.6941), (-8.3603, -36.6940), (-8.3610, -36.6940)]
    for i, (lat, lng) in enumerate(path):
        db.session.add(AgentePosicao(usuario_id=agente.id, prefeitura_id=agente.prefeitura_id, latitude=lat, longitude=lng,
                                     precisao_m=6, registrado_em=base + timedelta(minutes=9 * i), origem="app"))
    db.session.commit()
    log(f"rastro de hoje: {len(path)} pontos")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prefeitura-id", type=int, required=True)
    parser.add_argument("--usuario-demo", required=True, help="login de quem vai apresentar (dono do lote SINAN e autor das cargas)")
    parser.add_argument("--agente-login", default="agente.pesqueira")
    parser.add_argument("--agente-nome", default="Maria Agente")
    parser.add_argument("--agente-senha", default="", help="obrigatória se o agente ainda não existir")
    parser.add_argument("--email-alertas", default="", help="e-mail que recebe os alertas das regras criadas")
    parser.add_argument("--ibge", default="", help="código IBGE de 7 dígitos (padrão: VIGILANCIA_MUNICIPIOS_IBGE)")
    parser.add_argument("--demo", action="store_true", help="marca plano e carga como dados de demonstração (padrão: dados autorizados)")
    parser.add_argument("--sem-sinan", action="store_true")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        prefeitura = db.session.get(Prefeitura, args.prefeitura_id)
        if prefeitura is None:
            sys.exit("prefeitura não encontrada")
        user = Usuario.query.filter_by(login=args.usuario_demo).first()
        if user is None:
            sys.exit("usuário demo não encontrado")
        ibge = args.ibge or ibge_for(app, prefeitura.id)
        if not ibge:
            sys.exit("informe --ibge (prefeitura sem código em VIGILANCIA_MUNICIPIOS_IBGE)")
        log(f"{prefeitura.nome} (id {prefeitura.id}, IBGE {ibge}) · modo {'demonstração' if args.demo else 'dados autorizados'}")
        agente = seed_agent(args, prefeitura) if (args.agente_senha or Usuario.query.filter_by(login=args.agente_login).first()) else None
        if agente is None:
            sys.exit("informe --agente-senha para criar o agente")
        seed_plan(prefeitura, agente, args.demo)
        seed_field(prefeitura, ibge, str(user.id), args.demo)
        seed_rules(prefeitura, user, args.email_alertas)
        seed_reports(app, prefeitura)
        seed_track(agente)
        if not args.sem_sinan:
            seed_sinan(prefeitura, ibge, user)
        log("concluído")


if __name__ == "__main__":
    main()
