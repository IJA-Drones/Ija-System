"""DEV-only visibility and accountable release of login locks."""
import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.extensions import db
from app.models import LoginBloqueio, LoginEvento, PoliticaSenha
from app.shared.access import is_dev_user
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.login_protection import policy, unlock_bucket, utcnow
from app.shared.login_protection import client_ip
from app.shared.password_expiration import validity_days, valid_csrf


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
                               policy=policy(), password_validity_days=validity_days(),
                               unlock_csrf=session[CSRF_SESSION_KEY]), 200, {'Cache-Control': 'private, no-store'}

    @bp.post('/dev/seguranca-login/validade-senha', endpoint='password_policy_save')
    @login_required
    def password_policy_save():
        if not is_dev_user(current_user):
            abort(403)
        if not valid_csrf(request.form.get('_csrf_token')):
            abort(403, description='Recarregue a página e tente novamente.')
        try:
            days = int(request.form.get('validade_dias', ''))
        except (ValueError, TypeError):
            abort(400, description='Informe um prazo inteiro entre 1 e 365 dias.')
        if not 1 <= days <= 365:
            abort(400, description='Informe um prazo inteiro entre 1 e 365 dias.')
        try:
            dialect = db.session.get_bind().dialect.name
            if dialect not in {'postgresql', 'sqlite'}:
                abort(503)
            insert = pg_insert if dialect == 'postgresql' else sqlite_insert
            db.session.execute(insert(PoliticaSenha).values(id=1, validade_dias=90)
                               .on_conflict_do_nothing(index_elements=['id']))
            settings = db.session.execute(select(PoliticaSenha).where(PoliticaSenha.id == 1)
                                          .with_for_update().execution_options(populate_existing=True)).scalar_one()
            previous = settings.validade_dias
            if previous != days:
                settings.validade_dias = days
                settings.atualizado_em = utcnow()
                settings.atualizado_por_id = current_user.id
                db.session.add(LoginEvento(
                    criado_em=utcnow(), login=current_user.login, ip=client_ip(), canal='dev',
                    resultado='politica_senha', usuario_id=current_user.id, responsavel_id=current_user.id,
                    motivo=f'Validade das senhas alterada de {previous} para {days} dias.',
                ))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(503, description='Não foi possível salvar a validade das senhas. Tente novamente.')
        flash('Validade das senhas salva com sucesso.', 'success')
        return redirect(url_for('main.login_security'), code=303)

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
