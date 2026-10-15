"""Renew expired credentials without granting a regular authenticated session."""
from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import LoginEvento, Usuario
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.login_protection import client_ip, utcnow
from app.shared.password_expiration import (
    LOGIN_CHANNELS, RENEWAL_KEY, ensure_csrf, valid_csrf, valid_renewal, validity_days,
)
from app.shared.password_policy import password_input, password_policy, validate_password


def register_routes(bp):
    @bp.route("/renovar-senha", methods=["GET", "POST"], endpoint="renew_password")
    def renew_password():
        state = session.get(RENEWAL_KEY)
        channel = state.get("channel") if isinstance(state, dict) else None
        login_endpoint = LOGIN_CHANNELS.get(channel, "auth.login")

        def restart():
            session.pop(RENEWAL_KEY, None)
            session.pop(CSRF_SESSION_KEY, None)
            flash("Entre novamente com sua senha atual para iniciar a renovação.", "warning")
            return redirect(url_for(login_endpoint), code=303)

        if not isinstance(state, dict) or not isinstance(state.get("user_id"), int):
            return restart()
        if request.method == "POST" and not valid_csrf(request.form.get("_csrf_token")):
            abort(403, description="Recarregue a página e tente novamente.")
        try:
            query = select(Usuario).where(Usuario.id == state["user_id"])
            if request.method == "POST":
                query = query.with_for_update(of=Usuario).execution_options(populate_existing=True)
            user = db.session.execute(query).unique().scalar_one_or_none()
            if not valid_renewal(state, user):
                db.session.rollback()
                return restart()
            error = None
            if request.method == "POST":
                password = password_input(request.form.get("senha"))
                confirmation = password_input(request.form.get("senha2"))
                if not password or password != confirmation:
                    error = "Informe a nova senha e repita a mesma senha na confirmação."
                else:
                    error = validate_password(password, enforce=True)
                if not error and user.check_senha(password):
                    error = "Escolha uma senha diferente da senha atual."
                if not error:
                    # Conditional write also protects against replay/races on SQLite,
                    # where SELECT FOR UPDATE is not available.
                    candidate = Usuario()
                    candidate.set_senha(password)
                    result = db.session.execute(update(Usuario).where(
                        Usuario.id == user.id, Usuario.senha_hash == user.senha_hash,
                    ).values(senha_hash=candidate.senha_hash,
                             senha_alterada_em=candidate.senha_alterada_em)
                        .execution_options(synchronize_session=False))
                    if result.rowcount != 1:
                        db.session.rollback()
                        return restart()
                    db.session.add(LoginEvento(
                        criado_em=utcnow(), login=user.login, ip=client_ip(), canal=channel,
                        resultado="senha_renovada", usuario_id=user.id,
                        motivo="Senha vencida renovada pelo próprio usuário.",
                    ))
                    db.session.commit()
                    session.clear()
                    session["_remember"] = "clear"
                    flash("Senha renovada com sucesso. Entre com sua nova senha.", "success")
                    return redirect(url_for(login_endpoint), code=303)
            days = validity_days()
            db.session.rollback()  # Do not retain a row lock while rendering errors.
            return render_template("renew_password.html", error=error,
                                   renewal_csrf=ensure_csrf(), validity_days=days,
                                   rules=password_policy(), login_endpoint=login_endpoint), 400 if error else 200
        except SQLAlchemyError:
            db.session.rollback()
            return "Não foi possível renovar a senha agora. Tente novamente em instantes.", 503
