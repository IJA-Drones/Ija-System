"""Allowlisted reporting definitions. No arbitrary SQL or Python execution."""
import ast
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
import math
import time

from sqlalchemy import Float, cast, func, literal, not_, or_, text

from app.extensions import db
from app.models import Solicitacao, OrdemServico, Usuario
from app.shared.access import apply_solicitacao_prefeitura_scope, apply_solicitacao_regiao_scope
from app.shared.pdf_watermark import solicitacao_prefeitura_expr

# A source changes the included records, never the user's permission scope.
SOURCES = {'solicitacoes': 'Solicitações', 'ordens_servico': 'Ordens de serviço'}
FIELDS = {
    'id': ('Solicitação', Solicitacao.id, 'number'),
    'data': ('Data agendada', Solicitacao.data_agendamento, 'date'),
    'bairro': ('Bairro', Solicitacao.bairro, 'text'),
    'categoria': ('Categoria / tipo de visita', Solicitacao.tipo_visita, 'text'),
    'status': ('Status da solicitação', Solicitacao.status, 'text'),
    'foco': ('Foco', Solicitacao.foco, 'text'),
    'operacao': ('Tipo de operação', Solicitacao.tipo_operacao, 'text'),
    'cidade': ('Cidade', Solicitacao.cidade, 'text'),
    'logradouro': ('Logradouro', Solicitacao.logradouro, 'text'),
    'os': ('Identificador da OS', OrdemServico.identificador_os, 'text'),
    'data_execucao': ('Data da aplicação', OrdemServico.data_aplicacao, 'date'),
    'situacao_os': ('Situação da aplicação', OrdemServico.situacao_aplicacao, 'text'),
    'imagens': ('Quantidade de imagens', OrdemServico.quantidade_imagens_registradas, 'number'),
    'videos': ('Quantidade de vídeos', OrdemServico.quantidade_videos_registradas, 'number'),
    'produto_ml': ('Produto administrado (ml)', OrdemServico.quantidade_produto_administrada_ml, 'number'),
    'temperatura': ('Temperatura (°C)', OrdemServico.temperatura_c, 'number'),
    'umidade': ('Umidade (%)', OrdemServico.umidade_relativa_pct, 'number'),
    'registros': ('Registros', literal(1), 'number'),
}
MAX_ROWS = 10000
FORMATS = {'padrao', 'inteiro', 'decimal', 'percentual'}


class QueryError(ValueError):
    pass


def catalog():
    return {'sources': SOURCES, 'fields': [{'id': key, 'label': v[0], 'type': v[2]} for key, v in FIELDS.items()],
            'max_rows': MAX_ROWS}


def formula(expression):
    if not isinstance(expression, str) or len(expression) > 200:
        raise QueryError('A fórmula deve ter até 200 caracteres.')
    try:
        tree = ast.parse(expression, mode='eval')
    except (SyntaxError, ValueError, RecursionError):
        raise QueryError('Fórmula inválida. Use campos numéricos, números, parênteses e + - * /.') from None
    if len(list(ast.walk(tree))) > 40:
        raise QueryError('Simplifique a fórmula.')
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Name) and node.id in FIELDS and FIELDS[node.id][2] == 'number':
            return cast(FIELDS[node.id][1], Float)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and math.isfinite(node.value) and abs(node.value) <= 1e9:
            return literal(float(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) if isinstance(node.op, ast.UAdd) else -visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / func.nullif(right, 0)
        raise QueryError('Fórmula não permitida. Use somente campos numéricos e + - * /.')
    return visit(tree)


def validate(payload):
    if not isinstance(payload, dict): raise QueryError('Consulta inválida.')
    source = payload.get('source', 'solicitacoes')
    if not isinstance(source, str) or source not in SOURCES: raise QueryError('Base de consulta inválida.')
    columns = payload.get('columns', [])
    if not isinstance(columns, list) or not 1 <= len(columns) <= 12 or any(not isinstance(k, str) or k not in FIELDS for k in columns) or len(set(columns)) != len(columns):
        raise QueryError('Selecione de 1 a 12 campos distintos.')
    formulas = payload.get('formulas', [])
    if not isinstance(formulas, list) or len(formulas) > 3: raise QueryError('Use até três fórmulas.')
    clean_formulas = []
    for item in formulas:
        if not isinstance(item, dict): raise QueryError('Fórmula inválida.')
        label = str(item.get('label', '')).strip()
        if not label or len(label) > 60: raise QueryError('Nome da fórmula: de 1 a 60 caracteres.')
        formula(item.get('expression'))
        clean_formulas.append({'label': label, 'expression': item['expression']})
    formats = payload.get('formats', {})
    if not isinstance(formats, dict) or any(k not in columns + [f'formula_{i}' for i in range(len(formulas))] or not isinstance(v, str) or v not in FORMATS for k, v in formats.items()):
        raise QueryError('Formatação inválida.')
    group = payload.get('group', '')
    if group and (group not in columns or FIELDS[group][2] != 'text'): raise QueryError('Escolha um campo textual exibido para a quebra.')
    conditions, exclusions = payload.get('conditions', []), payload.get('exclusions', [])
    for rules in (conditions, exclusions):
        if not isinstance(rules, list) or len(rules) > 10: raise QueryError('Use até dez condições e dez exceções.')
        for rule in rules: condition(rule)
    filters = payload.get('filters', {})
    if not isinstance(filters, dict) or set(filters) - {'prefeitura', 'bairro', 'categoria', 'status', 'inicio', 'fim'}: raise QueryError('Filtros inválidos.')
    for key, value in filters.items():
        if not isinstance(value, str) or len(value) > 100: raise QueryError('Valor de filtro inválido.')
        if key == 'prefeitura' and value and (not value.isascii() or not value.isdecimal() or len(value) > 10 or int(value) < 1):
            raise QueryError('Prefeitura inválida.')
        if key in {'inicio', 'fim'} and value:
            try: date.fromisoformat(value)
            except ValueError: raise QueryError('Informe datas válidas.') from None
    if filters.get('inicio') and filters.get('fim') and filters['inicio'] > filters['fim']: raise QueryError('A data inicial deve ser anterior à final.')
    return dict(source=source, columns=columns, formulas=clean_formulas, formats=formats,
                group=group, conditions=conditions, exclusions=exclusions, filters=filters)


def condition(rule):
    if not isinstance(rule, dict) or not isinstance(rule.get('field'), str) or rule.get('field') not in FIELDS:
        raise QueryError('Campo de condição inválido.')
    _, col, kind = FIELDS[rule['field']]
    op, value = rule.get('op'), rule.get('value')
    if op == 'empty': return or_(col.is_(None), col == '') if kind == 'text' else col.is_(None)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool) or len(str(value)) > 120: raise QueryError('Valor de condição inválido.')
    try:
        if kind == 'number':
            value = float(value)
            if not math.isfinite(value) or abs(value) > 1e12: raise ValueError()
        elif kind == 'date': value = date.fromisoformat(str(value))
        else: value = str(value)
    except (ValueError, OverflowError): raise QueryError('Valor incompatível com o campo selecionado.') from None
    if op == 'eq': return col == value
    if op == 'ne': return or_(col.is_(None), col != value)
    if op == 'contains' and kind == 'text': return col.contains(value, autoescape=True)
    if op == 'gte' and kind in {'date', 'number'}: return col >= value
    if op == 'lte' and kind in {'date', 'number'}: return col <= value
    raise QueryError('Operador incompatível com o campo.')


def base_query(user, source):
    query = db.session.query(Solicitacao).outerjoin(OrdemServico, OrdemServico.solicitacao_id == Solicitacao.id)
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = apply_solicitacao_regiao_scope(query, user)
    if user.tipo_usuario == 'uvis': query = query.filter(Solicitacao.usuario_id == user.id)
    if source == 'ordens_servico': query = query.filter(OrdemServico.id.isnot(None))
    return query


def facets(user):
    query = base_query(user, 'solicitacoes')
    return {key: [value for (value,) in query.with_entities(FIELDS[key][1]).filter(
            FIELDS[key][1].isnot(None), FIELDS[key][1] != '').distinct().order_by(FIELDS[key][1]).limit(1000).all()]
            for key in ('bairro', 'categoria', 'status')}


def format_value(value, kind='padrao'):
    if value is None: return 'Não informado'
    if isinstance(value, (date, datetime)): return value.strftime('%d/%m/%Y')
    if isinstance(value, (float, Decimal)) and not math.isfinite(value): return 'Não informado'
    if isinstance(value, (int, float, Decimal)):
        if kind == 'percentual': return f'{value * 100:.2f}%'.replace('.', ',')
        if kind == 'inteiro': return f'{value:.0f}'
        if kind == 'decimal': return f'{value:.2f}'.replace('.', ',')
    return str(value)


def execute(user, payload):
    started = time.monotonic()
    spec = validate(payload)
    query = base_query(user, spec['source'])
    if spec['filters'].get('prefeitura'):
        query = query.filter(solicitacao_prefeitura_expr() == int(spec['filters']['prefeitura']))
    for key in ('bairro', 'categoria', 'status'):
        if spec['filters'].get(key): query = query.filter(FIELDS[key][1] == spec['filters'][key])
    if spec['filters'].get('inicio'): query = query.filter(Solicitacao.data_agendamento >= date.fromisoformat(spec['filters']['inicio']))
    if spec['filters'].get('fim'): query = query.filter(Solicitacao.data_agendamento <= date.fromisoformat(spec['filters']['fim']))
    for rule in spec['conditions']: query = query.filter(condition(rule))
    for rule in spec['exclusions']:
        # NULL is not a match for an exclusion and must not silently drop a row.
        query = query.filter(not_(func.coalesce(condition(rule), False)))
    columns = [{'id': k, 'label': FIELDS[k][0], 'type': FIELDS[k][2]} for k in spec['columns']]
    expressions = [FIELDS[k][1].label(k) for k in spec['columns']]
    for i, item in enumerate(spec['formulas']):
        key = f'formula_{i}'
        columns.append({'id': key, 'label': item['label'], 'type': 'number'})
        expressions.append(formula(item['expression']).label(key))
    expressions += [Solicitacao.latitude.label('_latitude'), Solicitacao.longitude.label('_longitude'),
                    solicitacao_prefeitura_expr().label('_prefeitura'), Solicitacao.bairro.label('_bairro'),
                    Solicitacao.status.label('_status'), Solicitacao.id.label('_id')]
    order = [FIELDS[spec['group']][1]] if spec['group'] else []
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL statement_timeout = '15s'"))
    records = query.with_entities(*expressions).order_by(*order, Solicitacao.id).limit(MAX_ROWS + 1).all()
    if len(records) > MAX_ROWS: raise QueryError(f'A consulta excede {MAX_ROWS:,} registros. Restrinja o período ou os filtros; nenhum resultado foi cortado.'.replace(',', '.'))
    rows, points, groups, cities, chart = [], [], {}, set(), Counter()
    for record in records:
        data = record._asdict(); cities.add(data['_prefeitura'])
        row = [format_value(data[c['id']], spec['formats'].get(c['id'], 'padrao')) for c in columns]
        rows.append(row)
        group_label = format_value(data.get(spec['group'])) if spec['group'] else 'Resultado'
        group = groups.setdefault(group_label, {'label': group_label, 'count': 0, 'totals': {}, 'start': len(rows) - 1})
        group['count'] += 1
        for col in columns:
            value = data[col['id']]
            if col['type'] == 'number' and col['id'] != 'id' and value is not None and math.isfinite(value):
                group['totals'][col['id']] = group['totals'].get(col['id'], 0) + float(value)
        chart[format_value(data['_status'])] += 1
        try:
            lat, lng = float(data['_latitude']), float(data['_longitude'])
            if math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180:
                points.append({'lat': lat, 'lng': lng, 'id': data['_id'], 'bairro': data['_bairro'] or 'Não informado'})
        except (TypeError, ValueError): pass
    return dict(spec=spec, columns=columns, rows=rows, total=len(rows), groups=list(groups.values()), points=points,
        unmapped=len(rows)-len(points), chart=dict(chart), prefeitura_ids=list(cities),
        generated_at=datetime.now(timezone.utc).isoformat(), duration_ms=round((time.monotonic()-started)*1000))
