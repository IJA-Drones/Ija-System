"""Chronological audit evidence with explicit request/resource/proximity links."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from app.models import AuditoriaUsuario

# These upload routes use Solicitacao.id as os_id (not OrdemServico.id).
UPLOAD_ENDPOINTS = {
    'main.os_upload_complementary_stream', 'main.os_upload_stream',
    'main.os_upload_video_stream',
}


def resource(row):
    from app.shared.edit_control import PROTECTED
    aliases = {'solicitacao': 'solicitacao', 'solicitacoes': 'solicitacao',
               'denuncia': 'denuncia', 'denuncias': 'denuncia'}
    if row.objeto_tipo in aliases and row.objeto_id and row.objeto_id.isdecimal():
        return aliases[row.objeto_tipo], int(row.objeto_id)
    rule = PROTECTED.get(row.endpoint)
    if row.endpoint in UPLOAD_ENDPOINTS:
        rule = ('solicitacao', 'os_id')
    details = row.detalhes if isinstance(row.detalhes, dict) else {}
    identifiers = details.get('identificadores', {})
    if rule and isinstance(identifiers, dict):
        value = identifiers.get(rule[1])
        if type(value) is int and value > 0:
            return rule[0], value
    return None


def build(selected, same_request, nearby, *, request_truncated=False, nearby_truncated=False):
    from app.modules.chatbot.dev_audit import _row
    from app.shared.edit_control import PROTECTED

    linked = {}
    def add(row, link):
        if row.id not in linked:
            item = _row(row)
            item['vinculo'] = link
            timestamp = row.criado_em.replace(tzinfo=timezone.utc) if row.criado_em.tzinfo is None else row.criado_em
            item['horario_brasilia'] = timestamp.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')
            item['deslocamento_segundos'] = round((row.criado_em - selected.criado_em).total_seconds(), 3)
            diagnostic = row.detalhes.get('diagnostico', {}) if isinstance(row.detalhes, dict) else {}
            exception = diagnostic.get('excecao', {}) if isinstance(diagnostic, dict) else {}
            if isinstance(exception, dict) and exception.get('motivo') in {'expired', 'busy', 'stale'}:
                item['motivo'] = exception['motivo']
            linked[row.id] = item

    add(selected, 'erro_selecionado')
    for row in same_request:
        add(row, 'mesma_requisicao')
    key = resource(selected)
    truncated = False
    if key:
        kind, oid = key
        endpoint_names = [endpoint for endpoint, rule in PROTECTED.items() if rule[0] == kind]
        if kind == 'solicitacao':
            endpoint_names += sorted(UPLOAD_ENDPOINTS)
        aliases = (kind, 'solicitacoes' if kind == 'solicitacao' else 'denuncias')
        candidates = AuditoriaUsuario.query.filter(
            AuditoriaUsuario.prefeitura_id == selected.prefeitura_id,
            AuditoriaUsuario.objeto_id == str(oid),
            or_(AuditoriaUsuario.objeto_tipo.in_(aliases), AuditoriaUsuario.endpoint.in_(endpoint_names)),
            AuditoriaUsuario.criado_em >= selected.criado_em - timedelta(minutes=30),
            AuditoriaUsuario.criado_em <= selected.criado_em + timedelta(minutes=5),
        ).order_by(AuditoriaUsuario.criado_em.desc(), AuditoriaUsuario.id.desc()).limit(41).all()
        truncated = len(candidates) > 40
        for row in candidates[:40]:
            if resource(row) == key:
                add(row, 'mesmo_recurso')
    for row in nearby:
        # When resource IDs exist, do not mix unrelated uploads on a templated URL.
        if row.prefeitura_id == selected.prefeitura_id and (not key or resource(row) == key):
            add(row, 'proximidade_na_rota_e_usuario')
    events = sorted(linked.values(), key=lambda item: (item['data'], item['id']))
    return {'eventos': events, 'recurso': {'tipo': key[0], 'id': key[1]} if key else None,
            'truncada': truncated or request_truncated or nearby_truncated,
            'janela_recurso': '30 minutos antes e 5 minutos depois do erro',
            'criterio': 'Mesma requisição tem vínculo direto. Mesmo recurso exige tipo, ID e prefeitura iguais, '
                        'podendo incluir outro editor. Proximidade temporal não comprova causa. '
                        'Horários são os eventos registrados; resposta HTTP não comprova o início da operação. '
                        'Ausência de evento não comprova ausência de ação. Ordenação por horário e ID em caso de empate.'}
