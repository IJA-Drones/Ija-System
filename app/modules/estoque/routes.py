from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.estoque.service import (
    ESTOQUE_STATUS,
    build_peca_form,
    create_peca,
    delete_peca,
    get_peca_scoped_or_404,
    list_drones_for_estoque,
    list_pecas,
    update_peca,
    validate_peca_form,
)
from app.shared.access import normalize_role


def _require_estoque_access():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "diretor"}:
        abort(403)


def register_routes(bp):
    @bp.route("/estoque", methods=["GET"], endpoint="estoque_listar")
    @login_required
    def estoque_listar():
        _require_estoque_access()
        pecas = list_pecas(user=current_user)
        return render_template("estoque_listar.html", pecas=pecas, status_labels=ESTOQUE_STATUS)

    @bp.route("/estoque/novo", methods=["GET", "POST"], endpoint="estoque_novo")
    @login_required
    def estoque_novo():
        _require_estoque_access()
        errors = {}
        form = {"status": "disponivel_manutencao", "quantidade": "1"}
        drones = list_drones_for_estoque(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_peca_form(request.form, user=current_user)
            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("estoque_form.html", form=form, errors=errors, drones=drones, status_labels=ESTOQUE_STATUS)
            try:
                create_peca(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None))
                flash("Peca cadastrada no estoque com sucesso.", "success")
                return redirect(url_for("main.estoque_listar"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar peca no estoque.")
                flash("Erro interno ao cadastrar a peca.", "danger")

        return render_template("estoque_form.html", form=form, errors=errors, drones=drones, status_labels=ESTOQUE_STATUS)

    @bp.route("/estoque/<int:peca_id>/editar", methods=["GET", "POST"], endpoint="estoque_editar")
    @login_required
    def estoque_editar(peca_id):
        _require_estoque_access()
        peca = get_peca_scoped_or_404(peca_id, current_user)
        errors = {}
        drones = list_drones_for_estoque(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_peca_form(request.form, existing_peca=peca, user=current_user)
            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("estoque_form.html", peca=peca, form=form, errors=errors, drones=drones, status_labels=ESTOQUE_STATUS)
            try:
                update_peca(peca, cleaned)
                flash("Peca atualizada com sucesso.", "success")
                return redirect(url_for("main.estoque_listar"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar peca %s.", peca.id)
                flash("Erro interno ao atualizar a peca.", "danger")

        return render_template("estoque_form.html", peca=peca, form=build_peca_form(peca), errors=errors, drones=drones, status_labels=ESTOQUE_STATUS)

    @bp.route("/estoque/<int:peca_id>/deletar", methods=["POST"], endpoint="estoque_deletar")
    @login_required
    def estoque_deletar(peca_id):
        _require_estoque_access()
        peca = get_peca_scoped_or_404(peca_id, current_user)
        try:
            delete_peca(peca)
            flash("Peca removida do estoque.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover peca %s.", peca.id)
            flash("Erro ao remover a peca.", "danger")
        return redirect(url_for("main.estoque_listar"))
