"""Durable leases + signed form versions. A lease never grants business access."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, abort, current_app, g, has_app_context, has_request_context,
                   jsonify, render_template, request, session, url_for)
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from markupsafe import Markup
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import Conflict, HTTPException

from app.extensions import db
from app.models import EdicaoReserva, Solicitacao, Denuncia, OrdemServico, OrdemServicoEquipeUvis, Usuario

bp = Blueprint('edit_control', __name__)
# Both the request and execution forms reserve the same logical OS.
PROTECTED = {
    'main.editar_solicitacao': ('solicitacao', 'id'),
    'main.atualizar': ('solicitacao', 'id'),
    'main.admin_os_formulario_view': ('solicitacao', 'os_id'),
    'main.piloto_os_formulario_view': ('solicitacao', 'os_id'),
    'main.uvis_os_formulario_view': ('solicitacao', 'os_id'),
    'main.equipe_uvis_os_formulario_view': ('solicitacao', 'os_id'),
    'main.denuncia_encaminhar_coordenadoria': ('denuncia', 'denuncia_id'),
    'main.coordenadoria_denuncia_designar_uvis': ('denuncia', 'denuncia_id'),
    'main.denuncia_arquivar': ('denuncia', 'denuncia_id'),
    'main.uvis_denuncia_detalhe': ('denuncia', 'denuncia_id'),
}
MODELS = (Solicitacao, Denuncia, OrdemServico, OrdemServicoEquipeUvis)
DIRECT_EDIT_ROLES = frozenset({'piloto', 'equipe_oceano', 'equipe_uvis', 'piloto_agro'})


def _direct_editor(user):
    return bool(user and user.is_authenticated and user.tipo_usuario in DIRECT_EDIT_ROLES)


def _direct_request():
    # This exempts reservations only; each route still authorizes access and edits.
    return has_request_context() and _direct_editor(current_user)


class EditConflict(Conflict):
    def __init__(self, message, *, owner=None, expires=None, reason='edit_conflict'):
        super().__init__(description=message)
        self.owner, self.expires, self.reason = owner, expires, reason


def enabled():
    return has_app_context() and 'edit_control' in current_app.extensions


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='ija-edit-form-v1')


def _key(obj):
    if isinstance(obj, Solicitacao):
        return 'solicitacao', obj.id
    if isinstance(obj, Denuncia):
        return 'denuncia', obj.id
    if isinstance(obj, (OrdemServico, OrdemServicoEquipeUvis)):
        return 'solicitacao', obj.solicitacao_id


def _versions(kind, oid):
    """Read columns directly, bypassing the ORM identity cache after row locking."""
    conn = db.session.connection()
    models = (Denuncia,) if kind == 'denuncia' else (Solicitacao, OrdemServico, OrdemServicoEquipeUvis)
    values = []
    for model in models:
        column = model.id if model in (Solicitacao, Denuncia) else model.solicitacao_id
        version = conn.execute(select(model.versao_edicao).where(column == oid)).scalar_one_or_none()
        values.append(version or 0)
    if not values[0]:
        abort(404)
    return values


def _ticket(obj, endpoint):
    kind, oid = _key(obj)
    # Versions must describe the objects actually used to render the form.
    versions = [obj.versao_edicao]
    if kind == 'solicitacao':
        versions += [getattr(obj.ordem_servico, 'versao_edicao', 0),
                     getattr(obj.ordem_servico_equipe_uvis, 'versao_edicao', 0)]
    session.setdefault('_edit_session', secrets.token_urlsafe(24))
    return _serializer().dumps(dict(kind=kind, id=oid, endpoint=endpoint, versions=versions,
                                    user=current_user.id, session=session['_edit_session']))


def _decode(ticket):
    try:
        data = _serializer().loads(ticket, max_age=86400)
    except (BadSignature, TypeError):
        raise EditConflict('Esta página expirou. Recarregue antes de iniciar a edição.', reason='stale')
    if (not current_user.is_authenticated or data.get('user') != current_user.id
            or not session.get('_edit_session') or data.get('session') != session['_edit_session']):
        abort(403)
    if data.get('endpoint') not in PROTECTED or data.get('kind') != PROTECTED[data['endpoint']][0]:
        abort(403)
    return data


def _authorize(data):
    """Recheck current role, tenant, team, owner and state on every lease operation."""
    from app.modules.gestao_ti.permissions import can_access_endpoint
    from app.modules.solicitacoes.service import build_editar_solicitacao_context, SolicitacaoAccessError
    from app.modules.piloto_os.service import (build_admin_os_form_context, build_piloto_os_form_context,
                                              is_piloto_os_user, PilotoOsError)
    from app.modules.equipe_uvis_dashboard.service import build_equipe_uvis_os_unificado_context, EquipeUvisDashboardError
    from app.modules.denuncias.service import get_denuncia_scoped_or_404, can_triage_denuncias
    from app.modules.dashboard.service import build_uvis_os_form_context, DashboardError
    from app.shared.access import is_regional_user
    endpoint, oid = data['endpoint'], data['id']
    if not can_access_endpoint(current_user, endpoint, 'POST'):
        abort(403)
    try:
        if endpoint == 'main.editar_solicitacao':
            return build_editar_solicitacao_context(current_user, oid)['pedido']
        if endpoint == 'main.atualizar':
            from app.modules.admin_dashboard.routes import _get_scoped_solicitacao_or_404
            from app.modules.admin_dashboard.service import can_edit_admin_panel
            if not can_edit_admin_panel(current_user):
                abort(403)
            return _get_scoped_solicitacao_or_404(oid)
        if endpoint in {'main.admin_os_formulario_view', 'main.piloto_os_formulario_view'}:
            if endpoint == 'main.piloto_os_formulario_view' and not is_piloto_os_user(current_user):
                abort(403)
            builder = build_admin_os_form_context if endpoint == 'main.admin_os_formulario_view' else build_piloto_os_form_context
            context = builder(current_user, oid)
            if context['modo_visualizacao']:
                abort(403)
            return context['solicitacao']
        if endpoint == 'main.uvis_os_formulario_view':
            context = build_uvis_os_form_context(current_user, oid)
            if not context['can_edit_uvis_tab']:
                abort(403)
            return context['solicitacao']
        if endpoint == 'main.equipe_uvis_os_formulario_view':
            if current_user.tipo_usuario not in {'uvis', 'equipe_uvis'}:
                abort(403)
            context = build_equipe_uvis_os_unificado_context(current_user, oid)
            if not context['can_edit_uvis_tab']:
                abort(403)
            return context['solicitacao']
        obj = get_denuncia_scoped_or_404(oid, current_user)
        if obj.solicitacao_id or obj.status in {Denuncia.STATUS_ARQUIVADA, Denuncia.STATUS_CONVERTIDA_SOLICITACAO}:
            raise EditConflict('Esta denúncia já foi encerrada. Recarregue para consultar o resultado.', reason='stale')
        legacy = (is_regional_user(current_user) if endpoint == 'main.coordenadoria_denuncia_designar_uvis'
                  else current_user.tipo_usuario == 'uvis' if endpoint == 'main.uvis_denuncia_detalhe'
                  else can_triage_denuncias(current_user))
        if not can_access_endpoint(current_user, endpoint, 'POST', legacy=legacy):
            abort(403)
        return obj
    except (SolicitacaoAccessError, PilotoOsError, EquipeUvisDashboardError, DashboardError):
        abort(403)


def _locked_state(kind, oid, conn=None):
    conn = conn or db.session.connection()
    table = EdicaoReserva.__table__
    if conn.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif conn.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError('Controle de edição requer PostgreSQL ou SQLite.')
    conn.execute(insert(table).values(tipo=kind, objeto_id=oid, geracao=0).on_conflict_do_nothing(
        index_elements=['tipo', 'objeto_id']))
    where = (table.c.tipo == kind) & (table.c.objeto_id == oid)
    # UPDATE acquires a write lock in SQLite too. Never commit apart from the business write.
    conn.execute(table.update().where(where).values(geracao=table.c.geracao))
    return conn.execute(select(table).where(where)).mappings().one()


def _update(kind, oid, **values):
    table = EdicaoReserva.__table__
    db.session.connection().execute(table.update().where(table.c.tipo == kind, table.c.objeto_id == oid).values(**values))


def _active(row):
    return row['token_hash'] and row['expira_em'] and row['expira_em'] > now()


def _owned(row, token):
    return (has_request_context() and current_user.is_authenticated and row['usuario_id'] == current_user.id
            and bool(token) and secrets.compare_digest(row['token_hash'] or '', _digest(token)))


def _busy(row):
    raise EditConflict(f"{row['usuario_nome'] or 'Outro usuário'} está editando este registro. "
                       'Você pode consultar os dados. Aguarde a liberação para alterar.',
                       owner=row['usuario_nome'], expires=row['expira_em'].isoformat()+'Z', reason='busy')


def _same_version(data):
    if data['versions'] != _versions(data['kind'], data['id']):
        raise EditConflict('Este registro mudou depois que você abriu a página. Suas alterações não foram salvas. '
                           'Copie o que precisar e recarregue para revisar a versão atual.', reason='stale')


def _audit(kind, data, details=None):
    from app.modules.auditoria.recorder import enabled as audit_enabled, event_values
    from app.models import AuditoriaUsuario
    if not audit_enabled():
        return
    row = event_values(kind, 'CONFIRMADO', objeto_tipo=data['kind'], objeto_id=str(data['id']), detalhes=details or {})
    model = Solicitacao if data['kind'] == 'solicitacao' else Denuncia
    row['prefeitura_id'] = db.session.connection().execute(select(model.prefeitura_id).where(model.id == data['id'])).scalar()
    db.session.connection().execute(AuditoriaUsuario.__table__.insert().values(**row))


def _clear(data, event_name='EDICAO_LIBERADA', details=None):
    _update(data['kind'], data['id'], token_hash=None, expira_em=None, usuario_id=None, usuario_nome=None)
    _audit(event_name, data, details)


@bp.post('/api/edicao/<action>')
@login_required
def lease(action):
    if action not in {'reservar', 'renovar', 'liberar', 'liberar-dev'}:
        abort(404)
    payload = request.get_json(silent=True) if request.is_json else request.form
    if not hasattr(payload, 'get'):
        abort(400)
    if any(not isinstance(payload.get(field, ''), str) for field in ('ticket', 'token', 'motivo')):
        abort(400)
    if len(payload.get('ticket', '')) > 4096 or len(payload.get('token', '')) > 256:
        abort(400)
    if _direct_request():
        if action == 'liberar-dev':
            abort(403)
        # Older open pages still send lease heartbeats after the role exemption.
        # This is a no-op: do not decode obsolete tickets, inspect a record or
        # change anyone's reservation. Business routes retain their own guards.
        # Token/expiry keep already-loaded legacy JS usable until a page refresh;
        # neither value authorizes access or extends the authenticated session.
        return jsonify(ok=True, required=False, token='direct-edit',
                       expires=(now()+timedelta(days=1)).isoformat()+'Z')
    data = _decode(payload.get('ticket', ''))
    _authorize(data)
    row = _locked_state(data['kind'], data['id'])
    token = payload.get('token', '')
    if action == 'liberar-dev':
        if current_user.tipo_usuario != 'dev':
            abort(403)
        reason = (payload.get('motivo') or '').strip()
        if len(reason) < 10 or len(reason) > 300:
            return jsonify(error='Informe um motivo entre 10 e 300 caracteres.'), 400
        _clear(data, 'EDICAO_LIBERADA_DEV', {'motivo': reason, 'editor_anterior_id': row['usuario_id']})
        # Invalidate any in-flight ticket/token. A former editor can never save with this lease.
        _update(data['kind'], data['id'], geracao=row['geracao'] + 1)
        db.session.commit()
        return jsonify(ok=True, message='Reserva liberada. Recarregue antes de editar.')
    if action == 'liberar':
        if not _owned(row, token):
            raise EditConflict('Esta reserva já foi encerrada ou pertence a outra aba.', reason='expired')
        _clear(data)
        db.session.commit()
        return jsonify(ok=True)
    if action == 'renovar':
        if not _active(row) or not _owned(row, token):
            raise EditConflict('Sua reserva expirou ou foi liberada. Copie suas alterações e recarregue a página.', reason='expired')
    else:
        _same_version(data)
        if _active(row):
            _busy(row)  # Even the same user in another tab must wait.
        token = secrets.token_urlsafe(32)
        _update(data['kind'], data['id'], usuario_id=current_user.id,
                usuario_nome=current_user.nome_uvis, token_hash=_digest(token), iniciado_em=now(), geracao=row['geracao']+1)
        _audit('EDICAO_RESERVADA', data)
    expiry = now() + timedelta(seconds=current_app.config['EDIT_LEASE_SECONDS'])
    _update(data['kind'], data['id'], expira_em=expiry)
    db.session.commit()
    return jsonify(ok=True, token=token, expires=expiry.isoformat()+'Z', owner=current_user.nome_uvis)


def _require_form():
    if request.method != 'POST' or request.endpoint not in PROTECTED or not current_user.is_authenticated or _direct_request():
        return
    kind, param = PROTECTED[request.endpoint]
    # Authorize before inspecting reservation metadata or accepting a form ticket.
    expected = dict(kind=kind, id=request.view_args[param], endpoint=request.endpoint)
    _authorize(expected)
    data = _decode(request.form.get('_edit_ticket', ''))
    if any(data.get(key) != expected[key] for key in expected):
        abort(403)
    row = _locked_state(kind, expected['id'])
    token = request.form.get('_edit_token', '')
    if not _active(row) or not _owned(row, token):
        if _active(row):
            _busy(row)
        raise EditConflict('Inicie a edição para reservar este registro. Se a reserva expirou, '
                           'copie suas alterações e recarregue a página.', reason='expired')
    _same_version(data)
    g.edit_finish = data


def _key_from_request():
    if not has_request_context():
        return None
    ticket = request.headers.get('X-Edit-Ticket') or request.form.get('_edit_ticket')
    if not ticket:
        return None
    data = _decode(ticket)
    return data['kind'], data['id']


def _before_flush(orm_session, *_):
    if not enabled() or _direct_request():
        return
    keys = set()
    background = orm_session.info.get('_edit_background_media') if not has_request_context() else None
    for obj in list(orm_session.dirty) + list(orm_session.deleted) + list(orm_session.new):
        if not isinstance(obj, MODELS) or (obj in orm_session.new and isinstance(obj, (Solicitacao, Denuncia))):
            continue
        if obj in orm_session.dirty and not orm_session.is_modified(obj, include_collections=False):
            continue
        key = _key(obj)
        if background:
            changed = {prop.key for prop in inspect(obj).mapper.column_attrs if inspect(obj).attrs[prop.key].history.has_changes()}
            if not isinstance(obj, OrdemServico) or obj in orm_session.new or changed - {'video', 'quantidade_videos_registradas'}:
                raise EditConflict('O processamento de vídeo tentou alterar campos fora da mídia.')
        if key and key[1]:
            keys.add(key)
    for kind, oid in sorted(keys):
        if (background and orm_session.info.get('_edit_background_direct')
                and kind == 'solicitacao' and oid == background.get('os_id')):
            continue
        row = _locked_state(kind, oid, orm_session.connection())
        token = (request.headers.get('X-Edit-Token') or request.form.get('_edit_token', '')) if has_request_context() else ''
        if _active(row):
            worker_owned = (background and kind == 'solicitacao' and oid == background.get('os_id')
                            and row['usuario_id'] == background.get('user_id')
                            and row['token_hash'] == background.get('edit_token_hash'))
            if not _owned(row, token) and not worker_owned:
                _busy(row)
        elif token and _key_from_request() == (kind, oid):
            raise EditConflict('Sua reserva expirou durante a operação. Recarregue antes de salvar novamente.', reason='expired')


def check_available(kind, oid):
    if not enabled() or _direct_request():
        return
    row = _locked_state(kind, oid)
    token = request.headers.get('X-Edit-Token') or request.form.get('_edit_token', '')
    if _active(row) and not _owned(row, token):
        _busy(row)
    if token and (not _active(row) or not _owned(row, token)):
        raise EditConflict('Sua reserva expirou. Recarregue antes de alterar os arquivos.', reason='expired')


def media_job_credentials():
    if not enabled() or not has_request_context() or _direct_request():
        return {}
    token = request.headers.get('X-Edit-Token', '')
    if not token:
        return {}
    key = _key_from_request()
    if not key:
        return {}
    row = _locked_state(*key)
    if not _active(row) or not _owned(row, token):
        raise EditConflict('A reserva do envio foi encerrada. Recarregue antes de enviar novamente.', reason='expired')
    return {'edit_token_hash': _digest(token), 'edit_generation': row['geracao']}


def prepare_background_media(job):
    if not enabled():
        return
    db.session.info.pop('_edit_background_direct', None)
    # Resolve the persisted account, including jobs queued before the exemption.
    # Keep the worker restricted to this OS's video fields in _before_flush.
    user = db.session.get(Usuario, job.get('user_id')) if job.get('user_id') else None
    if _direct_editor(user):
        db.session.info['_edit_background_media'] = job
        db.session.info['_edit_background_direct'] = True
        return
    row = _locked_state('solicitacao', job['os_id'])
    if job.get('edit_generation') is not None and job['edit_generation'] != row['geracao']:
        raise EditConflict('A reserva deste envio foi substituída. Envie novamente após revisar a OS.', reason='expired')
    if _active(row) and not (row['usuario_id'] == job.get('user_id') and row['token_hash'] == job.get('edit_token_hash')):
        _busy(row)
    db.session.info['_edit_background_media'] = job
    return _versions('solicitacao', job['os_id'])


def background_media_versions(oid):
    return _versions('solicitacao', oid) if enabled() else None


def publish_media_transition(job):
    """Advance only the initiating tab's exact pre-video snapshot, never a stale business form."""
    if enabled() and job.get('status') == 'success' and job.get('edit_versions_before'):
        g.edit_media_transition = job


def _before_commit(orm_session):
    if not enabled() or not has_request_context() or not getattr(g, 'edit_finish', None):
        return
    # Flush business changes first. Failed validation/flush rolls the release back too.
    orm_session.flush()
    data = g.edit_finish
    _clear(data, details={'motivo': 'salvamento'})
    g.edit_pending_finish = data


def _after_commit(orm_session):
    if enabled() and has_request_context() and getattr(g, 'edit_pending_finish', None):
        g.edit_saved = g.pop('edit_pending_finish')
        g.pop('edit_finish', None)


def _after_rollback(orm_session):
    if enabled() and has_request_context():
        g.pop('edit_pending_finish', None)
        g.pop('edit_finish', None)


event.listen(Session, 'before_flush', _before_flush)
event.listen(Session, 'before_commit', _before_commit)
event.listen(Session, 'after_commit', _after_commit)
event.listen(Session, 'after_rollback', _after_rollback)


def edit_fields(obj, endpoint):
    if endpoint not in PROTECTED or not current_user.is_authenticated or _direct_request():
        return ''
    return Markup(render_template('_edit_control.html', ticket=_ticket(obj, endpoint),
        edit_key=f'{_key(obj)[0]}:{obj.id}', edit_api=url_for('edit_control.lease', action='reservar').rsplit('/',1)[0],
        edit_dev=current_user.tipo_usuario == 'dev'))


def register_edit_control(app):
    if 'edit_control' in app.extensions:
        return
    seconds = int(app.config.get('EDIT_LEASE_SECONDS', 300))
    if not 60 <= seconds <= 1800:
        raise ValueError('EDIT_LEASE_SECONDS deve estar entre 60 e 1800.')
    app.config['EDIT_LEASE_SECONDS'] = seconds
    app.extensions['edit_control'] = True
    app.register_blueprint(bp)
    app.before_request(_require_form)
    app.context_processor(lambda: {'edit_fields': edit_fields, 'edit_control_enabled': True})

    @app.errorhandler(EditConflict)
    @app.errorhandler(StaleDataError)
    def edit_conflict(error):
        db.session.rollback()
        message = error.description if isinstance(error, EditConflict) else 'Este registro foi alterado por outra operação. Nada foi sobrescrito. Recarregue para revisar.'
        from app.modules.auditoria.recorder import mark_outcome
        mark_outcome('CONFLITO_EDICAO', 'NEGADO')
        if request.is_json or '/api/' in request.path or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(ok=False, error=message, code=getattr(error, 'reason', 'stale'),
                           owner=getattr(error, 'owner', None), expires=getattr(error, 'expires', None)), 409
        return render_template('edicao_conflito.html', message=message), 409

    @app.after_request
    def response_versions(response):
        response.headers['Cache-Control'] = 'no-store' if current_user.is_authenticated else response.headers.get('Cache-Control', 'no-cache')
        # Refresh only after this tab's own successful save/media mutation, not on arbitrary polls.
        if not _direct_request() and response.status_code < 400 and request.blueprint != 'edit_control' and (request.method in {'POST', 'PUT', 'DELETE'} or getattr(g, 'edit_media_transition', None)):
            ticket = request.headers.get('X-Edit-Ticket') or request.form.get('_edit_ticket')
            token = request.headers.get('X-Edit-Token') or request.form.get('_edit_token')
            if ticket and token:
                try:
                    data = _decode(ticket)
                    row = db.session.get(EdicaoReserva, (data['kind'], data['id']))
                    owned = row and row.usuario_id == current_user.id and row.token_hash == _digest(token)
                    transition = getattr(g, 'edit_media_transition', None)
                    allowed_transition = not transition or (
                        transition.get('os_id') == data['id'] and transition.get('user_id') == current_user.id
                        and transition.get('edit_token_hash') == _digest(token)
                        and data['versions'] == transition.get('edit_versions_before')
                        and _versions(data['kind'], data['id']) == transition.get('edit_versions_after'))
                    saved = getattr(g, 'edit_saved', None)
                    saved_here = saved and all(saved[key] == data[key] for key in ('kind', 'id', 'endpoint'))
                    if allowed_transition and (owned or saved_here):
                        data['versions'] = _versions(data['kind'], data['id'])
                        response.headers['X-Edit-Ticket'] = _serializer().dumps(data)
                        response.headers['X-Edit-Versions'] = ','.join(map(str, data['versions']))
                        if saved_here:
                            response.headers['X-Edit-Released'] = '1'
                except (HTTPException, BadSignature):
                    pass
        return response
