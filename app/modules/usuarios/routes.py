from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Usuario
from app.modules.usuarios.service import (
    build_admin_users_query,
    delete_admin_user,
    is_admin_managed_user,
    validate_edit_admin_user,
    validate_new_admin_user,
    validate_password_reset,
)


def _admin_only():
    if getattr(current_user, "tipo_usuario", None) != "admin":
        flash("Acesso restrito.", "danger")
        return False
    return True


def register_routes(bp):
    @bp.route("/admin/usuarios/novo", methods=["GET", "POST"], endpoint="admin_usuario_novo")
    @login_required
    def admin_usuario_novo():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            flash("Voce nao tem permissao para acessar esta pagina.", "danger")
            return redirect(url_for("main.dashboard"))

        errors = {}
        form = {}

        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            login = (request.form.get("login") or "").strip()
            tipo_usuario = (request.form.get("tipo_usuario") or "").strip().lower()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor = (request.form.get("codigo_setor") or "").strip() or None
            senha = (request.form.get("senha") or "").strip()
            senha2 = (request.form.get("senha2") or "").strip()

            form = {
                "nome": nome,
                "login": login,
                "tipo_usuario": tipo_usuario,
                "regiao": regiao or "",
                "codigo_setor": codigo_setor or "",
                "senha": senha,
                "senha2": senha2,
            }

            errors = validate_new_admin_user(nome, login, tipo_usuario, regiao, senha, senha2)
            if errors:
                flash("Revise os campos destacados.", "warning")
                return render_template("admin_usuario_novo.html", errors=errors, form=form)

            novo = Usuario(
                nome_uvis=nome,
                regiao=regiao,
                codigo_setor=codigo_setor,
                login=login,
                tipo_usuario=tipo_usuario,
            )
            novo.set_senha(senha)

            try:
                db.session.add(novo)
                db.session.commit()
                flash("Usuario criado com sucesso!", "success")
                return redirect(url_for("main.admin_usuarios_listar"))
            except IntegrityError:
                db.session.rollback()
                errors["login"] = "Esse login ja esta em uso."
                flash(errors["login"], "danger")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao criar usuario administrativo.")
                flash("Erro interno ao criar o usuario. Tente novamente.", "danger")

        return render_template("admin_usuario_novo.html", errors=errors, form=form)

    @bp.route("/admin/usuarios", methods=["GET"], endpoint="admin_usuarios_listar")
    @login_required
    def admin_usuarios_listar():
        if not _admin_only():
            return redirect(url_for("main.dashboard"))

        q = (request.args.get("q") or "").strip()
        tipo = (request.args.get("tipo") or "").strip().lower()
        page = request.args.get("page", 1, type=int)

        paginacao = build_admin_users_query(q, tipo).paginate(page=page, per_page=10, error_out=False)

        return render_template(
            "admin_usuarios_listar.html",
            usuarios=paginacao.items,
            paginacao=paginacao,
            q=q,
            tipo=tipo,
        )

    @bp.route("/admin/usuarios/<int:id>/editar", methods=["GET", "POST"], endpoint="admin_usuario_editar")
    @login_required
    def admin_usuario_editar(id):
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        usuario = Usuario.query.get_or_404(id)
        if not is_admin_managed_user(usuario):
            flash("Registro invalido para edicao.", "warning")
            return redirect(url_for("main.admin_usuarios_listar"))

        errors = {}
        form = {}

        if request.method == "POST":
            nome_uvis = (request.form.get("nome_uvis") or "").strip()
            login = (request.form.get("login") or "").strip()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor = (request.form.get("codigo_setor") or "").strip() or None

            if usuario.id == current_user.id:
                tipo_usuario = usuario.tipo_usuario
            else:
                tipo_usuario = (request.form.get("tipo_usuario") or "").strip().lower()

            senha = (request.form.get("senha") or "").strip()
            senha2 = (request.form.get("senha2") or "").strip()

            form = {
                "nome_uvis": nome_uvis,
                "login": login,
                "regiao": regiao or "",
                "codigo_setor": codigo_setor or "",
                "tipo_usuario": tipo_usuario,
            }

            errors = validate_edit_admin_user(
                nome_uvis=nome_uvis,
                login=login,
                tipo_usuario=tipo_usuario,
                regiao=regiao,
                senha=senha,
                senha2=senha2,
                usuario_id=usuario.id,
            )
            if errors:
                return render_template(
                    "admin_usuario_editar.html",
                    usuario=usuario,
                    errors=errors,
                    form=form,
                )

            usuario.nome_uvis = nome_uvis
            usuario.login = login
            usuario.regiao = regiao
            usuario.codigo_setor = codigo_setor
            usuario.tipo_usuario = tipo_usuario

            if senha:
                usuario.set_senha(senha)

            try:
                db.session.commit()
                flash("Usuario atualizado com sucesso!", "success")
                return redirect(url_for("main.admin_usuarios_listar"))
            except IntegrityError:
                db.session.rollback()
                errors["login"] = "Esse login ja esta em uso."
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar usuario administrativo %s.", usuario.id)
                flash("Erro interno ao atualizar o usuario. Tente novamente.", "danger")

            return render_template(
                "admin_usuario_editar.html",
                usuario=usuario,
                errors=errors,
                form=form,
            )

        form = {
            "nome_uvis": usuario.nome_uvis or "",
            "login": usuario.login or "",
            "regiao": usuario.regiao or "",
            "codigo_setor": usuario.codigo_setor or "",
            "tipo_usuario": usuario.tipo_usuario or "operario",
        }

        return render_template(
            "admin_usuario_editar.html",
            usuario=usuario,
            errors=errors,
            form=form,
        )

    @bp.route("/admin/usuarios/<int:id>/reset_senha", methods=["POST"], endpoint="admin_usuario_reset_senha")
    @login_required
    def admin_usuario_reset_senha(id):
        if not _admin_only():
            return redirect(url_for("main.dashboard"))

        user = Usuario.query.get_or_404(id)
        if not is_admin_managed_user(user):
            flash("Usuario invalido.", "warning")
            return redirect(url_for("main.admin_usuarios_listar"))

        senha = (request.form.get("senha") or "").strip()
        senha2 = (request.form.get("senha2") or "").strip()
        reset_error = validate_password_reset(
            senha,
            senha2,
            user_inputs=(user.nome_uvis, user.login, user.regiao, user.tipo_usuario),
        )
        if reset_error:
            flash(reset_error, "warning")
            return redirect(url_for("main.admin_usuarios_listar"))

        try:
            user.set_senha(senha)
            db.session.commit()
            flash("Senha atualizada com sucesso!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao redefinir senha do usuario %s.", user.id)
            flash("Erro interno ao atualizar a senha. Tente novamente.", "danger")

        return redirect(url_for("main.admin_usuarios_listar"))

    @bp.route("/admin/usuarios/<int:id>/excluir", methods=["POST"], endpoint="admin_usuario_excluir")
    @login_required
    def admin_usuario_excluir(id):
        if not _admin_only():
            return redirect(url_for("main.dashboard"))

        user = Usuario.query.get_or_404(id)
        if not is_admin_managed_user(user):
            flash("Usuario invalido.", "warning")
            return redirect(url_for("main.admin_usuarios_listar"))

        if user.id == current_user.id:
            flash("Voce nao pode excluir seu proprio usuario.", "warning")
            return redirect(url_for("main.admin_usuarios_listar"))

        try:
            delete_admin_user(user)
            db.session.commit()
            flash("Usuario excluido com sucesso!", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Nao foi possivel excluir o usuario porque ainda existem registros vinculados a ele no sistema.", "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao excluir usuario administrativo %s.", user.id)
            flash("Erro interno ao excluir o usuario. Tente novamente.", "danger")

        return redirect(url_for("main.admin_usuarios_listar"))
