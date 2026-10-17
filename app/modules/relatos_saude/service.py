"""Citizen health reports reuse municipal identity and notifications, not focus/OS records."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import hmac
import uuid

from sqlalchemy.orm import selectinload
from flask import abort, current_app
from app.extensions import db
from app.models import RelatoSaude, RelatoSaudeEvento, Prefeitura, Usuario, Notificacao
from app.modules.gestao_ti.permissions import has_permission
from app.shared.access import is_admin_global_user, is_covisa_user, is_prefeitura_admin_user
from app.modules.portal_cidadao.service import _digits, _format_phone

STATUS = {'RECEBIDO': 'Recebido pela COVISA', 'EM_ANALISE': 'Em análise pela COVISA',
          'ENCAMINHADO_UVIS': 'Encaminhado à UVIS', 'EM_ATENDIMENTO': 'Em atendimento pela UVIS',
          'CONCLUIDO': 'Concluído'}

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def manager(user):
    return is_admin_global_user(user) or is_covisa_user(user) or is_prefeitura_admin_user(user)

def allowed(user, action='consultar'):
    eligible = bool(getattr(user, 'is_authenticated', False)) and (manager(user) or user.tipo_usuario == 'uvis')
    return eligible and has_permission(user, 'prefeitura.relatos_saude.' + action, legacy=True)

def scope(user):
    query = RelatoSaude.query.options(selectinload(RelatoSaude.prefeitura), selectinload(RelatoSaude.uvis))
    if not allowed(user):
        return query.filter(db.false())
    if not is_admin_global_user(user):
        tenant = getattr(user, 'prefeitura_id', None)
        if tenant is None:
            return query.filter(db.false())
        query = query.filter(RelatoSaude.prefeitura_id == tenant)
    if not manager(user):
        query = query.filter(RelatoSaude.uvis_usuario_id == user.id)
    return query

def units(prefeitura_id):
    return Usuario.query.filter_by(prefeitura_id=prefeitura_id, tipo_usuario='uvis').order_by(Usuario.nome_uvis).all()

def _event(row, action, user=None, note=None):
    db.session.add(RelatoSaudeEvento(relato=row, acao=action, status=row.status,
        usuario_id=user.id if user else None, responsavel=user.nome_uvis if user else 'Cidadão',
        uvis_usuario_id=row.uvis_usuario_id, observacao=note))

def _notify(row, recipients):
    for uid in set(recipients):
        db.session.add(Notificacao(usuario_id=uid, titulo='Relato de saúde para atendimento',
            mensagem='Há um relato na sua caixa de atendimento. Acesse para registrar ciência e dar continuidade.',
            link=f'/relatos-saude/{row.id}'))

def _notify_management(row):
    people = Usuario.query.filter(Usuario.prefeitura_id == row.prefeitura_id).all()
    ids = [u.id for u in people if is_covisa_user(u) or is_prefeitura_admin_user(u)]
    # A report must not disappear if municipal accounts have not been configured yet.
    if not ids:
        ids = [u.id for u in Usuario.query.filter(Usuario.tipo_usuario.in_(['dev','diretor','admin'])).all()]
    _notify(row, ids)

def create_report(form, submission_id, origin_key):
    existing = RelatoSaude.query.filter_by(envio_id=submission_id).first()
    if existing:
        return existing
    errors = {}
    fields = {'nome':150, 'telefone':30, 'logradouro':150, 'numero':20,
              'bairro':100, 'descricao':2000}
    data = {k:(form.get(k) or '').strip() for k in fields}
    labels = {'nome':'Nome', 'telefone':'Telefone', 'logradouro':'Logradouro', 'numero':'Número', 'bairro':'Bairro', 'descricao':'Descrição'}
    for key, limit in fields.items():
        if not data[key] or len(data[key]) > limit:
            errors[key] = f'{labels[key]}: preencha com até {limit} caracteres.'
    if len(_digits(data['telefone'])) not in (10,11):
        errors['telefone'] = 'Informe um telefone com DDD (10 ou 11 dígitos).'
    try:
        pid = int(form.get('prefeitura_id', ''))
    except (ValueError, TypeError):
        pid = None
    prefeitura = db.session.get(Prefeitura, pid) if pid else None
    if not prefeitura or not prefeitura.ativa:
        errors['prefeitura_id'] = 'Selecione a prefeitura onde você mora.'
    onset = None
    if form.get('inicio_sintomas'):
        try:
            onset = date.fromisoformat(form['inicio_sintomas'])
            if onset > datetime.now(ZoneInfo('America/Sao_Paulo')).date() or onset.year < 1900:
                raise ValueError()
        except ValueError:
            errors['inicio_sintomas'] = 'Informe uma data válida, que não esteja no futuro.'
    if form.get('consentimento') != '1':
        errors['consentimento'] = 'Confirme que leu como os dados serão usados.'
    if form.get('website'):
        errors['formulario'] = 'Não foi possível enviar. Recarregue a página.'
    if errors:
        return errors
    fingerprint = hmac.new(str(current_app.secret_key).encode(), origin_key.encode(), hashlib.sha256).hexdigest()
    count = RelatoSaude.query.filter(RelatoSaude.origem_hash == fingerprint,
        RelatoSaude.criado_em >= now()-timedelta(hours=1)).count()
    if count >= current_app.config.get('RELATOS_SAUDE_MAX_HORA', 10):
        abort(429, description='Muitos relatos enviados nesta sessão. Tente novamente mais tarde.')
    row = RelatoSaude(prefeitura_id=pid, protocolo='SAU-' + uuid.uuid4().hex[:16].upper(),
        envio_id=submission_id, origem_hash=fingerprint, cidadao_nome=data['nome'],
        cidadao_telefone=_format_phone(_digits(data['telefone'])), logradouro=data['logradouro'],
        numero=data['numero'], bairro=data['bairro'], descricao=data['descricao'],
        inicio_sintomas=onset, consentimento=True, status='RECEBIDO')
    db.session.add(row)
    db.session.flush()
    _event(row, 'REGISTRADO')
    _notify_management(row)
    return row

def transition(row, user, form):
    if not allowed(user, 'atender'):
        abort(403)
    if row.status == 'CONCLUIDO':
        raise ValueError('Este relato já foi concluído. O histórico permanece disponível.')
    action = form.get('acao')
    note = (form.get('observacao') or '').strip()
    if len(note) > 2000:
        raise ValueError('Use até 2.000 caracteres na observação.')
    if action == 'ciencia':
        expected = 'RECEBIDO' if manager(user) and row.uvis_usuario_id is None else 'ENCAMINHADO_UVIS'
        if row.status != expected:
            raise ValueError('A ciência desta etapa já foi registrada.')
        if row.uvis_usuario_id is not None and user.id != row.uvis_usuario_id:
            raise ValueError('A ciência da UVIS deve ser registrada pela unidade responsável.')
        row.status = 'EM_ANALISE' if row.uvis_usuario_id is None else 'EM_ATENDIMENTO'
    elif action == 'encaminhar':
        if not manager(user):
            abort(403)
        if row.status == 'RECEBIDO':
            raise ValueError('Registre a ciência antes de encaminhar à UVIS.')
        try:
            uid = int(form.get('uvis_usuario_id', ''))
        except (TypeError, ValueError):
            raise ValueError('Selecione a UVIS responsável.')
        unit = Usuario.query.filter_by(id=uid, prefeitura_id=row.prefeitura_id, tipo_usuario='uvis').first()
        if unit is None:
            raise ValueError('Selecione uma UVIS desta prefeitura.')
        if row.uvis_usuario_id == uid:
            raise ValueError('Este relato já está com essa UVIS.')
        if not note:
            raise ValueError('Informe o motivo do encaminhamento.')
        row.uvis_usuario_id = uid
        row.status = 'ENCAMINHADO_UVIS'
        _notify(row, [uid])
    elif action == 'devolver':
        if user.tipo_usuario != 'uvis' or row.uvis_usuario_id != user.id:
            abort(403)
        if not note:
            raise ValueError('Informe o motivo da devolução à COVISA.')
        row.uvis_usuario_id = None
        row.status = 'EM_ANALISE'
        _notify_management(row)
    elif action in {'acompanhamento', 'concluir'}:
        if not note:
            raise ValueError('Descreva o encaminhamento ou resultado do atendimento.')
        if action == 'concluir':
            if row.status not in {'EM_ANALISE', 'EM_ATENDIMENTO'}:
                raise ValueError('Registre a ciência antes de concluir o atendimento.')
            row.status = 'CONCLUIDO'
            row.concluido_em = now()
    else:
        raise ValueError('Ação inválida.')
    row.atualizado_em = now()
    _event(row, action.upper(), user, note or None)


def filtered(user, args):
    """One query supplies screen, totals and PDF; period uses local receipt date."""
    query = scope(user)
    if args.get('status'):
        if args['status'] not in STATUS:
            abort(400, description='Situação inválida.')
        query = query.filter(RelatoSaude.status == args['status'])
    dates = {}
    for key in ('inicio', 'fim'):
        if args.get(key):
            try:
                dates[key] = date.fromisoformat(args[key])
            except ValueError:
                abort(400, description='Período inválido.')
    if len(dates) == 2 and dates['inicio'] > dates['fim']:
        abort(400, description='A data inicial deve ser anterior ou igual à final.')
    for key, value in dates.items():
        if key == 'fim':
            if value == date.max:
                abort(400, description='Data final inválida.')
            value += timedelta(days=1)
        dt = datetime.combine(value, datetime.min.time(), tzinfo=ZoneInfo('America/Sao_Paulo')).astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(RelatoSaude.criado_em >= dt) if key == 'inicio' else query.filter(RelatoSaude.criado_em < dt)
    if args.get('prefeitura_id'):
        try:
            pid = int(args['prefeitura_id'])
        except ValueError:
            abort(400, description='Prefeitura inválida.')
        query = query.filter(RelatoSaude.prefeitura_id == pid)
    return query
