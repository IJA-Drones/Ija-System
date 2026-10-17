"""Municipal destination settings; SMTP credentials stay in the environment."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import Prefeitura, Usuario, PrefeituraEmailConfig, ConsultaEmailEnvio
from app.shared.access import is_admin_global_user, is_covisa_user
from app.modules.configuracoes.service import prefeitura_permitida, require_access, can_view_all_settings, can_access_settings
from app.modules.configuracoes.routes import _csrf_token, _validate_post
from . import mail


def recipient_cities(user):
    query = Prefeitura.query
    if not is_admin_global_user(user):
        query = query.join(Usuario, Usuario.prefeitura_id == Prefeitura.id).filter(Usuario.id == user.id)
    return query.order_by(Prefeitura.nome)


def recipient_config(user, prefeitura_id):
    city = recipient_cities(user).filter(Prefeitura.id == prefeitura_id).first_or_404()
    setting = db.session.get(PrefeituraEmailConfig, city.id)
    return city, setting


def register_routes(bp):
    @bp.route('/configuracoes/email/<int:prefeitura_id>', methods=['GET', 'POST'], endpoint='configuracoes_email')
    @login_required
    def settings(prefeitura_id):
        if not (can_view_all_settings(current_user) or is_covisa_user(current_user)):
            abort(403)
        city = prefeitura_permitida(current_user, prefeitura_id)
        require_access(current_user, write=request.method == 'POST')
        setting = db.session.get(PrefeituraEmailConfig, prefeitura_id)
        error, status = None, 200
        address = setting.destinatario if setting else ''
        if request.method == 'POST':
            if request.content_length and request.content_length > 4096:
                abort(413)
            _validate_post(prefeitura_id)
            address = request.form.get('destinatario', '').strip()
            try:
                # Empty explicitly disables this municipality's email destination.
                if address:
                    mail.validate_recipient(address)
                version_text = request.form.get('versao', '')
                if not version_text.isascii() or not version_text.isdecimal() or len(version_text) > 10:
                    raise ValueError('Versão inválida. Recarregue a página antes de salvar.')
                version = int(version_text)
                if version != (setting.versao if setting else 0):
                    raise StaleDataError()
                if setting is None:
                    setting = PrefeituraEmailConfig(prefeitura_id=prefeitura_id)
                    db.session.add(setting)
                setting.destinatario = address
                setting.atualizado_por_id = current_user.id
                db.session.commit()
                flash('E-mail dos relatórios atualizado para esta prefeitura.', 'success')
                return redirect(url_for('main.configuracoes_email', prefeitura_id=prefeitura_id), code=303)
            except (StaleDataError, IntegrityError):
                db.session.rollback()
                error, status = 'Outra pessoa alterou esta configuração. Recarregue antes de salvar.', 409
            except ValueError as exc:
                db.session.rollback()
                error, status = str(exc), 400
            except SQLAlchemyError:
                db.session.rollback()
                error, status = 'Não foi possível salvar. Tente novamente.', 503
        history = db.session.query(ConsultaEmailEnvio, Usuario.login).join(Usuario, Usuario.id == ConsultaEmailEnvio.usuario_id).filter(
            ConsultaEmailEnvio.prefeitura_id == prefeitura_id).order_by(ConsultaEmailEnvio.criado_em.desc()).limit(20).all()
        return render_template('configuracoes_email.html', prefeitura=city, setting=setting,
            can_configurar_email=can_access_settings(current_user, write=True),
            destinatario=address, erro=error, history=history, email_available=mail.available(),
            config_csrf_token=_csrf_token()), status
