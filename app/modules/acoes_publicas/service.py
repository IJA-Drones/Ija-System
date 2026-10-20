"""Transições versionadas; somente o retrato aprovado pode ser público."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import abort, current_app, g
from flask_login import current_user
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Prefeitura
from app.modules.gestao_ti.permissions import has_permission
from app.shared.access import is_admin_global_user, is_covisa_user, is_prefeitura_admin_user, can_access_prefeitura
from .models import AcaoPublica, AcaoPublicaEvento, now

TYPES = {'inspecao': 'Inspeção', 'focal': 'Tratamento focal', 'orientacao': 'Orientação e prevenção',
         'monitoramento': 'Monitoramento', 'mutirao': 'Mutirão', 'outra': 'Outra ação de vigilância'}
STATUS = {'RASCUNHO': 'Rascunho', 'EM_REVISAO': 'Em revisão', 'PUBLICADO': 'Publicado', 'RETIRADO': 'Retirado'}
FIELDS = ('titulo', 'tipo', 'bairro', 'inicio', 'fim', 'descricao')


class ActionError(ValueError):
    pass


def ready():
    if not current_app.config.get('ACOES_PUBLICAS_ENABLED', False) or 'sqlalchemy' not in current_app.extensions:
        return False
    if 'acoes_schema_ready' not in g:
        try:
            names = set(inspect(db.session.connection()).get_table_names())
            g.acoes_schema_ready = {'acoes_publicas', 'acoes_publicas_midias', 'acoes_publicas_eventos'} <= names
        except SQLAlchemyError:
            db.session.rollback()
            g.acoes_schema_ready = False
    return g.acoes_schema_ready


def allowed(action='consultar'):
    user = current_user
    if not user.is_authenticated or getattr(user, 'tipo_usuario', '') in {'agente_endemias', 'gestor_ti'}:
        return False
    legacy = is_admin_global_user(user) or is_covisa_user(user) or is_prefeitura_admin_user(user)
    if not is_admin_global_user(user) and not getattr(user, 'prefeitura_id', None):
        return False
    return has_permission(user, f'prefeitura.acoes_publicas.{action}', legacy=legacy)


def guard(action='consultar'):
    if not allowed(action):
        abort(403)
    if not ready():
        abort(503, description='Ações realizadas ainda não disponíveis. Confira a migração deste módulo.')


def city(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', value):
        raise ActionError('Selecione uma prefeitura cadastrada.')
    row = db.session.get(Prefeitura, int(value))
    if row is None or not row.ativa:
        raise ActionError('Selecione uma prefeitura ativa.')
    if not can_access_prefeitura(current_user, row.id):
        abort(403)
    return row


def scoped_action(identifier):
    row = db.session.get(AcaoPublica, identifier)
    if row is None or not can_access_prefeitura(current_user, row.prefeitura_id):
        abort(404)
    return row


def version(row, value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) != row.versao:
        abort(409, description='Outra pessoa alterou esta ação. Recarregue a página antes de continuar.')


def text(value, label, maximum, required=False):
    value = str(value or '').strip()
    if (required and not value) or len(value) > maximum or any((ord(c) < 32 and c not in '\n\t') or ord(c) == 127 for c in value):
        raise ActionError(f'Confira {label}: limite de {maximum} caracteres.')
    return value


def validate(form):
    result = {key: text(form.get(key), label, maximum, required) for key, label, maximum, required in [
        ('titulo', 'o título', 160, True), ('bairro', 'o bairro ou área', 120, False), ('descricao', 'a descrição pública', 5000, False)]}
    result['tipo'] = form.get('tipo', '')
    if result['tipo'] not in TYPES:
        raise ActionError('Selecione o tipo da ação.')
    try:
        for key in ('inicio', 'fim'):
            value = form.get(key, '')
            result[key] = date.fromisoformat(value)
            if result[key].isoformat() != value:
                raise ValueError()
        if result['fim'] < result['inicio'] or result['fim'] > today():
            raise ValueError()
    except (TypeError, ValueError):
        raise ActionError('Informe o período de uma ação já realizada, com a data final igual ou posterior à inicial.') from None
    return result


def today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def snapshot(row):
    return {**{key: (getattr(row, key).isoformat() if key in ('inicio', 'fim') else getattr(row, key)) for key in FIELDS},
            'demo': row.demo, 'midias': [{'id': item.id, 'mime': item.mime, 'legenda': item.legenda}
                for item in row.midias if item.selecionada]}


def event(row, kind):
    db.session.flush()
    db.session.add(AcaoPublicaEvento(acao_id=row.id, prefeitura_id=row.prefeitura_id, usuario_id=current_user.id,
        usuario_nome=(current_user.nome_uvis or current_user.login)[:150], evento=kind, versao=row.versao,
        conteudo={'rascunho': snapshot(row), 'publicado': row.publicado, 'publicacao': row.publicacao}))


def create(form, identifier, source=None):
    values = validate(form)
    municipality = city(form.get('prefeitura_id', ''))
    mode = form.get('demo')
    if mode not in {'true', 'false'}:
        raise ActionError('Selecione demonstração ou conteúdo autorizado.')
    if source and (source.prefeitura_id != municipality.id or mode == 'true'):
        raise ActionError('A referência da OS exige a mesma prefeitura e a opção de conteúdo autorizado.')
    existing = db.session.get(AcaoPublica, identifier)
    if existing:
        if existing.criado_por_id != current_user.id or existing.prefeitura_id != municipality.id:
            abort(409)
        return existing
    row = AcaoPublica(id=identifier, prefeitura_id=municipality.id, demo=mode == 'true',
        origem_os_id=source.id if source else None, criado_por_id=current_user.id, **values)
    db.session.add(row)
    db.session.flush()
    event(row, 'CRIADA')
    db.session.commit()
    return row


def edit(row, form):
    version(row, form.get('versao'))
    values = validate(form)
    if row.status == 'EM_REVISAO':
        raise ActionError('Devolva a ação ao rascunho antes de editar.')
    for key, value in values.items():
        setattr(row, key, value)
    row.status, row.atualizado_em = 'RASCUNHO', now()
    event(row, 'EDITADA')
    db.session.commit()


def transition(row, form, kind):
    version(row, form.get('versao'))
    if kind == 'revisar':
        if row.status != 'RASCUNHO' or not row.descricao.strip():
            raise ActionError('Complete a descrição pública e salve o rascunho antes de enviar para revisão.')
        row.status = 'EM_REVISAO'
    elif kind == 'rascunho':
        if row.status not in {'EM_REVISAO', 'RETIRADO'}:
            raise ActionError('Esta ação não precisa ser devolvida ao rascunho.')
        row.status = 'RASCUNHO'
    elif kind == 'publicar':
        if row.status != 'EM_REVISAO' or form.getlist('autorizado') != ['sim']:
            raise ActionError('Confira a prévia e confirme a autorização do texto e de todas as mídias antes de publicar.')
        city(str(row.prefeitura_id))
        validate({**snapshot(row)})
        row.publicacao, row.publicado, row.publicado_em = snapshot(row), True, now()
        row.status = 'PUBLICADO'
    elif kind == 'retirar':
        if not row.publicado or form.get('confirmar') != 'sim':
            raise ActionError('Confirme a retirada desta publicação.')
        row.publicado, row.status = False, 'RETIRADO'
    else:
        raise ActionError('Ação inválida.')
    row.atualizado_em = now()
    event(row, {'revisar':'ENVIADA_REVISAO','rascunho':'DEVOLVIDA','publicar':'PUBLICADA','retirar':'RETIRADA'}[kind])
    db.session.commit()


def public_action(identifier):
    if not ready():
        abort(503)
    row = AcaoPublica.query.join(Prefeitura).filter(AcaoPublica.id == identifier,
        AcaoPublica.publicado.is_(True), Prefeitura.ativa.is_(True)).first()
    if row is None or not row.publicacao:
        abort(404)
    return row


def public_content(row):
    # Never serialize the model, its source OS, users, storage paths or history.
    approved = row.publicacao
    return {key: approved.get(key, '') for key in (*FIELDS, 'demo', 'midias')}
