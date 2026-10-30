"""User-bound export previews; the model never receives report rows or runs SQL."""
import hashlib
import json
import sqlite3
from functools import wraps
from datetime import date

from flask import abort, current_app, jsonify, request, send_file, url_for
from flask_login import current_user, login_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.modules.consultas import service, exporters
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.modules.relatorios.service import can_access_relatorios_menu

COLUMNS = {
    'solicitacoes': ['id', 'data', 'cidade', 'bairro', 'categoria', 'status', 'foco'],
    'ordens_servico': ['id', 'os', 'data_execucao', 'cidade', 'bairro', 'situacao_os', 'imagens'],
}
SOURCE_ENDPOINT = {'solicitacoes': 'main.exportar_excel', 'ordens_servico': 'main.relatorios_os_export_pdf'}
PARAMETERS = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'source': {'type': 'string', 'enum': list(COLUMNS)},
        'format': {'type': 'string', 'enum': ['excel', 'pdf']},
        'inicio': {'type': 'string', 'description': 'Data inicial ISO YYYY-MM-DD ou vazio para todo o período.'},
        'fim': {'type': 'string', 'description': 'Data final ISO YYYY-MM-DD ou vazio para todo o período.'},
        'status': {'type': 'string', 'description': 'Status exato da solicitação, em maiúsculas, ou vazio. Não é status da OS.'},
        'bairro': {'type': 'string', 'description': 'Bairro exato pedido pelo usuário ou vazio.'},
    },
    'required': ['source', 'format', 'inicio', 'fim', 'status', 'bairro'],
}


def allowed_sources(user):
    if getattr(user, 'tipo_usuario', '') not in {'dev', 'diretor'}:
        return []
    legacy = can_access_relatorios_menu(user)
    if not can_access_endpoint(user, 'main.consultas_exportar', 'POST', legacy=legacy):
        return []
    return [source for source, endpoint in SOURCE_ENDPOINT.items()
            if can_access_endpoint(user, endpoint, 'GET', legacy=legacy)]


def export_tool(user):
    sources = allowed_sources(user)
    if not sources:
        return []
    schema = {**PARAMETERS, 'properties': {**PARAMETERS['properties'],
                                         'source': {'type': 'string', 'enum': sources}}}
    return [{'type': 'function', 'name': 'preparar_exportacao', 'strict': True,
             'description': 'Prepara uma prévia para confirmação humana. Não gera nem envia o arquivo. Somente solicitações e OS MUNICIPAIS, nunca Agro. Datas de solicitações filtram agendamento; datas de OS filtram aplicação. Não use se o pedido exigir outros filtros não suportados ou se for só uma pergunta sobre como exportar. Solicite esclarecimento quando necessário.',
             'parameters': schema}]


def plan_spec(plan):
    if (not isinstance(plan, dict) or set(plan) != set(PARAMETERS['required'])
            or any(not isinstance(value, str) for value in plan.values())
            or plan['source'] not in COLUMNS or plan['format'] not in {'excel', 'pdf'}
            or any(len(plan[key]) > 100 for key in ('inicio', 'fim', 'status', 'bairro'))):
        raise service.QueryError('Não foi possível interpretar os filtros. Informe o tipo de relatório, formato e período.')
    filters = {key: plan[key] for key in ('inicio', 'fim', 'status', 'bairro') if plan[key]}
    # Validate dates and interval using the existing query contract first.
    spec = service.validate({'source': plan['source'], 'columns': COLUMNS[plan['source']], 'filters': filters})
    if plan['source'] == 'ordens_servico':
        for key, op in (('inicio', 'gte'), ('fim', 'lte')):
            value = spec['filters'].pop(key, '')
            if value:
                spec['conditions'].append({'field': 'data_execucao', 'op': op, 'value': value})
    return spec


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='azul-export-preview-v1')


def fingerprint(result):
    data = {'rows': result['rows'], 'columns': result['columns'],
            'cities': sorted(result['prefeitura_ids'], key=str)}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepare(user, plan):
    spec = plan_spec(plan)
    if plan['source'] not in allowed_sources(user):
        abort(403)
    result = service.execute(user, spec)
    if plan['format'] == 'pdf' and result['total'] > 2000:
        raise service.QueryError('O PDF aceita até 2.000 registros. Restrinja o período ou peça Excel.')
    if not result['total']:
        raise service.QueryError('Nenhum registro encontrado com esses filtros. Ajuste o período ou os filtros.')
    token = serializer().dumps({'user': user.id, 'plan': plan, 'digest': fingerprint(result)})
    start = date.fromisoformat(plan['inicio']).strftime('%d/%m/%Y') if plan['inicio'] else 'Sem início'
    end = date.fromisoformat(plan['fim']).strftime('%d/%m/%Y') if plan['fim'] else 'Sem fim'
    period = f'{start} até {end}' if plan['inicio'] or plan['fim'] else 'Todo o período'
    return {'token': token, 'url': url_for('main.azul_export_download'),
            'title': service.SOURCES[plan['source']] + ' municipais',
            'format': plan['format'], 'total': result['total'],
            'filters': {'Período': period,
                        'Data utilizada': 'Agendamento' if plan['source'] == 'solicitacoes' else 'Aplicação da OS',
                        'Status da solicitação': plan['status'] or 'Todos', 'Bairro': plan['bairro'] or 'Todos'},
            'columns': [column['label'] for column in result['columns']],
            'notice': 'Somente registros acessíveis ao seu usuário. Confirmação válida por 10 minutos. Se os dados mudarem, peça uma nova prévia.'}


def protected(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if not allowed_sources(current_user):
            abort(403)
        try:
            return fn(*args, **kwargs)
        except service.QueryError as exc:
            return jsonify(error=str(exc)), 400
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.warning('Azul: consulta de exportação indisponível')
            return jsonify(error='Não foi possível consultar os dados. Tente novamente.'), 503
    return wrapped


def register_routes(bp):
    @bp.post('/api/azul/exportar', endpoint='azul_export_download')
    @protected
    def download():
        if not request.is_json:
            return jsonify(error='Envie a confirmação em JSON.'), 415
        raw = request.stream.read(8001)
        if len(raw) > 8000:
            return jsonify(error='Confirmação muito longa.'), 413
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            data = None
        if not isinstance(data, dict) or data.get('confirm') is not True or not isinstance(data.get('token'), str):
            return jsonify(error='Confira a prévia e confirme a geração.'), 400
        try:
            preview = serializer().loads(data['token'], max_age=600)
        except (BadSignature, SignatureExpired):
            return jsonify(error='A prévia expirou ou é inválida. Peça uma nova.'), 400
        if preview['user'] != current_user.id:
            abort(403)
        plan = preview['plan']
        if plan['source'] not in allowed_sources(current_user):
            abort(403)
        # A valid confirmation must not allow unlimited expensive regeneration.
        from app.modules.chatbot.azul import consume_help_quota
        try:
            available = consume_help_quota(current_user.id, export=True)
        except sqlite3.Error:
            return jsonify(error='Não foi possível validar o limite de exportações. Tente novamente.'), 503
        if not available:
            return jsonify(error='Limite de exportações atingido (3 por minuto e 50 por dia). Tente mais tarde.'), 429
        result = service.execute(current_user, plan_spec(plan))
        if fingerprint(result) != preview['digest']:
            return jsonify(error='Os dados ou seu acesso mudaram. Peça uma nova prévia antes de baixar.'), 409
        if plan['format'] == 'excel':
            stream = exporters.excel(result)
            extension, mimetype = 'xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            from app.modules.consultas.routes import build_pdf
            stream = build_pdf(result)
            extension, mimetype = 'pdf', 'application/pdf'
        response = send_file(stream, as_attachment=True, download_name=f"azul-{plan['source']}.{extension}", mimetype=mimetype)
        response.headers['Cache-Control'] = 'private, no-store'
        return response
