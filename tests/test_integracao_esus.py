"""Integração e-SUS APS: PEC simulado -> sincronização (síncrona e em segundo plano) -> API com token."""

import os
import re
from datetime import date, timedelta

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager

from app.extensions import db
from app.models import Prefeitura
from app.modules.integracoes import esus
from app.modules.integracoes.esus import ESUS_TABLES, EsusConfig, EsusExecucao, EsusVisita
from app.modules.integracoes.esus_routes import producao, register_routes


@pytest.fixture
def app():
    uri = os.environ.get("DATABASE_URL", "")
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-only-local-key", CENTRAL_TI_ENABLED=False,
                      SQLALCHEMY_DATABASE_URI=uri if uri.startswith("sqlite") else "sqlite:///:memory:")
    db.init_app(app)
    LoginManager(app).user_loader(lambda uid: None)
    bp = Blueprint("main", __name__)
    register_routes(bp)
    app.register_blueprint(bp)
    with app.app_context():
        Prefeitura.__table__.create(db.engine)
        for table in ESUS_TABLES:
            table.create(db.engine)
        db.session.add(Prefeitura(id=1, nome="Pesqueira", slug="pesqueira"))
        db.session.add(EsusConfig(prefeitura_id=1, modo="simulado", ibge="2610905"))
        db.session.commit()
        yield app
        db.session.remove()


def test_simulado_sincroniza_pelos_dois_caminhos_e_expoe_api(app):
    resumo = esus.gerar_simulado("2610905", "Pesqueira", acs=6, ace=2, domicilios=300, visitas=1500, dias=30, seed=7)
    assert resumo["visitas"] == 1500

    domicilios, visitas = esus.sincronizar_tudo(1, "sincrona")
    assert (domicilios.status, visitas.status) == ("concluida", "concluida"), (domicilios.mensagem, visitas.mensagem)
    assert domicilios.inseridos == 300 and visitas.lidos == visitas.inseridos == 1500
    rows = EsusVisita.query.all()
    assert {v.categoria for v in rows} == {"ACS", "ACE"}
    assert {v.desfecho for v in rows} == {"realizada", "recusada", "ausente"}
    assert any(v.motivo_aedes for v in rows) and len({v.profissional_nome for v in rows}) == 8
    assert all(re.fullmatch(r"\d\d:\d\d", v.hora) for v in rows)
    gps = [v for v in rows if v.latitude is not None]
    assert len(gps) > 1300 and all(-8.40 < v.latitude < -8.31 and -36.75 < v.longitude < -36.64 for v in gps)
    assert all(date.today() - timedelta(days=30) <= v.data < date.today() for v in rows)

    thread = esus.iniciar_em_segundo_plano(1)  # mesma função, em thread, registrando a execução
    thread.join(60)
    db.session.expire_all()
    fundo = EsusExecucao.query.filter_by(forma="assincrona", processo="visitas").one()
    assert fundo.status == "concluida" and fundo.inseridos == 0 and fundo.atualizados == 1500
    assert EsusVisita.query.count() == 1500

    painel = producao(1, date.today() - timedelta(days=30), date.today())
    assert painel["kpis"]["visitas"] == 1500 and len(painel["profissionais"]) == 8
    assert painel["kpis"]["realizadas"] + painel["kpis"]["recusadas"] + painel["kpis"]["ausentes"] == 1500
    assert {p["microarea"] for p in painel["profissionais"] if p["categoria"] == "ACE"} == {"6 microáreas"}

    cfg = db.session.get(EsusConfig, 1)
    token = esus.gerar_token(cfg)
    db.session.commit()
    assert cfg.token_hash != token and token not in (cfg.token_prefixo or "x" * 99)

    client = app.test_client()
    assert client.get("/api/integracoes/esus/visitas").status_code == 401
    assert client.get("/api/integracoes/esus/status", headers={"Authorization": "Bearer esus_invalido"}).status_code == 401
    auth = {"Authorization": f"Bearer {token}"}
    page = client.get("/api/integracoes/esus/visitas?categoria=ACE&per_page=50&page=2", headers=auth)
    assert page.status_code == 200
    body = page.get_json()
    assert body["page"] == 2 and len(body["items"]) == 50 and body["total"] > 100
    assert all(item["profissional"]["categoria"] == "ACE" for item in body["items"])
    nome = body["items"][0]["profissional"]["nome"]
    so_um = client.get(f"/api/integracoes/esus/visitas?profissional={nome}", headers=auth).get_json()
    assert so_um["total"] > 0 and {i["profissional"]["nome"] for i in so_um["items"]} == {nome}
    status = client.get("/api/integracoes/esus/status", headers=auth).get_json()
    assert status["totais"]["visitas"] == 1500 and status["totais"]["domicilios"] == 300 and len(status["execucoes"]) == 4

    cfg.ativo = False
    db.session.commit()
    assert client.get("/api/integracoes/esus/status", headers=auth).status_code == 401


def test_agendamento_e_falha_de_conexao_ao_pec_ficam_registrados(app):
    esus.gerar_simulado("2610905", "Pesqueira", acs=2, ace=1, domicilios=20, visitas=60, dias=10, seed=1)
    cfg = db.session.get(EsusConfig, 1)
    cfg.intervalo_min = 5
    db.session.commit()
    esus.executar_agendadas()
    esus.executar_agendadas()  # intervalo ainda não venceu: não repete
    agendadas = EsusExecucao.query.filter_by(forma="agendada").all()
    assert sorted((e.processo, e.status) for e in agendadas) == [("domicilios", "concluida"), ("visitas", "concluida")]

    EsusVisita.query.delete()
    db.session.commit()
    cfg.modo, cfg.host, cfg.porta, cfg.base, cfg.usuario = "pec", "127.0.0.1", 1, "esus", "leitura"
    db.session.commit()
    execucao = esus.sincronizar(1, "visitas")
    assert execucao.status == "falhou" and "conectar" in execucao.mensagem
    assert EsusVisita.query.count() == 0
