import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import abort, current_app, flash, redirect, render_template, request, session, url_for, send_file
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from app.extensions import db
from app.models import RelatoSaude
from app.shared.access import is_admin_global_user
from app.modules.portal_cidadao.routes import list_public_prefeituras
from .service import STATUS, allowed, create_report, manager, scope, transition, units, filtered


def token():
    session.setdefault('_saude_csrf', secrets.token_urlsafe(32))
    return session['_saude_csrf']


def check_token():
    supplied = request.form.get('saude_csrf', '')
    expected = session.get('_saude_csrf', '')
    if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(403, description='Recarregue o formulário e tente novamente.')


def private(response):
    response = current_app.make_response(response)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


def register_routes(bp):
    @bp.app_template_filter('saude_datetime')
    def local_date(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M') if value else '-'

    @bp.context_processor
    def health_navigation():
        return {'can_access_relatos_saude': allowed}

    @bp.route('/portal-cidadao/relato-saude', methods=['GET', 'POST'], endpoint='portal_relato_saude')
    def public_report():
        errors = {}
        if request.method == 'GET':
            if session.pop('_saude_submitted', False):
                session.pop('_saude_envio', None)
            session.setdefault('_saude_envio', secrets.token_urlsafe(32))
        else:
            check_token()
            envio = session.get('_saude_envio')
            if not envio or not secrets.compare_digest(envio.encode(), request.form.get('envio_id', '').encode()):
                abort(400, description='Reabra o formulário para enviar um novo relato.')
            try:
                # A session quota does not block an entire city behind one shared proxy IP.
                origin = session.setdefault('_saude_origem', secrets.token_urlsafe(32))
                result = create_report(request.form, envio, origin)
                if isinstance(result, dict):
                    errors = result
                else:
                    db.session.commit()
                    session['_saude_recibo'] = {'protocolo': result.protocolo, 'prefeitura': result.prefeitura.nome}
                    session['_saude_submitted'] = True
                    return private(redirect(url_for('main.portal_relato_saude_recibo'), code=303))
            except IntegrityError:
                db.session.rollback()
                # A retry from the same form may race the original commit.
                row = RelatoSaude.query.filter_by(envio_id=envio).first()
                if row is None:
                    raise
                session['_saude_recibo'] = {'protocolo': row.protocolo, 'prefeitura': row.prefeitura.nome}
                session['_saude_submitted'] = True
                return private(redirect(url_for('main.portal_relato_saude_recibo'), code=303))
            except Exception:
                db.session.rollback()
                raise
        return private((render_template('relatos_saude/publico.html', prefeituras=list_public_prefeituras(),
            errors=errors, form=request.form, saude_csrf=token(), envio_id=session.get('_saude_envio', ''),
            hoje=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()), 400 if errors else 200))

    @bp.route('/portal-cidadao/relato-saude/recebido', endpoint='portal_relato_saude_recibo')
    def receipt():
        data = session.get('_saude_recibo')
        if not data:
            return redirect(url_for('main.portal_relato_saude'))
        return private(render_template('relatos_saude/recibo.html', recibo=data))

    @bp.route('/relatos-saude', endpoint='relatos_saude_listar')
    @login_required
    def inbox():
        if not allowed(current_user):
            abort(403)
        query = filtered(current_user, request.args)
        pending = query.filter(RelatoSaude.status != 'CONCLUIDO').count()
        selected = request.args.get('status', '')
        page = query.order_by(RelatoSaude.criado_em.desc(), RelatoSaude.id.desc()).paginate(
            page=request.args.get('page', 1, type=int), per_page=20, error_out=False)
        return private(render_template('relatos_saude/lista.html', pagination=page, status=STATUS,
            selected=selected, pending=pending,
            filters={k:v for k,v in request.args.items() if k in {'status','inicio','fim','prefeitura_id'}},
            prefeituras=[p for p in list_public_prefeituras() if is_admin_global_user(current_user) or p.id == current_user.prefeitura_id] if manager(current_user) else [], can_export=allowed(current_user,'exportar')))

    @bp.route('/relatos-saude/relatorio.pdf', endpoint='relatos_saude_pdf')
    @login_required
    def export_pdf():
        if not allowed(current_user, 'exportar'):
            abort(403)
        rows = filtered(current_user, request.args).order_by(RelatoSaude.criado_em.desc(), RelatoSaude.id.desc()).limit(2001).all()
        if len(rows) > 2000:
            abort(400, description='Restrinja o período: o PDF aceita até 2.000 relatos por geração.')
        from .exporters import pdf
        return private(send_file(pdf(rows, request.args, current_user), mimetype='application/pdf',
            as_attachment=True, download_name='suspeitas-adoecimento.pdf'))

    @bp.route('/relatos-saude/<int:relato_id>', methods=['GET','POST'], endpoint='relatos_saude_detalhe')
    @login_required
    def detail(relato_id):
        if not allowed(current_user):
            abort(403)
        query = scope(current_user).filter(RelatoSaude.id == relato_id)
        row = query.with_for_update().populate_existing().first_or_404() if request.method == 'POST' else query.first_or_404()
        error = None
        status_code = 200
        if request.method == 'POST':
            check_token()
            if not allowed(current_user, 'atender'):
                abort(403)
            try:
                if request.form.get('versao') != str(row.versao):
                    raise StaleDataError()
                transition(row, current_user, request.form)
                db.session.commit()
                flash('Atendimento atualizado. A ação foi registrada no histórico.', 'success')
                destination = url_for('main.relatos_saude_detalhe', relato_id=relato_id) if manager(current_user) or row.uvis_usuario_id == current_user.id else url_for('main.relatos_saude_listar')
                return private(redirect(destination, code=303))
            except StaleDataError:
                db.session.rollback()
                row = scope(current_user).filter_by(id=relato_id).first_or_404()
                error = 'Outra pessoa atualizou este relato. Confira o histórico e tente novamente.'
                status_code = 409
            except ValueError as exc:
                db.session.rollback()
                error = str(exc)
                status_code = 400
            except Exception:
                db.session.rollback()
                raise
        return private((render_template('relatos_saude/detalhe.html', relato=row, status=STATUS,
            saude_csrf=token(), error=error, can_manage=manager(current_user), can_write=allowed(current_user,'atender'),
            uvis_options=units(row.prefeitura_id) if manager(current_user) else []), status_code))
