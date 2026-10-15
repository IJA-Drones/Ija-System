"""Request evidence plus transactional ORM changes. Never store request bodies."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from flask import current_app, g, has_app_context, has_request_context, request
from flask_login import current_user
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import AuditoriaUsuario


INTERNAL_TABLES = {
    'auditoria_usuarios', 'auditoria_arquivos', 'auditoria_instalacao',
    'login_bloqueios', 'login_eventos', 'usuario_presencas', 'watchdog_deploy_events',
    'rastreamento_sincronizacao', 'rastreamento_posicoes', 'rastreamento_historicos',
}
# Field names are recorded for other columns, but their contents are not copied.
# No generic serialization of free text, URLs, files, JSON, tokens or passwords.
VISIBLE_FIELDS = {
    'status', 'tipo_usuario', 'regiao', 'ativa', 'ativo', 'quantidade', 'tipo_evento',
    'validade_dias', 'versao', 'perfil_codigo', 'codigo', 'tipo_visita', 'foco',
    'data_agendamento', 'hora_agendamento', 'data_aplicacao', 'categoria',
    'gerada_automaticamente', 'uvis_visualizado', 'trabalha_agro',
    'trabalha_oceano_azul', 'suporte_operacional', 'suporte_tecnico',
    'habilitada', 'opacidade', 'tamanho_percentual', 'incluir_usuario',
}
LOGIN_ENDPOINTS = {'auth.login', 'auth.login_piloto_agro', 'auth.login_uvis_operacional'}
QUIET_ENDPOINTS = {'static', 'healthz', 'healthz_full'}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enabled():
    return has_app_context() and 'audit_trail' in current_app.extensions


def actor_snapshot(user=None):
    if user is None:
        user = current_user if has_request_context() else None
    from app.shared.access import get_user_prefeitura_id
    if user is None or not getattr(user, 'is_authenticated', False):
        return dict(usuario_id=None, usuario_nome='Não autenticado' if has_request_context() else 'Sistema',
                    usuario_login=None, tipo_usuario=None, prefeitura_usuario_id=None)
    return dict(usuario_id=user.id, usuario_nome=(user.nome_uvis or user.login or 'Usuário')[:100],
                usuario_login=(user.login or '')[:50], tipo_usuario=(user.tipo_usuario or '')[:20],
                prefeitura_usuario_id=get_user_prefeitura_id(user))


def event_values(kind, result, *, actor=None, **extra):
    if actor is None:
        actor = getattr(g, 'audit_actor', None) if has_request_context() else None
    actor = dict(actor or actor_snapshot())
    if has_request_context():
        from app.shared.login_protection import client_ip
        # Route templates avoid copying tokens/PII embedded in arbitrary URL paths.
        path = request.url_rule.rule if request.url_rule else '/rota-nao-encontrada'
        context = dict(metodo=request.method, endpoint=request.endpoint, path=path[:255],
                       ip=client_ip(), requisicao_id=getattr(g, 'audit_request_id', None))
    else:
        context = dict(metodo='SYSTEM', endpoint=None, path='/processo-interno', ip=None, requisicao_id=None)
    return dict(actor, **context, evento_id=str(uuid4()), criado_em=utcnow(), tipo_evento=kind,
                resultado=result, prefeitura_id=actor.get('prefeitura_usuario_id'), status_code=0,
                **extra)


def mark_outcome(kind, result, user=None):
    """Annotate semantic outcomes that cannot be inferred from an HTTP redirect."""
    if enabled() and has_request_context():
        g.audit_outcome = (kind, result)
        if user is not None:
            g.audit_actor = actor_snapshot(user)


def _visible(key):
    return key in VISIBLE_FIELDS or key == 'id' or key.endswith('_id')


def _value(key, value):
    if not _visible(key):
        return '[conteúdo protegido]'
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:160]


def _municipality(obj, actor):
    if hasattr(obj, 'prefeitura_id'):
        return obj.prefeitura_id
    if obj.__tablename__ == 'prefeituras':
        return obj.id
    for relation in ('solicitacao', 'equipe', 'veiculo', 'drone', 'topico', 'uvis_usuario'):
        parent = getattr(obj, relation, None)
        if parent is not None and hasattr(parent, 'prefeitura_id'):
            return parent.prefeitura_id
    return actor.get('prefeitura_usuario_id')


def _before_flush(session, flush_context, instances):
    if not enabled():
        return
    pending = []
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        table = getattr(obj, '__tablename__', '')
        if not table or table in INTERNAL_TABLES:
            continue
        state = inspect(obj)
        kind = 'CRIACAO' if obj in session.new else 'EXCLUSAO' if obj in session.deleted else 'EDICAO'
        relationship_keys = {
            state.mapper.get_property_by_column(column).key
            for relationship in state.mapper.relationships
            if relationship.direction.name == 'MANYTOONE' and state.attrs[relationship.key].history.has_changes()
            for column in relationship.local_columns
        }
        changes = {}
        for prop in state.mapper.column_attrs:
            key = prop.key
            history = state.attrs[key].history
            if kind == 'EDICAO' and not history.has_changes() and key not in relationship_keys:
                continue
            old = None
            if kind != 'CRIACAO':
                if history.deleted:
                    old = history.deleted[0]
                elif history.unchanged:
                    old = history.unchanged[0]
                elif _visible(key) and state.identity:
                    column = prop.columns[0]
                    old = session.connection().execute(select(column).select_from(state.mapper.persist_selectable).where(
                        *[col == value for col, value in zip(state.mapper.primary_key, state.identity)]
                    )).scalar_one_or_none()
            new = None if kind == 'EXCLUSAO' else getattr(obj, key)
            changes[key] = {'antes': None if kind == 'CRIACAO' else _value(key, old),
                            'depois': None if kind == 'EXCLUSAO' else _value(key, new)}
        if not changes:
            continue
        row = event_values(kind, 'CONFIRMADO', objeto_tipo=table, detalhes={'campos': changes})
        row['prefeitura_id'] = _municipality(obj, row)
        pending.append((obj, row))
    session.info['_audit_pending'] = pending


def _after_flush(session, flush_context):
    for obj, row in session.info.pop('_audit_pending', []):
        state = inspect(obj)
        identity = [getattr(obj, col.key, None) for col in state.mapper.primary_key]
        row['objeto_id'] = ':'.join(str(value) for value in identity)[:100]
        if row['tipo_evento'] != 'EXCLUSAO':
            for key, change in row['detalhes']['campos'].items():
                change['depois'] = _value(key, getattr(obj, key))
            row['prefeitura_id'] = _municipality(obj, row)
        # Same connection/transaction: a failed business commit rolls this back too.
        session.connection().execute(AuditoriaUsuario.__table__.insert().values(**row))


def _after_rollback(session):
    session.info.pop('_audit_pending', None)


def _bulk_write(state):
    """Track ORM bulk DML without pretending to have individual before/after values."""
    if not enabled() or not (state.is_update or state.is_delete or state.is_insert):
        return
    table = getattr(state.statement, 'table', None)
    if table is None or table.name in INTERNAL_TABLES:
        return
    row = event_values('ALTERACAO_LOTE', 'CONFIRMADO', objeto_tipo=table.name,
                       detalhes={'operacao': 'exclusao' if state.is_delete else 'edicao' if state.is_update else 'criacao',
                                 'observacao': 'Operação em lote; valores individuais não capturados.'})
    result = state.invoke_statement()
    row['detalhes']['quantidade'] = getattr(result, 'rowcount', None)
    state.session.connection().execute(AuditoriaUsuario.__table__.insert().values(**row))
    return result


event.listen(Session, 'before_flush', _before_flush)
event.listen(Session, 'after_flush', _after_flush)
event.listen(Session, 'after_rollback', _after_rollback)
event.listen(Session, 'do_orm_execute', _bulk_write, retval=True)


def register_audit(app):
    if 'audit_trail' in app.extensions:
        return
    app.extensions['audit_trail'] = True

    @app.before_request
    def capture_identity():
        g.audit_request_id = str(uuid4())
        g.audit_actor = actor_snapshot()

    @app.after_request
    def record_response(response):
        endpoint = request.endpoint or ''
        is_login = endpoint in LOGIN_ENDPOINTS and request.method == 'POST'
        actor = getattr(g, 'audit_actor', None) or actor_snapshot()
        authenticated = actor.get('usuario_id') is not None
        denied = response.status_code in (401, 403, 429)
        # Polling/presence and static assets are not sensitive consultations.
        if endpoint in QUIET_ENDPOINTS or endpoint.startswith('session_security.'):
            if not getattr(g, 'audit_outcome', None):
                return response
        elif not (authenticated or is_login or denied or request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}):
            return response

        kind, result = getattr(g, 'audit_outcome', (None, None))
        if kind is None:
            if is_login:
                actor = actor_snapshot()
                if not actor['usuario_id']:
                    actor['usuario_login'] = (request.form.get('login') or '')[:50]
                kind = 'LOGIN'
                result = 'BLOQUEADO' if response.status_code == 429 else 'SUCESSO' if actor['usuario_id'] else 'FALHA'
            elif endpoint == 'auth.logout':
                kind, result = 'LOGOUT', 'SUCESSO'
            elif denied:
                kind, result = 'ACESSO_NEGADO', 'NEGADO'
            else:
                download = 'attachment' in response.headers.get('Content-Disposition', '').lower()
                export = any(word in endpoint.lower() for word in ('export', 'download', 'pdf', 'excel'))
                kind = 'EXPORTACAO' if download or export else 'CONSULTA' if request.method == 'GET' else 'REQUISICAO'
                result = 'FALHA' if response.status_code >= 400 else 'RESPONDIDA'
        row = event_values(kind, result, actor=actor)
        row['status_code'] = response.status_code
        # Only numeric route identifiers, never arbitrary query strings/form data.
        identifiers = {key: value for key, value in (request.view_args or {}).items() if isinstance(value, int)}
        row['detalhes'] = {'identificadores': identifiers}
        if identifiers:
            row['objeto_id'] = str(next(iter(identifiers.values())))
        row['objeto_tipo'] = (endpoint or 'requisicao')[:100]
        try:
            # Release read transactions before opening the independent audit write.
            # No implicit business commit: unfinished work remains uncommitted.
            db.session.rollback()
            with db.engine.begin() as conn:
                conn.execute(AuditoriaUsuario.__table__.insert().values(**row))
        except Exception:
            app.logger.exception('Não foi possível persistir o evento de auditoria da requisição.')
            response.headers['X-Audit-Status'] = 'unavailable'
        return response

    from app.modules.auditoria.archive import register_archive_worker
    register_archive_worker(app)
