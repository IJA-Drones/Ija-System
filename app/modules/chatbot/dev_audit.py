"""Minimal, bounded audit context for an already-authorized DEV diagnosis."""
import re
from datetime import timedelta

from app.models import AuditoriaUsuario
from app.modules.auditoria.diagnostics import clean_text
from app.modules.dev_dashboard.service import _serialize_datetime


def _label(value):
    return value if isinstance(value, str) and re.fullmatch(r'[\w.:-]{1,120}', value) else None


def _items(value, limit):
    return value[:limit] if isinstance(value, list) else []


def _exception(value):
    if not isinstance(value, dict):
        return None
    frames = []
    for frame in _items(value.get('frames'), 12):
        if not isinstance(frame, dict):
            continue
        frames.append({'arquivo': clean_text(frame.get('arquivo', ''), 200),
                       'funcao': _label(frame.get('funcao')), 'linha': frame.get('linha') if type(frame.get('linha')) is int else None})
    return {'tipo': _label(value.get('tipo')), 'motivo': value.get('motivo') if value.get('motivo') in {'busy', 'expired', 'stale'} else None,
            'frames': frames}


def _row(row, *, include_diagnostics=False):
    details = row.detalhes if isinstance(row.detalhes, dict) else {}
    data = {'id': row.id, 'data': _serialize_datetime(row.criado_em), 'evento': _label(row.tipo_evento),
            'resultado': _label(row.resultado), 'status': row.status_code, 'endpoint': _label(row.endpoint)}
    identifiers = details.get('identificadores')
    if isinstance(identifiers, dict):
        data['identificadores'] = {key: value for key, value in list(identifiers.items())[:10]
                                   if _label(key) and type(value) is int}
    changes = details.get('campos')
    if isinstance(changes, dict):
        safe_changes = {}
        for key in ('status', 'versao', 'ativo', 'ativa', 'habilitada'):
            change = changes.get(key)
            if isinstance(change, dict):
                safe_changes[key] = {side: value if type(value) in (int, float, bool) or value is None
                                    or (isinstance(value, str) and value in {'PENDENTE', 'APROVADO', 'CANCELADO', 'CONCLUIDA', 'EM_ANDAMENTO', 'FINALIZADO'})
                                    else '[valor omitido]' for side, value in change.items() if side in {'antes', 'depois'}}
        data['alteracoes'] = safe_changes
    diagnostic = details.get('diagnostico')
    if include_diagnostics and isinstance(diagnostic, dict) and diagnostic.get('versao') == 1:
        logs = []
        for item in _items(diagnostic.get('logs'), 10):
            if not isinstance(item, dict):
                continue
            logs.append({'nivel': _label(item.get('nivel')), 'logger': _label(item.get('logger')),
                         'mensagem_modelo': clean_text(item.get('mensagem_modelo', '')),
                         'excecao': _exception(item.get('excecao'))})
        data['diagnostico'] = {'logs': logs, 'logs_truncados': bool(diagnostic.get('logs_truncados')),
                               'excecao': _exception(diagnostic.get('excecao'))}
    return data


def context(log_id):
    row = AuditoriaUsuario.query.filter_by(id=log_id).one()
    same = []
    if row.requisicao_id:
        same = AuditoriaUsuario.query.filter(
            AuditoriaUsuario.requisicao_id == row.requisicao_id, AuditoriaUsuario.id != row.id,
        ).order_by(AuditoriaUsuario.criado_em, AuditoriaUsuario.id).limit(21).all()
    nearby = []
    if row.usuario_id is not None and row.endpoint and row.criado_em:
        nearby = AuditoriaUsuario.query.filter(
            AuditoriaUsuario.usuario_id == row.usuario_id, AuditoriaUsuario.endpoint == row.endpoint,
            AuditoriaUsuario.prefeitura_id == row.prefeitura_id,
            AuditoriaUsuario.path == row.path, AuditoriaUsuario.id != row.id,
            AuditoriaUsuario.criado_em >= row.criado_em - timedelta(minutes=5),
            AuditoriaUsuario.criado_em <= row.criado_em + timedelta(minutes=5),
        ).order_by(AuditoriaUsuario.criado_em.desc(), AuditoriaUsuario.id.desc()).limit(11).all()
    from app.modules.chatbot.dev_timeline import build
    timeline = build(row, same[:20], nearby[:10], request_truncated=len(same) > 20,
                     nearby_truncated=len(nearby) > 10)
    selected = _row(row, include_diagnostics=True)
    return {'linha_do_tempo': timeline, 'registro_selecionado': selected, 'mesma_requisicao': [_row(item) for item in same[:20]],
            'mesma_requisicao_truncada': len(same) > 20,
            'proximos_mesma_rota_e_usuario': [_row(item) for item in nearby[:10]],
            'proximos_truncados': len(nearby) > 10,
            'cobertura': ('Diagnóstico capturado na requisição.' if 'diagnostico' in selected else
                          'Registro histórico sem captura de logs/stack trace. Não é possível reconstruir o log original.'),
            'limites': 'Somente auditoria disponível no banco. Eventos próximos (±5 min) são contexto, não prova de causalidade. '
                       'Não inclui arquivos arquivados, console da hospedagem ou logs de outros processos. '
                       'Mensagens de log são modelos sem argumentos; exceções não incluem valores nem variáveis locais.'}


def summary(data):
    parts = [data.get('cobertura', '')]
    row = data.get('registro_selecionado', {})
    if row:
        parts.append(f"Evento #{row['id']}: {row.get('evento') or '-'} / {row.get('resultado') or '-'}.")
    diagnostic = row.get('diagnostico', {})
    exception = diagnostic.get('excecao')
    if exception:
        parts.append(f"Exceção: {exception.get('tipo')}; motivo: {exception.get('motivo') or 'não informado'}.")
        for frame in exception.get('frames', [])[-3:]:
            parts.append(f"{frame['arquivo']}:{frame['linha']} · {frame['funcao']}")
    for log in diagnostic.get('logs', [])[:3]:
        parts.append(f"{log.get('nivel')}: {log.get('mensagem_modelo')}")
        if log.get('excecao'):
            parts.append(f"Exceção do log: {log['excecao'].get('tipo')}.")
    related = data.get('mesma_requisicao', [])
    if related:
        parts.append('Mesma requisição: ' + ', '.join(f"#{item['id']} ({item.get('evento')})" for item in related[:5]) + '.')
    if data.get('proximos_mesma_rota_e_usuario'):
        parts.append('Há eventos próximos na mesma rota e usuário; proximidade não comprova causa.')
    timeline = data.get('linha_do_tempo', {})
    if timeline.get('eventos'):
        parts.append('Linha do tempo (horário de São Paulo):')
        for item in timeline['eventos'][-8:]:
            parts.append(f"{item['horario_brasilia']} · #{item['id']} · {item['evento']} · HTTP {item['status']} · {item['vinculo']}"
                         + (f" · {item['motivo']}" if item.get('motivo') else ''))
        if timeline.get('truncada') or len(timeline['eventos']) > 8:
            parts.append('Exibição parcial da linha do tempo.')
    return '\n'.join(parts)
