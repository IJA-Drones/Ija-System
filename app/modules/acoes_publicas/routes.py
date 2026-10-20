"""Editor municipal autenticado; páginas e mídias públicas com revisão vigente."""
import io
import json
import secrets
from datetime import date, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from uuid import uuid4

from flask import Response, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException
from werkzeug.wsgi import LimitedStream

from app.extensions import db
from app.models import Prefeitura
from app.shared.access import is_admin_global_user
from app.modules.gestao_ti.permissions import has_permission
from . import service as s, media
from .models import AcaoPublica, AcaoPublicaEvento, AcaoPublicaMidia


class BodyLimit:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if environ.get('REQUEST_METHOD') == 'POST' and path.startswith('/acoes-realizadas'):
            limit = media.MAX_FILE + 65536 if path.endswith('/midias') else 65536
            try:
                length = int(environ.get('CONTENT_LENGTH') or 0)
            except ValueError:
                length = -1
            if length < 0 or length > limit:
                return Response('Conteúdo maior que o permitido.', status=413,
                    headers={'Cache-Control':'private, no-store'})(environ, start_response)
            environ['wsgi.input'] = LimitedStream(environ['wsgi.input'], limit, is_max=True)
        return self.app(environ, start_response)


def csrf():
    value = session.get('_acoes_csrf')
    if not isinstance(value, str) or not value:
        value = session['_acoes_csrf'] = secrets.token_urlsafe(32)
    return value


def post_guard():
    token = request.form.get('acao_csrf', '')
    if not secrets.compare_digest(csrf().encode(), token.encode()):
        abort(403, description='Recarregue a página antes de continuar.')
    if any(len(request.form.getlist(key)) != 1 for key in request.form):
        abort(400, description='Informe um único valor por campo.')


def mode():
    value = request.args.get('demo', 'false')
    if value not in {'true','false'}:
        abort(400)
    return value == 'true'


def page_number():
    raw = request.args.get('pagina', '1')
    if not raw.isascii() or not raw.isdecimal() or not 1 <= int(raw) <= 1000:
        abort(400)
    return int(raw)


def source_os(value):
    if not value:
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        abort(400)
    if not has_permission(current_user, 'prefeitura.os.consultar', legacy=True):
        abort(403)
    from app.shared.retorno_ciclo import get_accessible_solicitacao_for_retorno_ciclo
    source = get_accessible_solicitacao_for_retorno_ciclo(current_user, int(value))
    if source is None or source.status != 'CONCLUIDO' or not source.ordem_servico or source.prefeitura_id is None:
        abort(404, description='Selecione uma OS concluída e disponível para a sua conta.')
    return source


def source_media(source):
    if not source:
        return []
    order = source.ordem_servico
    items = []
    if order.imagem_principal:
        items.append(('principal','Imagem principal',order.imagem_principal))
    try:
        extra = json.loads(order.outras_imagens or '[]')
        if isinstance(extra, list):
            items += [(f'complementar-{i}',f'Imagem complementar {i+1}',path) for i,path in enumerate(extra[:30]) if isinstance(path,str) and path]
    except (ValueError, TypeError):
        pass
    if order.video:
        items.append(('video','Vídeo',order.video))
    return items


def private_editor(row, error=None, status=200):
    source = None
    if row.origem_os_id and s.allowed('editar'):
        try:
            source = source_os(str(row.origem_os_id))
        except HTTPException:
            # A reopened/deleted/inaccessible OS must not prevent withdrawing its publication.
            pass
    history = AcaoPublicaEvento.query.filter_by(acao_id=row.id).order_by(AcaoPublicaEvento.id.desc()).limit(30).all()
    return render_template('acoes_publicas/editor.html', acao=row, types=s.TYPES, statuses=s.STATUS,
        acao_csrf=csrf(), erro=error, form=request.form if error else {}, can_edit=s.allowed('editar'),
        can_publish=s.allowed('publicar'), source_choices=source_media(source), history=history), status


def register_routes(bp):
    @bp.app_template_filter('acao_data')
    def format_date(value):
        if isinstance(value, str):
            value = date.fromisoformat(value)
        return value.strftime('%d/%m/%Y')

    @bp.app_template_filter('acao_hora')
    def format_time(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M')

    @bp.record_once
    def install_limit(state):
        state.app.wsgi_app = BodyLimit(state.app.wsgi_app)

    @bp.app_context_processor
    def navigation():
        return {'acoes_publicas_ready': s.ready(), 'acoes_publicas_can_create': s.allowed('criar'),
                'acoes_publicas_can_view': s.allowed()}

    @bp.after_request
    def no_cache(response):
        if (request.endpoint or '').startswith(('main.acoes_', 'main.portal_acoes', 'main.portal_acao')):
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response

    @bp.get('/acoes-realizadas', endpoint='acoes_listar')
    @login_required
    def listing():
        s.guard()
        demo = mode()
        query = AcaoPublica.query.filter_by(demo=demo)
        selected = request.args.get('prefeitura_id','')
        if not is_admin_global_user(current_user):
            if selected and selected != str(current_user.prefeitura_id):
                abort(403)
            selected = str(current_user.prefeitura_id)
        if selected:
            query = query.filter_by(prefeitura_id=s.city(selected).id)
        pagination = query.order_by(AcaoPublica.atualizado_em.desc(), AcaoPublica.id).paginate(page=page_number(),per_page=20,error_out=False)
        return render_template('acoes_publicas/lista.html', pagination=pagination, demo=demo, selected=selected,
            cities=Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all() if is_admin_global_user(current_user) else [],
            statuses=s.STATUS, can_create=s.allowed('criar'))

    @bp.route('/acoes-realizadas/nova', methods=['GET','POST'], endpoint='acoes_nova')
    @login_required
    def create():
        s.guard('criar')
        error, status = None, 200
        source = source_os(request.form.get('os_id','') if request.method == 'POST' else request.args.get('os_id',''))
        if request.method == 'POST':
            post_guard()
            identifier = request.form.get('request_id','')
            if identifier not in session.get('_acoes_create_ids', []):
                abort(403)
            try:
                row = s.create(request.form, identifier, source)
                return redirect(url_for('main.acoes_editar', identifier=row.id), code=303)
            except s.ActionError as exc:
                db.session.rollback()
                error, status = str(exc), 400
        identifier = request.form.get('request_id') if error else uuid4().hex
        ids = session.get('_acoes_create_ids', [])
        session['_acoes_create_ids'] = (ids + [identifier])[-8:]
        cities = Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome)
        if not is_admin_global_user(current_user):
            cities = cities.filter_by(id=current_user.prefeitura_id)
        activity_date = (source.ordem_servico.data_aplicacao or source.data_agendamento or s.today()) if source else s.today()
        defaults = {'prefeitura_id':str(source.prefeitura_id) if source else str(current_user.prefeitura_id or ''),
            'demo':'false' if source else 'true','titulo':'','tipo':'inspecao','bairro':source.bairro if source else '',
            'inicio':activity_date.isoformat(), 'fim':activity_date.isoformat()}
        return render_template('acoes_publicas/nova.html', cities=cities.all(), form=request.form if error else defaults,
            source=source, acao_csrf=csrf(), request_id=identifier, types=s.TYPES, erro=error), status

    @bp.route('/acoes-realizadas/<identifier>', methods=['GET','POST'], endpoint='acoes_editar')
    @login_required
    def edit(identifier):
        s.guard('editar' if request.method == 'POST' else 'consultar')
        row = s.scoped_action(identifier)
        if request.method == 'POST':
            post_guard()
            try:
                s.edit(row, request.form)
                flash('Rascunho salvo. A versão pública só muda após nova revisão e publicação.', 'success')
                return redirect(url_for('main.acoes_editar', identifier=row.id), code=303)
            except s.ActionError as exc:
                db.session.rollback()
                return private_editor(s.scoped_action(identifier), str(exc), 400)
            except StaleDataError:
                db.session.rollback()
                abort(409)
        return private_editor(row)

    def change(identifier, kind):
        s.guard('publicar' if kind in {'publicar','retirar'} else 'editar')
        post_guard()
        row = s.scoped_action(identifier)
        try:
            s.transition(row, request.form, kind)
            return redirect(url_for('main.acoes_editar',identifier=row.id),code=303)
        except s.ActionError as exc:
            db.session.rollback()
            return private_editor(s.scoped_action(identifier),str(exc),400)
        except StaleDataError:
            db.session.rollback()
            abort(409)

    for kind in ('revisar','rascunho','publicar','retirar'):
        bp.add_url_rule(f'/acoes-realizadas/<identifier>/{kind}',endpoint=f'acoes_{kind}',
            view_func=login_required(lambda identifier, kind=kind:change(identifier,kind)),methods=['POST'])

    @bp.post('/acoes-realizadas/<identifier>/midias',endpoint='acoes_midias_adicionar')
    @login_required
    def add_media(identifier):
        s.guard('editar')
        post_guard()
        row = s.scoped_action(identifier)
        try:
            s.version(row, request.form.get('versao'))
            if request.form.get('source_key'):
                source = source_os(str(row.origem_os_id or ''))
                candidates = source_media(source)
                selected = next((item for item in candidates if item[0] == request.form['source_key']),None)
                if not selected:
                    raise s.ActionError('Selecione um arquivo disponível na OS de origem.')
                from app.modules.piloto_os.routes import _send_os_media
                response = _send_os_media(selected[2])
                try:
                    buffer = io.BytesIO()
                    for chunk in response.iter_encoded():
                        if buffer.tell()+len(chunk)>media.MAX_FILE:
                            raise s.ActionError('O arquivo da OS ultrapassa 50 MiB.')
                        buffer.write(chunk)
                    buffer.seek(0)
                    upload = FileStorage(stream=buffer,filename='copia-selecionada')
                finally:
                    response.close()
            else:
                uploads=request.files.getlist('arquivo')
                if len(uploads)!=1 or not uploads[0].filename:
                    raise s.ActionError('Selecione uma imagem ou um vídeo MP4.')
                upload=uploads[0]
            media.add(row,upload,request.form)
            return redirect(url_for('main.acoes_editar',identifier=identifier)+'#midias',code=303)
        except s.ActionError as exc:
            db.session.rollback()
            return private_editor(s.scoped_action(identifier),str(exc),400)
        except StaleDataError:
            db.session.rollback()
            abort(409)

    @bp.post('/acoes-realizadas/<identifier>/midias/<media_id>/remover',endpoint='acoes_midias_remover')
    @login_required
    def remove_media(identifier,media_id):
        s.guard('editar');post_guard()
        try:
            media.remove(s.scoped_action(identifier),media_id,request.form)
            return redirect(url_for('main.acoes_editar',identifier=identifier)+'#midias',code=303)
        except s.ActionError as exc:
            db.session.rollback()
            return private_editor(s.scoped_action(identifier),str(exc),400)
        except StaleDataError:
            db.session.rollback();abort(409)

    @bp.get('/acoes-realizadas/<identifier>/midias/<media_id>',endpoint='acoes_midia')
    @login_required
    def private_media(identifier,media_id):
        s.guard();row=s.scoped_action(identifier)
        item=next((m for m in row.midias if m.id==media_id),None)
        if item is None:abort(404)
        return media.serve(item)

    @bp.get('/acoes-realizadas/<identifier>/previa',endpoint='acoes_previa')
    @login_required
    def preview(identifier):
        s.guard();row=s.scoped_action(identifier)
        return render_template('acoes_publicas/publicacao.html',acao=row,conteudo=s.snapshot(row),preview=True,types=s.TYPES)

    @bp.get('/portal-cidadao/acoes',endpoint='portal_acoes')
    def public_listing():
        if not s.ready():abort(503)
        demo=mode();selected=request.args.get('prefeitura_id','')
        query=AcaoPublica.query.join(Prefeitura).filter(AcaoPublica.publicado.is_(True),AcaoPublica.demo==demo,Prefeitura.ativa.is_(True))
        if selected:
            if not selected.isascii() or not selected.isdecimal() or len(selected)>10:abort(400)
            query=query.filter(AcaoPublica.prefeitura_id==int(selected))
        dates={key:request.args.get(key,'') for key in ('inicio','fim')}
        try:
            for value in dates.values():
                if value and date.fromisoformat(value).isoformat()!=value:raise ValueError()
            if dates['inicio'] and dates['fim'] and dates['inicio']>dates['fim']:raise ValueError()
        except ValueError:abort(400)
        if dates['inicio']:query=query.filter(AcaoPublica.publicacao['fim'].as_string()>=dates['inicio'])
        if dates['fim']:query=query.filter(AcaoPublica.publicacao['inicio'].as_string()<=dates['fim'])
        pagination=query.order_by(AcaoPublica.publicado_em.desc(),AcaoPublica.id).paginate(page=page_number(),per_page=12,error_out=False)
        return render_template('acoes_publicas/portal.html',pagination=pagination,selected=selected,demo=demo,dates=dates,
            cities=Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all(),types=s.TYPES)

    @bp.get('/portal-cidadao/acoes/<identifier>',endpoint='portal_acao')
    def public_page(identifier):
        row=s.public_action(identifier)
        content = s.public_content(row)
        permalink = url_for('main.portal_acao', identifier=row.id, _external=True)
        return render_template('acoes_publicas/publicacao.html',acao=row,conteudo=content,preview=False,types=s.TYPES,
            whatsapp_url='https://wa.me/?'+urlencode({'text':content['titulo']+' '+permalink}),
            facebook_url='https://www.facebook.com/sharer/sharer.php?'+urlencode({'u':permalink}))

    @bp.get('/portal-cidadao/acoes/<identifier>/midias/<media_id>',endpoint='portal_acao_midia')
    def public_media(identifier,media_id):
        row=s.public_action(identifier)
        approved={m['id'] for m in row.publicacao.get('midias',[])}
        if media_id not in approved:abort(404)
        item=next((m for m in row.midias if m.id==media_id),None)
        if item is None:abort(404)
        return media.serve(item)
