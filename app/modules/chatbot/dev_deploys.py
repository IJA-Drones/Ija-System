"""Correlate observed versions, watchdog events and HTTP occurrences; no causal claims."""
import re
import subprocess
from datetime import timedelta
from pathlib import Path

from flask import current_app
from sqlalchemy import func

from app.models import AuditoriaUsuario, WatchdogDeployEvent
from app.modules.dev_dashboard.service import _serialize_datetime, _format_brazil_datetime


def _sha(value):
    return value if isinstance(value, str) and re.fullmatch(r'[a-f0-9]{40,64}', value) else None


def changed_files(before, after):
    if not _sha(before) or not _sha(after):
        return {'disponivel': False, 'motivo': 'Duas versões válidas são necessárias.'}
    root = Path(current_app.root_path).resolve().parent
    if not (root / '.git').exists():
        return {'disponivel': False, 'motivo': 'Histórico Git não disponível nesta instância.'}
    try:
        result = subprocess.run(['git', '--no-pager', 'diff', '--no-ext-diff', '--name-only', '-z', before, after, '--', 'app/'],
                                cwd=root, capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'disponivel': False, 'motivo': 'Não foi possível consultar o histórico Git local.'}
    if result.returncode:
        return {'disponivel': False, 'motivo': 'Uma das versões não está disponível no Git local.'}
    names = result.stdout.decode('utf-8', errors='replace').split('\0')
    names = [name for name in names if name.startswith('app/') and len(name) <= 250
             and not any(ord(char) < 32 for char in name)]
    return {'disponivel': True, 'arquivos': names[:100], 'truncado': len(names) > 100,
            'base': before, 'versao': after}


def _comparison(error, at):
    # Equal windows around the observation, ending no later than the selected error.
    end = min(at + timedelta(hours=1), error.criado_em + timedelta(microseconds=1))
    base = AuditoriaUsuario.query.filter(AuditoriaUsuario.endpoint == error.endpoint,
                                         AuditoriaUsuario.metodo == error.metodo)
    def sample(start, stop):
        query = base.filter(AuditoriaUsuario.criado_em >= start, AuditoriaUsuario.criado_em < stop)
        return {'inicio': _serialize_datetime(start), 'fim': _serialize_datetime(stop),
                'requisicoes_auditadas': query.filter(AuditoriaUsuario.status_code >= 100).count(),
                'ocorrencias_mesmo_status': query.filter(AuditoriaUsuario.status_code == error.status_code).count()}
    duration = min(timedelta(hours=1), max(timedelta(microseconds=1), end - at))
    return {'antes': sample(at - duration, at), 'depois': sample(at, at + duration),
            'limite': 'Janelas de mesma duração (até 1 hora), mesma rota, método e status. Contagens da auditoria, '
                      'não todo o tráfego. Ausência anterior não prova que o erro começou neste deploy.'}


def context(log_id, code):
    error = AuditoriaUsuario.query.filter_by(id=log_id).one()
    diagnostics = (error.detalhes or {}).get('diagnostico', {}) if isinstance(error.detalhes, dict) else {}
    error_sha = _sha(diagnostics.get('release_sha')) if isinstance(diagnostics, dict) else None
    releases = AuditoriaUsuario.query.filter(
        AuditoriaUsuario.tipo_evento == 'DEPLOY_OBSERVADO', AuditoriaUsuario.criado_em <= error.criado_em,
    ).order_by(AuditoriaUsuario.criado_em.desc(), AuditoriaUsuario.id.desc()).limit(6).all()
    versions = []
    for row in releases:
        sha = _sha((row.detalhes or {}).get('release_sha')) if isinstance(row.detalhes, dict) else None
        if sha:
            versions.append({'registro': row.id, 'sha': sha, 'observado_em': _serialize_datetime(row.criado_em),
                             'horario_brasilia': _format_brazil_datetime(row.criado_em),
                             'corresponde_ao_erro': sha == error_sha if error_sha else None})
    # Watchdog start is a health failure observation, not a successful rollout.
    timestamp = func.coalesce(WatchdogDeployEvent.started_at, WatchdogDeployEvent.criado_em)
    watchdog = WatchdogDeployEvent.query.filter(
        timestamp >= error.criado_em - timedelta(days=7), timestamp <= error.criado_em + timedelta(hours=1),
    ).order_by(timestamp.desc(), WatchdogDeployEvent.id.desc()).limit(5).all()
    events = [{'id': row.id, 'status': row.status if row.status in {'redeploy_triggered', 'redeploy_triggered_unconfirmed'} else 'outro',
               'inicio_monitoramento': _serialize_datetime(row.started_at),
               'recuperacao_servico': _serialize_datetime(row.recovered_at),
               'registrado_em': _serialize_datetime(row.criado_em),
               'falhas_healthcheck': row.failures} for row in watchdog]
    result = {'versao_do_erro': error_sha, 'versoes_observadas': versions, 'watchdog': events,
              'limites': 'Versão observada significa primeira requisição que registrou esse SHA, não horário exato do deploy. '
                         'Um mesmo SHA é registrado uma vez; rollback/restart para ele não gera nova observação. '
                         'Watchdog indica acionamento e recuperação de saúde, não commit publicado nem conclusão do deploy. '
                         'Erros antigos podem não ter versão registrada. Eventos posteriores ao erro não podem causá-lo. '
                         'Correlação temporal e arquivo alterado são pistas, nunca prova de regressão.'}
    applicable = versions and (not error_sha or versions[0]['sha'] == error_sha)
    if applicable:
        boundary = next(row for row in releases if row.id == versions[0]['registro'])
        result['comparacao'] = _comparison(error, boundary.criado_em) if error.endpoint else None
        result['comparacao_sha_observado'] = versions[0]['sha']
    elif versions:
        result['comparacao_indisponivel'] = 'A versão do erro difere da observação mais recente; não inferir rollout ou rollback.'
    if applicable and len(versions) >= 2:
        diff = changed_files(versions[1]['sha'], versions[0]['sha'])
        known = {item['arquivo'] for item in code.get('trechos', [])}
        diff['arquivos_relacionados_ao_erro'] = [name for name in diff.get('arquivos', []) if name in known]
        result['mudancas_entre_ultimas_observacoes'] = diff
    return result


def summary(data):
    if data.get('indisponivel'):
        return data['indisponivel']
    lines = []
    if data.get('versao_do_erro'):
        lines.append('Versão registrada no erro: ' + data['versao_do_erro'][:12] + '.')
    for item in data.get('versoes_observadas', [])[:2]:
        lines.append(f"Versão {item['sha'][:12]} observada em {item['horario_brasilia']} (evento #{item['registro']}).")
    if data.get('watchdog'):
        lines.append(f"{len(data['watchdog'])} evento(s) próximo(s) do watchdog; recuperação não confirma publicação de versão.")
    return '\n'.join(lines) or 'Nenhuma versão ou evento de deploy encontrado no histórico consultado.'
