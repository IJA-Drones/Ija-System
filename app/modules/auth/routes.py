from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import Usuario
from app.modules.auth.service import (
    authenticate_piloto_agro,
    authenticate_user,
    authenticate_uvis_operacional,
    get_authenticated_redirect_endpoint,
)
from app.shared.presence import record_user_presence
from app.shared.session_security import start_security_session
from app.shared.csrf_security import rotate_csrf_token
from app.shared.login_protection import LoginBlocked, LoginProtectionUnavailable
from app.shared.password_expiration import password_expired, start_renewal, remember_password_version
from sqlalchemy.exc import SQLAlchemyError


bp = Blueprint("auth", __name__)


def _password_renewal_redirect(user, channel):
    try:
        verified_hash = getattr(user, "_verified_password_hash", None)
        if verified_hash is not None and verified_hash != user.senha_hash:
            raise LoginProtectionUnavailable()
        if password_expired(user):
            start_renewal(user, channel)
            return redirect(url_for("auth.renew_password"), code=303)
    except SQLAlchemyError:
        from app.extensions import db
        db.session.rollback()
        raise LoginProtectionUnavailable() from None
    remember_password_version(user)


def _login_error_page(message, status, retry_after=None):
    template = {
        "auth.login_uvis_operacional": "login_uvis_operacional.html",
        "auth.login_piloto_agro": "login_piloto_agro.html",
    }.get(request.endpoint, "login.html")
    if not retry_after:
        flash(message, "warning")
    headers = {"Cache-Control": "private, no-store"}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return render_template(
        template, login_retry_after=retry_after,
        login_retry_minutes=(retry_after + 59) // 60 if retry_after else None,
        login_value=(request.form.get("login") or "")[:50] if retry_after else "",
    ), status, headers


@bp.errorhandler(LoginBlocked)
def login_blocked(error):
    minutes = max(1, (error.seconds + 59) // 60)
    return _login_error_page(
        f"Muitas tentativas de acesso. Aguarde cerca de {minutes} minuto(s) e tente novamente.",
        429, error.seconds,
    )


@bp.errorhandler(LoginProtectionUnavailable)
def login_protection_unavailable(error):
    return _login_error_page("Não foi possível verificar o acesso agora. Tente novamente em instantes.", 503)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(get_authenticated_redirect_endpoint(current_user)))

    if request.method == "POST":
        login_form = request.form.get("login")
        senha_form = request.form.get("senha")

        user = authenticate_user(login_form, senha_form)
        if user:
            renewal = _password_renewal_redirect(user, "principal")
            if renewal:
                return renewal
            login_user(user)
            start_security_session()
            rotate_csrf_token()
            record_user_presence(user, mark_login=True)
            flash(f"Bem-vindo, {user.nome_uvis}! Login realizado com sucesso.", "success")
            return redirect(url_for(get_authenticated_redirect_endpoint(user)))

        piloto_agro = (
            Usuario.query.filter_by(login=login_form, tipo_usuario="piloto_agro").first()
            if login_form and senha_form and len(login_form) <= 50 and len(senha_form) <= 128 else None
        )
        if piloto_agro and piloto_agro.check_senha(senha_form):
            flash("Piloto Agro deve acessar pelo login exclusivo do Agro.", "warning")
            return redirect(url_for("auth.login_piloto_agro"))

        flash("Login ou senha incorretos. Tente novamente.", "danger")

    return render_template("login.html")


@bp.route("/uvis-operacional/login", methods=["GET", "POST"])
def login_uvis_operacional():
    if current_user.is_authenticated:
        user_type = getattr(current_user, "tipo_usuario", None)
        if user_type in {"uvis", "equipe_uvis"}:
            return redirect(url_for("main.dashboard_equipe_uvis"))
        return redirect(url_for(get_authenticated_redirect_endpoint(current_user)))

    if request.method == "POST":
        login_form = request.form.get("login")
        senha_form = request.form.get("senha")

        user = authenticate_uvis_operacional(login_form, senha_form)
        if user:
            renewal = _password_renewal_redirect(user, "uvis")
            if renewal:
                return renewal
            login_user(user)
            start_security_session()
            rotate_csrf_token()
            record_user_presence(user, mark_login=True)
            flash(f"Bem-vindo, {user.nome_uvis}! Acesso operacional UVIS liberado.", "success")
            return redirect(url_for("main.dashboard_equipe_uvis"))

        flash("Login ou senha incorretos para o acesso operacional UVIS.", "danger")

    return render_template("login_uvis_operacional.html")


@bp.route("/agro/login", methods=["GET", "POST"])
def login_piloto_agro():
    if current_user.is_authenticated:
        return redirect(url_for(get_authenticated_redirect_endpoint(current_user)))

    if request.method == "POST":
        login_form = request.form.get("login")
        senha_form = request.form.get("senha")

        user, error_code = authenticate_piloto_agro(login_form, senha_form)
        if user:
            renewal = _password_renewal_redirect(user, "agro")
            if renewal:
                return renewal
            login_user(user)
            start_security_session()
            rotate_csrf_token()
            record_user_presence(user, mark_login=True)
            flash(f"Bem-vindo, {user.nome_uvis}! Login do Agro realizado com sucesso.", "success")
            return redirect(url_for("main.agro_piloto_dashboard"))

        if error_code == "inactive":
            flash("Seu acesso do Agro esta inativo no momento. Fale com a administracao.", "warning")
        else:
            flash("Login ou senha incorretos para o acesso do piloto Agro.", "danger")

    return render_template("login_piloto_agro.html")


@bp.route("/logout")
@login_required
def logout():
    record_user_presence(current_user, mark_logout=True)
    logout_user()
    session.clear()
    flash("Voce saiu do sistema.", "info")
    return redirect(url_for("auth.login"))


from app.modules.auth.password_routes import register_routes as register_password_routes
register_password_routes(bp)
