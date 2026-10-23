from flask import abort, flash, redirect, render_template, request, url_for, make_response
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from app.extensions import db
from app.models import PrefeituraContatoPublico, PrefeituraContatoHistorico
from app.shared.access import is_covisa_user, is_dev_user
from app.modules.configuracoes.service import prefeitura_permitida, can_access_settings, can_view_all_settings
from .service import FIELDS, schema_ready, snapshot, save, public_directory


def register_routes(bp):
    @bp.route('/configuracoes/contatos/<int:prefeitura_id>', methods=['GET', 'POST'], endpoint='configuracoes_contatos')
    @login_required
    def settings(prefeitura_id):
        from app.modules.configuracoes.routes import _csrf_token, _validate_post
        if not (can_view_all_settings(current_user) or is_covisa_user(current_user)):
            abort(403)
        city = prefeitura_permitida(current_user, prefeitura_id)
        can_write = (is_dev_user(current_user) or is_covisa_user(current_user)) and can_access_settings(current_user, write=True)
        if request.method == 'POST' and not can_write:
            abort(403)
        if not schema_ready():
            abort(503, description='Contatos públicos ainda não disponíveis. Aplique a migração deste módulo.')
        setting = db.session.get(PrefeituraContatoPublico, prefeitura_id)
        values, error, status = snapshot(setting), None, 200
        if request.method == 'POST':
            if request.content_length and request.content_length > 16384:
                abort(413)
            _validate_post(prefeitura_id)
            try:
                save(setting, prefeitura_id, current_user, request.form)
                flash('Contatos públicos da prefeitura atualizados.', 'success')
                return redirect(url_for('main.configuracoes_contatos', prefeitura_id=prefeitura_id), code=303)
            except (StaleDataError, IntegrityError):
                db.session.rollback()
                error, status = 'Outra pessoa alterou estes contatos. Recarregue antes de salvar.', 409
            except ValueError as exc:
                db.session.rollback()
                values = {key: request.form.get(key, '')[:6000] for key in FIELDS}
                values['publicado'] = request.form.get('publicado') == '1'
                error, status = str(exc), 400
            except SQLAlchemyError:
                db.session.rollback()
                error, status = 'Não foi possível salvar. Tente novamente.', 503
        history = PrefeituraContatoHistorico.query.filter_by(prefeitura_id=prefeitura_id).order_by(PrefeituraContatoHistorico.id.desc()).limit(10).all()
        return render_template('configuracoes_contatos.html', prefeitura=city, setting=setting, values=values,
                               can_write=can_write, erro=error, config_csrf_token=_csrf_token(), history=history), status

    @bp.route('/portal-cidadao/contatos', endpoint='portal_contatos')
    def directory():
        data = public_directory()
        selected = request.args.get('prefeitura', '', type=str)
        response = make_response(render_template('portal_contatos.html', directory=data, selected=selected), 200 if data['disponivel'] else 503)
        response.headers['Cache-Control'] = 'no-store'
        return response
