import base64
import json
import re
from datetime import datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app import create_app
from app.extensions import db
from app.models import (
    CentralTiPerfilConfiguracao,
    CentralTiSelecao,
    ChecklistSemanalAgro,
    EquipamentoAgro,
    EquipeAgro,
    PilotoAgro,
    Prefeitura,
    Usuario,
)
from app.modules.agro import checklists
from app.modules.piloto_checklists.service import CHECKLIST_DRONE_BOOL_FIELDS, CHECKLIST_VEICULO_BOOL_FIELDS
from config import Config


URL = "/agro/piloto/checklists/semanais"
NOW = datetime(2026, 11, 24, 9)


@pytest.fixture
def app(monkeypatch):
    for name, value in {
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "isolated-agro-checklists-testing-key",
        "DEBUG": True,
        "TESTING": True,
        "CENTRAL_TI_ENABLED": True,
        "CENTRAL_TI_ENFORCE_PERMISSIONS": True,
        "CSRF_PROTECTION_ENABLED": True,
        "SECURITY_CONTROLS_ENABLED": False,
        "CSS_BUNDLE_AUTO_BUILD": False,
        "AUDIT_SKYBOX_ENABLED": False,
        "AUDIT_SYSLOG_ENABLED": False,
    }.items():
        monkeypatch.setattr(Config, name, value, raising=False)
    monkeypatch.setattr("app.load_dotenv", lambda *_: None)
    monkeypatch.setattr("app.modules.backup.routes.start_daily_backup_scheduler", lambda *_: None)
    monkeypatch.setattr(checklists, "agora_brasilia_naive", lambda: NOW)

    app = create_app()
    with app.app_context():
        db.create_all()
        db.session.add_all([
            Prefeitura(id=1, slug="teste", nome="Município fictício"),
            Prefeitura(id=2, slug="outra", nome="Outro município fictício"),
            EquipeAgro(id=1, prefeitura_id=1, nome="Equipe Agro de teste"),
            EquipeAgro(id=2, prefeitura_id=1, nome="Equipe de fora"),
            PilotoAgro(id=1, prefeitura_id=1, equipe_agro_id=1, nome="Piloto Agro de teste"),
            PilotoAgro(id=2, prefeitura_id=1, equipe_agro_id=1, nome="Outro piloto Agro de teste"),
            Usuario(id=1, login="piloto-teste", nome_uvis="Piloto de teste", senha_hash="unused", tipo_usuario="piloto_agro",
                    prefeitura_id=1, piloto_agro_id=1),
            Usuario(id=2, login="admin-teste", nome_uvis="Admin de teste", senha_hash="unused", tipo_usuario="admin", prefeitura_id=1),
            Usuario(id=3, login="outro-piloto", nome_uvis="Outro piloto de teste", senha_hash="unused", tipo_usuario="piloto_agro",
                    prefeitura_id=1, piloto_agro_id=2),
        ])
        for equipment_id, tipo, identifier, equipe, prefeitura, status, funcao in [
            (1, "Veículo", "PLACA-TESTE", 1, None, "Ativo", "Apoio"),
            (2, "Drone Pulverizador", "DRONE-TESTE", 1, 1, "Operacional", "Pulverizacao"),
            (3, "Drone", "DRONE-OUTRA-EQUIPE", 2, 1, "Ativo", "Mapeamento"),
            (4, "Drone", "DRONE-OUTRO-MUNICIPIO", 1, 2, "Ativo", "Mapeamento"),
            (5, "Bateria", "BATERIA-SOLTA", 1, 1, "Ativo", "Pulverizacao"),
            (6, "Drone", "DRONE-MAPEAMENTO", 1, 1, "Ativo", "Mapeamento"),
            (7, "Veículo", "PLACA-INATIVA", 1, 1, "Inativo", None),
        ]:
            db.session.add(EquipamentoAgro(
                id=equipment_id, tipo=tipo, identificacao=identifier, modelo="Modelo fictício",
                equipe_agro_id=equipe, prefeitura_id=prefeitura, status=status, funcao_operacional=funcao,
            ))
        db.session.commit()
    yield app
    with app.app_context():
        db.engine.dispose()


def logged_client(app, user_id=1):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(_user_id=str(user_id), _fresh=True, _ija_csrf="checklist-test-token")
    return client


@pytest.fixture
def form():
    image = Image.new("RGBA", (640, 160))
    ImageDraw.Draw(image).line(((10, 30), (20, 50), (90, 25)), fill="black", width=3)
    signature = BytesIO()
    image.save(signature, format="PNG")
    return {
        **dict.fromkeys(CHECKLIST_VEICULO_BOOL_FIELDS + CHECKLIST_DRONE_BOOL_FIELDS, "1"),
        "_csrf_token": "checklist-test-token", "veiculo_id": "1", "drone_id": "2",
        "km_leitura": "1234.50", "num_baterias": "3", "num_baterias_wb": "0",
        "nome_responsavel": "Piloto Agro de teste",
        "assinatura_piloto": "data:image/png;base64," + base64.b64encode(signature.getvalue()).decode(),
    }


def rendered_data(response):
    body = response.get_data(as_text=True)
    return json.loads(re.search(r'id="agro-checklist-data">(.*?)</script>', body)[1])


def test_dashboard_and_checklist_show_only_active_team_equipment(app):
    client = logged_client(app)
    dashboard = client.get("/agro/piloto")
    assert dashboard.status_code == 200 and URL in dashboard.get_data(as_text=True)

    response = client.get(URL)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="1" selected' in body
    assert '23/11/2026 a 29/11/2026' in body
    for excluded in ("DRONE-OUTRA-EQUIPE", "DRONE-OUTRO-MUNICIPIO", "BATERIA-SOLTA", "PLACA-INATIVA"):
        assert excluded not in body
    for field in CHECKLIST_VEICULO_BOOL_FIELDS + CHECKLIST_DRONE_BOOL_FIELDS:
        assert f'name="{field}"' in body
    assert logged_client(app, 2).get(URL).status_code == 403


def test_save_both_and_update_only_the_selected_equipment_in_the_current_week(app, form, monkeypatch):
    client = logged_client(app)
    result = client.post(URL, data={**form, "freio_mao": "0", "condicao_embreagem_freios": "Folga na alavanca"})
    assert result.status_code == 303
    data = rendered_data(client.get(result.location))["saved"]
    assert data["1"]["fields"]["freio_mao"] is False
    assert data["1"]["fields"]["condicao_embreagem_freios"] == "Folga na alavanca"
    assert data["2"]["fields"]["tanque"] is True
    assert rendered_data(logged_client(app, 3).get(URL))["saved"] == {}

    result = client.post(URL, data={**form, "drone_id": "", "km_leitura": "1235.50"})
    assert result.status_code == 303
    with app.app_context():
        records = {record.tipo: record for record in ChecklistSemanalAgro.query.all()}
        assert set(records) == {"veiculo", "drone"}
        assert records["veiculo"].respostas["km_leitura"] == 1235.50
        assert "condicao_embreagem_freios" not in records["veiculo"].respostas
        assert records["drone"].respostas["num_baterias_wb"] == 0
        assert all(record.assinatura_piloto == form["assinatura_piloto"] for record in records.values())

    monkeypatch.setattr(checklists, "agora_brasilia_naive", lambda: NOW + timedelta(days=7))
    assert rendered_data(client.get(URL))["saved"] == {}
    assert client.post(URL, data={**form, "veiculo_id": ""}).status_code == 303
    with app.app_context():
        assert ChecklistSemanalAgro.query.count() == 3


@pytest.mark.parametrize("changes", [
    {"drone_id": "3"}, {"drone_id": "4"}, {"veiculo_id": "2"}, {"veiculo_id": "7"},
    {"freio_mao": "0"}, {"km_leitura": "NaN"}, {"assinatura_piloto": "data:image/png;base64,AAAA"},
    {"num_baterias_wb": "2.5"}, {"cameras": ""},
])
def test_rejects_invalid_partial_saves(app, form, changes):
    result = logged_client(app).post(URL, data={**form, **changes})
    assert result.status_code == 422
    assert rendered_data(result)["draft"] is not None
    with app.app_context():
        assert ChecklistSemanalAgro.query.count() == 0


def test_mapping_drone_ignores_tank_and_unauthenticated_post_is_refused(app, form):
    result = logged_client(app).post(URL, data={**form, "veiculo_id": "", "drone_id": "6", "tanque": "0"})
    assert result.status_code == 303
    with app.app_context():
        record = ChecklistSemanalAgro.query.one()
        assert record.equipamento_agro_id == 6
        assert "tanque" not in record.respostas
    assert app.test_client().post(URL, data=form).status_code == 302
    assert logged_client(app).post(URL, data={**form, "_csrf_token": ""}).status_code == 403


def test_configured_profile_can_consult_without_editing(app, form):
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo="piloto_agro", versao=2))
        for code in ("area:agro", "agro.checklists.consultar"):
            db.session.add(CentralTiSelecao(perfil_codigo="piloto_agro", codigo=code))
        db.session.commit()
    client = logged_client(app)
    result = client.get(URL)
    assert result.status_code == 200
    assert 'data-can-save="false"' in result.get_data(as_text=True)
    assert client.post(URL, data=form).status_code == 403


ADMIN_URL = "/agro/checklists/semanais"


@pytest.fixture
def admin_records(app, form):
    result = logged_client(app).post(URL, data={
        **form, "freio_mao": "0", "condicao_embreagem_freios": "Folga na alavanca",
    })
    assert result.status_code == 303
    with app.app_context():
        return {record.tipo: record.id for record in ChecklistSemanalAgro.query.all()}


def test_admin_list_filters_and_group_detail_reuse_the_agro_checklists(app, form, admin_records):
    admin = logged_client(app, 2)
    dashboard = admin.get("/agro/admin")
    assert dashboard.status_code == 200 and ADMIN_URL in dashboard.get_data(as_text=True)
    listing = admin.get(ADMIN_URL, query_string={"q": "Equipe Agro de teste", "data_fim": "2026-11-24"})
    body = listing.get_data(as_text=True)
    assert listing.status_code == 200
    assert "Piloto Agro de teste" in body and "1 veiculo(s) • 1 drone(s)" in body
    assert "Alerta de pendência" in body
    assert form["assinatura_piloto"] not in body
    assert "Nenhum checklist semanal encontrado" in admin.get(
        ADMIN_URL, query_string={"data_inicio": "2026-11-25"},
    ).get_data(as_text=True)

    detail = admin.get(f"{ADMIN_URL}/{admin_records['veiculo']}")
    assert detail.status_code == 200
    body = detail.get_data(as_text=True)
    for item in ("PLACA-TESTE", "DRONE-TESTE", "Freio de mão", "Folga na alavanca", "1234.50 km", form["assinatura_piloto"]):
        assert item in body
    assert 'href="/admin/checklists/semanais' not in body
    assert logged_client(app).get(ADMIN_URL).status_code == 403
    assert logged_client(app).get(f"{ADMIN_URL}/{admin_records['veiculo']}").status_code == 403


def test_admin_correction_preserves_original_signature_date_and_author(app, form, admin_records):
    admin = logged_client(app, 2)
    vehicle_id = admin_records["veiculo"]
    edit_url = f"/agro/checklists/{vehicle_id}/editar"
    edit = admin.get(edit_url)
    assert edit.status_code == 200
    revision = re.search(r'name="checklist_revision" value="([^\"]+)"', edit.get_data(as_text=True))[1]
    corrected = {**form, "checklist_revision": revision, "km_leitura": "1300.25", "assinatura_piloto": "ignored",
                 "nome_responsavel": "Outro nome", "condicao_embreagem_freios": "Ignorada sem defeito"}
    invalid = admin.post(edit_url, data={**corrected, "km_leitura": "-1"})
    assert invalid.status_code == 400
    assert "quilometragem válida" in invalid.get_data(as_text=True)
    assert admin.post(edit_url, data={**corrected, "_csrf_token": ""}).status_code == 403
    saved = admin.post(edit_url, data=corrected)
    assert saved.status_code == 303 and saved.location == f"{ADMIN_URL}/{vehicle_id}"
    detail = admin.get(saved.location).get_data(as_text=True)
    assert "1300.25 km" in detail and "Folga na alavanca" not in detail

    outdated = admin.post(edit_url, data={**corrected, "km_leitura": "1600"})
    assert outdated.status_code == 409
    with app.app_context():
        vehicle = db.session.get(ChecklistSemanalAgro, vehicle_id)
        assert vehicle.data_registro == NOW and vehicle.nome_responsavel == form["nome_responsavel"]
        assert vehicle.piloto_agro_id == vehicle.equipe_agro_id == vehicle.equipamento_agro_id == 1
        assert vehicle.assinatura_piloto == form["assinatura_piloto"]
        assert vehicle.respostas["km_leitura"] == 1300.25 and vehicle.respostas["freio_mao"] is True
        assert "condicao_embreagem_freios" not in vehicle.respostas
        assert db.session.get(ChecklistSemanalAgro, admin_records["drone"]).respostas["num_baterias"] == 3


def test_agro_admin_scopes_records_and_honors_read_only_permissions(app, form, admin_records):
    with app.app_context():
        db.session.add(Usuario(
            id=4, login="gestor-externo", nome_uvis="Gestor externo fictício", senha_hash="unused",
            tipo_usuario="prefeitura_admin", prefeitura_id=2, trabalha_agro=True,
        ))
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo="admin", versao=2))
        for code in ("area:agro", "agro.checklists.consultar"):
            db.session.add(CentralTiSelecao(perfil_codigo="admin", codigo=code))
        db.session.commit()

    record_id = admin_records["veiculo"]
    edit_url = f"/agro/checklists/{record_id}/editar"
    admin = logged_client(app, 2)
    body = admin.get(f"{ADMIN_URL}/{record_id}").get_data(as_text=True)
    assert "PLACA-TESTE" in body and edit_url not in body
    assert admin.get(edit_url).status_code == 403
    assert admin.post(edit_url, data=form).status_code == 403
    outsider = logged_client(app, 4)
    assert "Nenhum checklist semanal encontrado" in outsider.get(ADMIN_URL).get_data(as_text=True)
    assert outsider.get(f"{ADMIN_URL}/{record_id}").status_code == 404
    assert outsider.get(edit_url).status_code == 404

    with app.app_context():
        db.session.add(CentralTiSelecao(perfil_codigo="admin", codigo="agro.checklists.corrigir"))
        db.session.commit()
    assert admin.get(edit_url).status_code == 200


def test_admin_can_open_archived_mapping_drone_without_an_equipment_link(app, form):
    result = logged_client(app).post(URL, data={**form, "veiculo_id": "", "drone_id": "6"})
    assert result.status_code == 303
    with app.app_context():
        record = ChecklistSemanalAgro.query.one()
        record_id = record.id
        record.equipamento_agro_id = record.piloto_agro_id = record.equipe_agro_id = None
        db.session.commit()

    admin = logged_client(app, 2)
    detail = admin.get(f"{ADMIN_URL}/{record_id}")
    assert detail.status_code == 200
    assert "DRONE-MAPEAMENTO" in detail.get_data(as_text=True)
    edit = admin.get(f"/agro/checklists/{record_id}/editar")
    assert edit.status_code == 200
    assert 'name="tanque"' not in edit.get_data(as_text=True)
