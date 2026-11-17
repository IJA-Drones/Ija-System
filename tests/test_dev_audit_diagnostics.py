import json
from datetime import datetime
from unittest.mock import patch

from flask import current_app

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario
from app.modules.auditoria.recorder import register_audit
from app.modules.auditoria.diagnostics import record_exception
from app.modules.chatbot import dev_diagnostics
from tests.test_azul_exports import app, client


def test_request_logs_are_persisted_bounded_and_private(app):
    register_audit(app)

    @app.post('/test-error')
    def error():
        try:
            raise ValueError('PRIVATE_EXCEPTION_VALUE')
        except ValueError:
            current_app.logger.exception('Upload falhou para %s', 'PRIVATE_ARGUMENT')
        for _ in range(15):
            current_app.logger.warning('Outro aviso')
        return '', 500

    @app.post('/test-next')
    def next_request():
        return '', 400

    c = client(app)
    assert c.post('/test-error').status_code == 500
    assert c.post('/test-next').status_code == 400
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(endpoint='error').one()
        logs = row.detalhes['diagnostico']['logs']
        assert len(logs) == 10
        assert row.detalhes['diagnostico']['logs_truncados'] is True
        assert logs[0]['mensagem_modelo'] == 'Upload falhou para %s'
        assert logs[0]['excecao']['tipo'] == 'ValueError'
        assert logs[0]['excecao']['frames'][-1]['funcao'] == 'error'
        assert 'PRIVATE_' not in json.dumps(row.detalhes)
        other = AuditoriaUsuario.query.filter_by(endpoint='next_request').one()
        assert other.requisicao_id != row.requisicao_id
        assert other.detalhes['diagnostico']['logs'] == []


def test_handled_conflict_retains_reason_without_exception_values(app):
    from app.shared.edit_control import EditConflict
    register_audit(app)

    @app.post('/conflict')
    def conflict():
        try:
            raise EditConflict('PRIVATE_OWNER_NAME', reason='expired')
        except EditConflict as exc:
            record_exception(exc, reason=exc.reason)
        return '', 409

    client(app).post('/conflict')
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(endpoint='conflict').one()
        exception = row.detalhes['diagnostico']['excecao']
        assert exception['motivo'] == 'expired'
        assert exception['tipo'] == 'EditConflict'
        assert exception['frames']
        assert 'PRIVATE_OWNER_NAME' not in json.dumps(row.detalhes)


def test_audit_context_correlates_request_and_excludes_unrelated_users(app):
    now = datetime.now()
    with app.app_context():
        def add(kind, user=1, request_id=None, **kw):
            row = AuditoriaUsuario(usuario_id=user, usuario_nome='PRIVATE_NAME', metodo='PUT',
                                   path='/api/os/<int:os_id>', endpoint='main.os_upload_complementary_stream',
                                   status_code=409, criado_em=now, tipo_evento=kind,
                                   requisicao_id=request_id, **kw)
            db.session.add(row)
            db.session.flush()
            return row
        target = add('CONFLITO_EDICAO', request_id='request1', detalhes={'diagnostico': {
            'versao': 1, 'excecao': {'tipo': 'EditConflict', 'motivo': 'expired', 'frames': []}},
            'token': 'PRIVATE_TOKEN', 'identificadores': {'os_id': 15}})
        sibling = add('EDICAO', request_id='request1', detalhes={'campos': {
            'versao': {'antes': 1, 'depois': 2}, 'senha_hash': {'depois': 'PRIVATE_HASH'}}})
        other = add('REQUISICAO', user=2, request_id='request2')
        db.session.commit()
        data = dev_diagnostics.evidence(db.session.get(Usuario, 1), target.id)
        audit = data['auditoria']
        assert [item['id'] for item in audit['mesma_requisicao']] == [sibling.id]
        assert other.id not in [item['id'] for item in audit['proximos_mesma_rota_e_usuario']]
        assert audit['registro_selecionado']['diagnostico']['excecao']['motivo'] == 'expired'
        assert audit['mesma_requisicao'][0]['alteracoes']['versao']['depois'] == 2
        assert 'PRIVATE_' not in json.dumps(data)
        assert 'Expired indica reserva encerrada' in data['roteiro']
        assert 'expired' in dev_diagnostics.local_answer(data)


def test_audit_permission_is_rechecked_and_historical_gap_is_explicit(app):
    with app.app_context():
        row = AuditoriaUsuario(usuario_nome='Teste', metodo='POST', path='/test', status_code=500,
                               tipo_evento='REQUISICAO', criado_em=datetime.now())
        db.session.add(row)
        db.session.commit()
        user = db.session.get(Usuario, 1)
        assert 'histórico sem captura' in dev_diagnostics.evidence(user, row.id)['auditoria']['cobertura']
        with patch.object(dev_diagnostics, 'can_access_endpoint', side_effect=lambda u, endpoint, *a, **kw: endpoint != 'main.admin_logs_usuarios'), patch('app.modules.chatbot.dev_audit.context') as query:
            data = dev_diagnostics.evidence(user, row.id)
            assert 'não autorizada' in data['auditoria']['cobertura']
            query.assert_not_called()


def test_dynamic_logs_and_invalid_diagnostics_do_not_expose_values(app):
    register_audit(app)

    @app.post('/dynamic')
    def dynamic():
        private = 'PRIVATE_DYNAMIC_SECRET'
        current_app.logger.warning(f'Falha: {private}')
        return '', 500

    client(app).post('/dynamic')
    with app.app_context():
        row = AuditoriaUsuario.query.filter_by(endpoint='dynamic').one()
        assert row.detalhes['diagnostico']['logs'][0]['mensagem_modelo'] == '[mensagem dinâmica omitida]'
        assert 'PRIVATE_DYNAMIC_SECRET' not in json.dumps(row.detalhes)


def test_log_followup_keeps_selected_error():
    from app.modules.chatbot import topics
    history = [{'role': 'user', 'content': 'Analise o erro #7'}]
    assert topics.evaluate('Consulte os logs e a auditoria', history).kind == 'allowed'
    assert dev_diagnostics.selected_id('Consulte os logs e a auditoria', history) == 7
