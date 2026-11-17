import importlib.util
import json
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario
from app.modules.chatbot import dev_audit, dev_code, dev_diagnostics, topics
from tests.test_azul_exports import app


def event(now, *, kind='REQUISICAO', endpoint='main.os_upload_complementary_stream', oid=15,
          object_type=None, tenant=1, actor=1, request_id=None, status=200, details=None):
    row = AuditoriaUsuario(usuario_id=actor, usuario_nome='PRIVATE_NAME', metodo='PUT',
                           path='/api/os/<int:os_id>/upload', endpoint=endpoint, status_code=status,
                           criado_em=now, tipo_evento=kind, requisicao_id=request_id, prefeitura_id=tenant,
                           objeto_id=str(oid), objeto_tipo=object_type or endpoint,
                           detalhes=details if details is not None else {'identificadores': {'os_id': oid}})
    db.session.add(row)
    db.session.flush()
    return row


def test_timeline_orders_reservation_upload_and_conflict_without_crossing_resources(app):
    with app.app_context():
        now = datetime.now()
        reservation = event(now - timedelta(minutes=20), kind='EDICAO_RESERVADA', endpoint='edit_control.lease',
                            object_type='solicitacao', actor=2, status=0)
        upload = event(now - timedelta(minutes=1), status=201)
        conflict = event(now, kind='CONFLITO_EDICAO', status=409, request_id='request1', details={
            'identificadores': {'os_id': 15}, 'diagnostico': {'versao': 1, 'excecao': {'motivo': 'expired'}}})
        related = event(now, kind='EDICAO', object_type='solicitacoes', request_id='request1')
        unrelated = [event(now, oid=16), event(now, tenant=2),
                     event(now, object_type='denuncias', endpoint='edit_control.lease'),
                     event(now - timedelta(minutes=31), kind='EDICAO_RESERVADA', object_type='solicitacao')]
        db.session.commit()
        timeline = dev_audit.context(conflict.id)['linha_do_tempo']
        assert [item['id'] for item in timeline['eventos']] == [reservation.id, upload.id, conflict.id, related.id]
        assert timeline['eventos'][0]['vinculo'] == 'mesmo_recurso'
        assert timeline['eventos'][2]['motivo'] == 'expired'
        assert timeline['eventos'][3]['vinculo'] == 'mesma_requisicao'
        assert timeline['recurso'] == {'tipo': 'solicitacao', 'id': 15}
        assert 'PRIVATE_NAME' not in json.dumps(timeline)
        assert not timeline['truncada']
        assert all(item['horario_brasilia'] for item in timeline['eventos'])
        assert not ({item.id for item in unrelated} & {item['id'] for item in timeline['eventos']})


def test_timeline_bounds_and_missing_identifiers_are_explicit(app):
    with app.app_context():
        now = datetime.now()
        target = event(now, status=500)
        for index in range(45):
            event(now - timedelta(seconds=index + 1), kind='EDICAO_RESERVADA', object_type='solicitacao')
        db.session.commit()
        timeline = dev_audit.context(target.id)['linha_do_tempo']
        assert timeline['truncada']
        assert len(timeline['eventos']) <= 41
        legacy = event(now, endpoint='legacy.route', details={})
        db.session.commit()
        timeline = dev_audit.context(legacy.id)['linha_do_tempo']
        assert timeline['recurso'] is None
        assert [item['id'] for item in timeline['eventos']] == [legacy.id]


@pytest.fixture
def source_module(app, tmp_path, monkeypatch):
    root = tmp_path / 'app'
    folder = root / 'modules' / 'diagnostic_fixture'
    folder.mkdir(parents=True)
    source = folder / 'routes.py'
    source.write_text('''from functools import wraps

def decorate(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def helper():
    token = "PRIVATE_LITERAL_TOKEN"
    return 409

@decorate
def handler():
    return helper()
''')
    name = 'app.modules.diagnostic_fixture.routes'
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(app, 'root_path', str(root))
    app.add_url_rule('/fixture', endpoint='main.fixture', view_func=module.handler)
    return module, source, root


def test_code_includes_decorated_handler_dependency_lines_hash_and_redacts_literals(app, source_module):
    module, source, root = source_module
    with app.app_context():
        data = dev_code.context(module.handler, {})
    snippets = data['trechos']
    assert [item['funcao'] for item in snippets] == ['handler', 'helper']
    assert snippets[0]['origem'] == 'rota'
    assert snippets[1]['origem'] == 'dependencia_direta'
    assert 'return helper()' in snippets[0]['codigo']
    assert 'PRIVATE_LITERAL_TOKEN' not in json.dumps(data)
    for item in snippets:
        assert item['arquivo'] == 'app/modules/diagnostic_fixture/routes.py'
        assert len(item['sha256_arquivo_atual']) == 64
        assert item['codigo'].startswith(f"{item['inicio']}: ")
    assert 'não comprova a versão' in data['versao']


def test_frames_cannot_read_arbitrary_files_and_stale_lines_are_not_used(app, source_module):
    module, source, root = source_module
    (root / 'secret.py').write_text('PRIVATE_FILE')
    audit = {'registro_selecionado': {'diagnostico': {'excecao': {'frames': [
        {'arquivo': 'app/../secret.py', 'funcao': 'secret', 'linha': 1},
        {'arquivo': 'app/modules/diagnostic_fixture/routes.py', 'funcao': 'helper', 'linha': 999},
    ]}}}}
    with app.app_context(), patch.object(dev_code, '_file', wraps=dev_code._file) as read:
        data = dev_code.context(None, audit)
    assert data['trechos'] == []
    assert all(call.args[0] == source for call in read.call_args_list)


def test_matching_frame_supplies_stack_function_without_executing_it(app, source_module):
    module, source, root = source_module
    audit = {'registro_selecionado': {'diagnostico': {'excecao': {'frames': [
        {'arquivo': 'app/modules/diagnostic_fixture/routes.py', 'funcao': 'helper', 'linha': 10},
    ]}}}}
    with app.app_context():
        data = dev_code.context(None, audit)
    assert len(data['trechos']) == 1
    assert data['trechos'][0]['origem'] == 'stack_trace'
    assert data['trechos'][0]['funcao'] == 'helper'


def test_evidence_integrates_code_and_timeline_and_enforces_permissions(app, source_module):
    module, source, root = source_module
    with app.app_context():
        row = event(datetime.now(), endpoint='main.fixture', status=500)
        db.session.commit()
        user = db.session.get(Usuario, 1)
        data = dev_diagnostics.evidence(user, row.id)
        assert data['codigo']['trechos'][0]['funcao'] == 'handler'
        assert data['auditoria']['linha_do_tempo']['eventos'][0]['id'] == row.id
        with patch.object(dev_diagnostics, 'allowed', return_value=False), patch.object(dev_code, '_file') as read:
            with pytest.raises(PermissionError):
                dev_diagnostics.evidence(user, row.id)
            read.assert_not_called()


def test_code_and_timeline_followups_remain_on_selected_error():
    history = [{'role': 'user', 'content': 'Analise o erro #7'}]
    for message in ['Mostre a linha do tempo', 'Quais trechos de código explicam isso?']:
        assert topics.evaluate(message, history).kind == 'allowed'
        assert dev_diagnostics.selected_id(message, history) == 7


def test_snippet_limits_and_trace_window_for_long_handler(app, source_module, monkeypatch):
    module, source, root = source_module
    source.write_text('def handler():\n' + ''.join(f'    value = {index}\n' for index in range(100)) + '    return value\n')
    spec = importlib.util.spec_from_file_location(module.__name__, source)
    replacement = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module.__name__, replacement)
    spec.loader.exec_module(replacement)
    audit = {'registro_selecionado': {'diagnostico': {'excecao': {'frames': [
        {'arquivo': 'app/modules/diagnostic_fixture/routes.py', 'funcao': 'handler', 'linha': 95},
    ]}}}}
    with app.app_context():
        data = dev_code.context(replacement.handler, audit)
    assert data['truncado']
    assert len(data['trechos']) == 2
    assert data['trechos'][1]['inicio'] <= 95 <= data['trechos'][1]['fim']
    assert all(item['fim'] - item['inicio'] + 1 <= dev_code.MAX_LINES for item in data['trechos'])
    assert sum(len(item['codigo']) for item in data['trechos']) <= dev_code.MAX_CHARS


def test_source_missing_and_symlinks_outside_app_are_not_read(app, source_module):
    module, source, root = source_module
    outside = root.parent / 'private.py'
    outside.write_text('PRIVATE_OUTSIDE')
    symlink = source.parent / 'external.py'
    symlink.symlink_to(outside)
    with app.app_context():
        assert dev_code._source_path(symlink) is None
        source.unlink()
        assert dev_code.context(module.handler, {})['trechos'] == []
