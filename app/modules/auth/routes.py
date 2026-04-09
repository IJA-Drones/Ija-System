from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.modules.auth.service import authenticate_piloto_agro, authenticate_user, get_authenticated_redirect_endpoint


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(get_authenticated_redirect_endpoint(current_user)))

    if request.method == "POST":
        login_form = request.form.get("login")
        senha_form = request.form.get("senha")

        user = authenticate_user(login_form, senha_form)
        if user:
            login_user(user)
            flash(f"Bem-vindo, {user.nome_uvis}! Login realizado com sucesso.", "success")
            return redirect(url_for(get_authenticated_redirect_endpoint(user)))

        flash("Login ou senha incorretos. Tente novamente.", "danger")

    return render_template("login.html")


@bp.route("/agro/login", methods=["GET", "POST"])
def login_piloto_agro():
    if current_user.is_authenticated:
        return redirect(url_for(get_authenticated_redirect_endpoint(current_user)))

    if request.method == "POST":
        login_form = request.form.get("login")
        senha_form = request.form.get("senha")

        user, error_code = authenticate_piloto_agro(login_form, senha_form)
        if user:
            login_user(user)
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
    logout_user()
    session.clear()
    flash("Voce saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
