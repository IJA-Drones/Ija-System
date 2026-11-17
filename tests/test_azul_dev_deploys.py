from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models import AuditoriaUsuario, WatchdogDeployEvent
from app.modules.auditoria.recorder import register_audit
from app.modules.chatbot import dev_deploys, dev_diagnostics, topics
from app.modules.dev_dashboard.service import _parse_iso_datetime
from tests.test_azul_exports import app, client

SHA_A = 'a' * 40
SHA_B = 'b' * 40


def add(now, status=500, endpoint='main.upload', kind='REQUISICAO', details=None):
    row = AuditoriaUsuario(usuario_nome='PRIVATE_NAME', metodo='PUT', path='/test', status_code=status,
                           endpoint=endpoint, tipo_evento=kind, criado_em=now, detalhes=details)
    db.session.add(row)
    db.session.flush()
    return row


def test_release_is_recorded_once_and_attached_to_error(app):
    app.config['APP_RELEASE_SHA'] = SHA_B
    register_audit(app)
    app.add_url_rule('/error', endpoint='error', view_func=lambda: ('', 500), methods=['PUT'])
    c = client(app)
    c.put('/error')
    c.put('/error')
    with app.app_context():
        observed = AuditoriaUsuario.query.filter_by(tipo_evento='DEPLOY_OBSERVADO').all()
        assert len(observed) == 1
        assert observed[0].detalhes['release_sha'] == SHA_B
        errors = AuditoriaUsuario.query.filter_by(endpoint='error').all()
        assert len(errors) == 2
        assert all(row.detalhes['diagnostico']['release_sha'] == SHA_B for row in errors)


def test_deploy_context_compares_equal_windows_and_omits_private_urls(app):
    now = datetime(2026, 11, 17, 16, 0)
    with app.app_context():
        add(now - timedelta(days=1), 0, kind='DEPLOY_OBSERVADO', details={'release_sha': SHA_A})
        observed = add(now, 0, kind='DEPLOY_OBSERVADO', details={'release_sha': SHA_B})
        add(now - timedelta(minutes=10))
        add(now - timedelta(minutes=5), 200)
        error = add(now + timedelta(minutes=20), details={'diagnostico': {'release_sha': SHA_B}})
        add(now + timedelta(minutes=21))  # Must not be counted after the selected error.
        db.session.add(WatchdogDeployEvent(event_id='test', status='redeploy_triggered_unconfirmed',
                       started_at=now + timedelta(minutes=30), health_url='https://PRIVATE_SECRET', criado_em=now))
        db.session.commit()
        with patch.object(dev_deploys, 'changed_files', return_value={'disponivel': True, 'arquivos': ['app/modules/upload.py']}):
            context = dev_deploys.context(error.id, {'trechos': [{'arquivo': 'app/modules/upload.py'}]})
        assert context['versao_do_erro'] == SHA_B
        assert context['versoes_observadas'][0]['registro'] == observed.id
        assert context['comparacao']['antes']['ocorrencias_mesmo_status'] == 1
        assert context['comparacao']['antes']['requisicoes_auditadas'] == 2
        assert context['comparacao']['depois']['ocorrencias_mesmo_status'] == 1
        assert context['mudancas_entre_ultimas_observacoes']['arquivos_relacionados_ao_erro'] == ['app/modules/upload.py']
        assert 'PRIVATE_' not in str(context)
        assert context['watchdog'][0]['status'] == 'redeploy_triggered_unconfirmed'


def test_unknown_or_different_version_does_not_invent_commit_or_diff(app):
    with app.app_context():
        now = datetime.now()
        error = add(now)
        db.session.commit()
        context = dev_deploys.context(error.id, {})
        assert context['versao_do_erro'] is None
        assert context['versoes_observadas'] == []
        add(now - timedelta(minutes=1), 0, kind='DEPLOY_OBSERVADO', details={'release_sha': SHA_A})
        error.detalhes = {'diagnostico': {'release_sha': SHA_B}}
        db.session.commit()
        with patch.object(dev_deploys, 'changed_files') as diff:
            context = dev_deploys.context(error.id, {})
        assert 'comparacao' not in context
        assert 'comparacao_indisponivel' in context
        diff.assert_not_called()


def test_git_access_requires_valid_shas_and_existing_repository(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'root_path', str(tmp_path / 'app'))
    with app.app_context(), patch.object(dev_deploys.subprocess, 'run') as command:
        assert not dev_deploys.changed_files('--help', SHA_B)['disponivel']
        assert not dev_deploys.changed_files(SHA_A, SHA_B)['disponivel']
        command.assert_not_called()


def test_deploy_followup_and_utc_normalization():
    history = [{'role': 'user', 'content': 'Analise o erro #7'}]
    assert dev_diagnostics.selected_id('Isso começou depois do deploy?', history) == 7
    assert topics.evaluate('Isso começou depois do deploy?', history).kind == 'allowed'
    assert _parse_iso_datetime('2026-11-17T13:00:00-03:00') == datetime(2026, 11, 17, 16)


def test_git_diff_is_bounded_and_reports_matches(app, tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(app, 'root_path', str(tmp_path / 'app'))
    (tmp_path / '.git').mkdir()
    names = b'\0'.join(f'app/modules/file{i}.py'.encode() for i in range(105)) + b'\0'
    with app.app_context(), patch.object(dev_deploys.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=names)) as command:
        data = dev_deploys.changed_files(SHA_A, SHA_B)
    assert data['disponivel']
    assert data['truncado']
    assert len(data['arquivos']) == 100
    assert command.call_args.kwargs['timeout'] == 3
    assert '--no-ext-diff' in command.call_args.args[0]


def test_repeated_worker_observation_is_idempotent_and_invalid_sha_is_ignored(app):
    from app.modules.auditoria.releases import register_release_observation
    app.config['APP_RELEASE_SHA'] = SHA_A
    register_release_observation(app)
    register_release_observation(app)
    app.add_url_rule('/ok', endpoint='ok', view_func=lambda: 'ok')
    client(app).get('/ok')
    with app.app_context():
        assert AuditoriaUsuario.query.filter_by(tipo_evento='DEPLOY_OBSERVADO').count() == 1
    app.config['APP_RELEASE_SHA'] = 'invalid-token-value'
    client(app).get('/ok')
    with app.app_context():
        assert AuditoriaUsuario.query.filter_by(tipo_evento='DEPLOY_OBSERVADO').count() == 1
