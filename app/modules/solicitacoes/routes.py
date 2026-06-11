import os

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.solicitacoes.service import (
    NovoCadastroValidationError,
    build_novo_cadastro_context,
    build_novo_cadastro_context_with_form,
    build_editar_solicitacao_context,
    create_nova_solicitacao,
    deletar_solicitacao_admin,
    atualizar_solicitacao,
    SolicitacaoAccessError,
)


def register_routes(bp):
    @bp.route("/novo_cadastro", methods=["GET", "POST"], endpoint="novo")
    @login_required
    def novo():
        if getattr(current_user, "tipo_usuario", None) not in {"uvis", "dev", "admin", "visualizar", "prefeitura_admin"}:
            flash("Seu perfil nao possui permissao para criar solicitacoes.", "warning")
            return redirect(url_for("main.dashboard"))

        google_maps_key = current_app.config.get("Maps_KEY_FRONT") or os.getenv("KEY_API_GOOGLE_MAPS")
        context = build_novo_cadastro_context(current_user, google_maps_key)

        if request.method == "POST":
            try:
                create_nova_solicitacao(current_user, request.form)
                flash("Solicitacao criada e enviada para a UVIS com sucesso!", "success")
                return redirect(url_for("main.dashboard"))
            except NovoCadastroValidationError as exc:
                flash(exc.message, exc.category)
                context = build_novo_cadastro_context_with_form(current_user, google_maps_key, request.form)
                return render_template("cadastro.html", **context)
            except Exception:
                current_app.logger.exception("Erro ao criar nova solicitacao.")
                flash("Erro ao salvar o pedido.", "danger")
                context = build_novo_cadastro_context_with_form(current_user, google_maps_key, request.form)

        return render_template("cadastro.html", **context)

    @bp.route("/solicitacao/editar/<int:id>", methods=["GET", "POST"], endpoint="editar_solicitacao")
    @login_required
    def editar_solicitacao(id):
        try:
            context = build_editar_solicitacao_context(current_user, id)
        except SolicitacaoAccessError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        if request.method == "POST":
            try:
                redirect_endpoint = atualizar_solicitacao(current_user, id, request.form)
                flash("Solicitacao atualizada com sucesso!", "success")
                return redirect(url_for(redirect_endpoint))
            except NovoCadastroValidationError as exc:
                flash(exc.message, exc.category)
            except SolicitacaoAccessError as exc:
                flash(exc.message, exc.category)
                return redirect(url_for(exc.redirect_endpoint))
            except Exception:
                current_app.logger.exception("Erro ao editar solicitacao %s.", id)
                flash("Erro interno ao salvar a solicitacao. Tente novamente.", "danger")
                context = build_editar_solicitacao_context(current_user, id)

        return render_template("editar_solicitacao.html", **context)

    @bp.route("/admin/deletar/<int:id>", methods=["POST"], endpoint="deletar_registro")
    @login_required
    def deletar_registro(id):
        try:
            message = deletar_solicitacao_admin(current_user, id)
            flash(message, "success")
        except SolicitacaoAccessError as exc:
            flash(exc.message, exc.category)
        return redirect(url_for("main.admin_dashboard"))
