"""DEV-only visibility and accountable release of login locks."""
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import LoginBloqueio, LoginEvento
from app.shared.access import is_dev_user
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.login_protection import policy, unlock_bucket, utcnow


def register_routes(bp):
    @bp.get('/dev/seguranca-login', endpoint='login_security')
    @login_required
    def login_security():
        if not is_dev_user(current_user):
            abort(403)
        if not session.get(CSRF_SESSION_KEY):
            session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
        blocked = LoginBloqueio.query.filter(LoginBloqueio.bloqueado_ate > utcnow()).order_by(
            LoginBloqueio.bloqueado_ate.desc()).limit(100).all()
        events = LoginEvento.query.order_by(LoginEvento.criado_em.desc(), LoginEvento.id.desc()).limit(100).all()
        return render_template('login_security.html', blocked=blocked, events=events,
                               policy=policy(), unlock_csrf=session[CSRF_SESSION_KEY]), 200, {'Cache-Control': 'private, no-store'}

    @bp.post('/dev/seguranca-login/<string:key>/desbloquear', endpoint='login_security_unlock')
    @login_required
    def login_security_unlock(key):
        if not is_dev_user(current_user):
            abort(403)
        expected = session.get(CSRF_SESSION_KEY)
        supplied = request.form.get('_csrf_token', '')
        if not isinstance(expected, str) or not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
            abort(403)
        try:
            if not unlock_bucket(key, current_user, request.form.get('motivo', '')):
                abort(404)
        except ValueError as exc:
            abort(400, description=str(exc))
        except SQLAlchemyError:
            abort(503, description='Não foi possível desbloquear agora. Tente novamente.')
        flash('Bloqueio liberado. A ação e o motivo foram registrados.', 'success')
        return redirect(url_for('main.login_security'), code=303)
