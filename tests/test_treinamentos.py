"""Autenticação, isolamento e distribuição dos materiais em SQLite descartável."""

import zipfile

import pytest

from app.extensions import db
from app.models import Usuario, Prefeitura, CentralTiPerfilConfiguracao
from app.modules.gestao_ti.permissions import validate_route_policy
from app.modules.treinamentos.catalog import MATERIALS, RESOURCE_DIR
from app.modules.vigilancia.sinan_import import parse_cases
from tests import test_central_ti as base


@pytest.fixture
def training():
    setup = base.CentralTiTests()
    setup.setUp()
    setup.app.config.update(CENTRAL_TI_ENFORCE_PERMISSIONS=True,
                            VIGILANCIA_IMPORT_ENABLED=True, SINAN_ENABLED=True,
                            ACOES_PUBLICAS_ENABLED=True)
    prefeitura = Prefeitura(id=14, nome="Pesqueira", slug="pesqueira-treinamento")
    db.session.add(prefeitura)
    for key, role, regiao in (("covisa", "visualizar", "COVISA"), ("agent", "agente_endemias", "")):
        user = Usuario(login=f"training_{key}", nome_uvis=f"Conta fictícia {key}", senha_hash="unused",
                       tipo_usuario=role, regiao=regiao, prefeitura_id=14)
        db.session.add(user)
        setup.users[key] = user
    db.session.commit()
    try:
        yield setup
    finally:
        setup.tearDown()


def test_training_and_files_require_login(training):
    for path in ("/treinamentos", "/treinamentos/arquivos/guia-geral", "/treinamentos/arquivos/kit-testes"):
        response = training.client.get(path)
        assert response.status_code == 302
        assert "/login" in response.location
        assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("role", ["dev", "covisa", "agent"])
def test_learning_center_available_without_granting_other_modules(training, role):
    training.login(role)
    # Um perfil com seleções vazias ainda pode ler materiais de apoio.
    code = "agente_endemias" if role == "agent" else role
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo=code, versao=2))
    db.session.commit()
    response = training.client.get("/treinamentos")
    assert response.status_code == 200
    assert '<span>Treinamentos</span>' in response.text
    assert "Cadastro territorial" in response.text and "21/10/2026" in response.text
    assert 'href="/vigilancia/planejamento' not in response.text
    assert 'href="/acoes-realizadas' not in response.text
    assert training.client.get("/treinamentos/arquivos/csv-visitas").status_code == 200
    if role == "agent":
        assert training.client.get("/vigilancia/planejamento").status_code == 403
        assert training.client.get("/admin/usuarios/novo").status_code == 403


def test_agent_gets_only_their_operational_shortcut(training):
    training.login("agent")
    response = training.client.get("/treinamentos")
    assert 'href="/vigilancia/agente?demo=true"' in response.text
    assert 'href="/vigilancia/planejamento' not in response.text
    assert 'href="/vigilancia/sinan' not in response.text


def test_resources_are_fixed_private_and_correctly_served(training):
    training.login()
    for material_id, (relative, mimetype) in MATERIALS.items():
        response = training.client.get(f"/treinamentos/arquivos/{material_id}")
        assert response.status_code == 200, material_id
        assert response.mimetype == mimetype
        assert response.data == (RESOURCE_DIR / relative).read_bytes()
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        expected = "inline" if mimetype == "application/pdf" else "attachment"
        assert response.headers["Content-Disposition"].startswith(expected)
        response.close()
    response = training.client.get("/treinamentos/arquivos/guia-geral?baixar=1")
    assert response.headers["Content-Disposition"].startswith("attachment")
    for path in ("inexistente", "..%2F..%2F.env", "guia-geral/../../.env"):
        assert training.client.get("/treinamentos/arquivos/" + path).status_code == 404


def test_page_and_downloads_do_not_write_database(training):
    training.login()
    from sqlalchemy import event
    def reject_write(conn, cursor, statement, *args):
        assert statement.lstrip().split()[0].upper() not in {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    event.listen(db.engine, "before_cursor_execute", reject_write)
    try:
        assert training.client.get("/treinamentos").status_code == 200
        assert training.client.get("/treinamentos/arquivos/kit-testes").status_code == 200
    finally:
        event.remove(db.engine, "before_cursor_execute", reject_write)
    validate_route_policy(training.app)


def test_kit_includes_current_linked_files_and_valid_sinan():
    with zipfile.ZipFile(RESOURCE_DIR / MATERIALS["kit-testes"][0]) as archive:
        names = archive.namelist()
        assert len([n for n in names if n.endswith(".csv")]) == 4
        assert any(n.endswith("LEIA_PRIMEIRO.txt") for n in names)
        for material_id in ("csv-territorio", "csv-amostra", "csv-visitas", "csv-sinan", "imagem-acao", "texto-acao"):
            source = RESOURCE_DIR / MATERIALS[material_id][0]
            assert archive.read("Pesqueira-DEMO/" + source.name) == source.read_bytes()
    content = (RESOURCE_DIR / MATERIALS["csv-sinan"][0]).read_bytes()
    assert len(parse_cases(content, dict(disease="dengue", ibge="2610905", year=2026), True)) == 6

