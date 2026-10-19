"""A central respeita o acesso e funciona antes da migração dos dados de campo."""

import pytest
from sqlalchemy import event

from app.extensions import db
from app.modules.vigilancia.field_models import FIELD_TABLES
from tests.test_vigilancia_field_routes import client, login


def test_hub_requires_authenticated_authorized_user(client):
    assert client.get('/vigilancia').status_code == 302
    login(client, 'uvis')
    assert client.get('/vigilancia').status_code == 403
    login(client)
    response = client.get('/vigilancia')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'


def test_hub_without_field_schema_does_not_query_data(client):
    login(client)
    with client.application.app_context():
        engine = db.engine
        for table in reversed(FIELD_TABLES):
            table.drop(engine)
        def reject_query(*args):
            pytest.fail('A central de navegação não deve consultar dados dos módulos.')
        event.listen(engine, 'before_cursor_execute', reject_query)
        try:
            assert client.get('/vigilancia').status_code == 200
        finally:
            event.remove(engine, 'before_cursor_execute', reject_query)


def test_disabled_modules_have_no_unavailable_links(client):
    login(client)
    client.application.config.update(SINAN_ENABLED=False, VIGILANCIA_IMPORT_ENABLED=False,
                                     VIGILANCIA_PREVIEW_ENABLED=False)
    response = client.get('/vigilancia')
    assert response.status_code == 200
    assert response.text.count('Aguardando ativação neste ambiente') == 3
    for path in ('/vigilancia/sinan', '/vigilancia/campo', '/vigilancia/importacoes', '/vigilancia/validacao'):
        assert f'href="{path}"' not in response.text


@pytest.mark.parametrize('import_enabled,preview_enabled', [(True, True), (True, False), (False, True)])
def test_enabled_file_workflows_remain_accessible(client, import_enabled, preview_enabled):
    login(client)
    client.application.config.update(VIGILANCIA_IMPORT_ENABLED=import_enabled,
                                     VIGILANCIA_PREVIEW_ENABLED=preview_enabled)
    response = client.get('/vigilancia')
    assert response.status_code == 200
    assert ('href="/vigilancia/importacoes"' in response.text) == import_enabled
    assert ('href="/vigilancia/validacao"' in response.text) == preview_enabled
