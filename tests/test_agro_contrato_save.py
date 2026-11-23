import time

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import InternalServerError

from app import create_app
from app.extensions import db
from app.models import AuditoriaUsuario, ContratoAgro, EquipeAgro, OrcamentoAgro, Prefeitura, RdMapeamentoAgro, Usuario
from app.modules.agro import routes as agro_routes
from app.shared.session_security import SESSION_KEY
from config import Config


@pytest.fixture
def app(monkeypatch):
    settings = {
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "isolated-agro-test-secret-long-enough",
        "DEBUG": True,
        "TESTING": True,
        "AUDIT_SKYBOX_ENABLED": False,
        "AUDIT_SYSLOG_ENABLED": False,
        "CENTRAL_TI_ENABLED": False,
        "CSS_BUNDLE_AUTO_BUILD": False,
        "CSRF_PROTECTION_ENABLED": False,
        "SECURITY_CONTROLS_ENABLED": True,
    }
    for key, value in settings.items():
        monkeypatch.setattr(Config, key, value, raising=False)
    monkeypatch.setattr("app.load_dotenv", lambda *_: None)
    monkeypatch.setattr("app.modules.backup.routes.start_daily_backup_scheduler", lambda *_: None)
    app = create_app()

    with app.app_context():
        db.create_all()
        db.session.add(Prefeitura(id=1, nome="Prefeitura teste", slug="teste"))
        db.session.add(Usuario(
            id=1, login="admin", nome_uvis="Admin teste", senha_hash="unused", tipo_usuario="admin", prefeitura_id=1,
        ))
        db.session.add(EquipeAgro(id=1, nome="Equipe teste", prefeitura_id=1))
        for budget_id, service in ((1, OrcamentoAgro.SERVICO_PULVERIZACAO), (2, OrcamentoAgro.SERVICO_MAPEAMENTO)):
            db.session.add(OrcamentoAgro(
                id=budget_id, prefeitura_id=1, cliente_nome="Cliente teste", nome_fazenda="Fazenda teste",
                servico=service, cep="01000000", logradouro="Rua teste", numero="10", bairro="Centro",
                cidade="São Paulo", uf="SP",
            ))
        db.session.add(RdMapeamentoAgro(
            orcamento_agro_id=2, prefeitura_id=1, equipe_agro_id=1, status=RdMapeamentoAgro.STATUS_PREENCHIDO,
            cliente_nome="Cliente teste", propriedade_nome="Fazenda teste", municipio="São Paulo",
        ))
        db.session.commit()
    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        now = time.time()
        session.update(_user_id="1", _fresh=True)
        session[SESSION_KEY] = {"csrf": "test-token", "created_at": now, "last_activity": now}
    return client


@pytest.mark.parametrize(("budget_id", "team_id"), [(1, None), (2, 1)])
def test_create_and_edit_contract(app, client, budget_id, team_id):
    url = f"/agro/orcamentos/{budget_id}/contrato"
    form = {
        "contratante_nome": "Cliente teste", "contratante_documento": "529.982.247-25",
        "contratante_cep": "01000-000", "contratante_logradouro": "Rua teste", "contratante_numero": "10",
        "contratante_bairro": "Centro", "contratante_cidade": "São Paulo", "contratante_uf": "SP",
        "propriedade_nome": "Fazenda teste", "propriedade_cep": "01000-000", "propriedade_logradouro": "Rua teste",
        "propriedade_numero": "10", "propriedade_bairro": "Centro", "propriedade_cidade": "São Paulo",
        "propriedade_uf": "SP", "descricao_servico": "Serviço contratado", "valor_total": "1200,00",
        "prazo_inicio_dias": "10", "prazo_pagamento_dias": "10", "cidade_assinatura": "São Paulo",
        "foro_cidade": "São Paulo", "data_assinatura": "2026-11-23",
    }
    assert client.post(url, data=form, headers={"Accept": "text/html"}).status_code == 302
    with app.app_context():
        contract = ContratoAgro.query.filter_by(orcamento_agro_id=budget_id).one()
        assert contract.equipe_agro_id == team_id
        assert contract.contratante_nome == "Cliente teste"
        assert contract.valor_total == 1200
        contract_id = contract.id

    assert client.post(url, data={**form, "contratante_nome": "Nome atualizado"}).status_code == 302
    with app.app_context():
        contract = ContratoAgro.query.filter_by(orcamento_agro_id=budget_id).one()
        assert contract.id == contract_id
        assert contract.equipe_agro_id == team_id
        assert contract.contratante_nome == "Nome atualizado"


@pytest.mark.parametrize("wrapped", [False, True])
def test_html_error_after_failed_flush_preserves_original_diagnostics(app, client, monkeypatch, wrapped):
    def failed_contract_flush():
        db.session.add(ContratoAgro(prefeitura_id=1, orcamento_agro_id=1))
        try:
            ContratoAgro.query.count()
        except IntegrityError as error:
            if wrapped:
                raise InternalServerError(original_exception=error) from error
            raise

    monkeypatch.setattr(agro_routes, "_build_agro_equipes_ativas", failed_contract_flush)
    response = client.post("/agro/orcamentos/1/contrato", headers={"Accept": "text/html"})
    assert response.status_code == 500
    assert "Identificador da ocorrência" in response.get_data(as_text=True)
    assert "contratante_nome" not in response.get_data(as_text=True)
    with app.app_context():
        assert ContratoAgro.query.count() == 0
        audit = AuditoriaUsuario.query.filter_by(endpoint="main.agro_contrato_editar", status_code=500).one()
        assert audit.requisicao_id in response.get_data(as_text=True)
        assert audit.detalhes["diagnostico"]["excecao"]["tipo"] == "IntegrityError"
