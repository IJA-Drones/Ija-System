from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Baterias, Drones
from app.modules.equipamentos.service import (
    build_bateria_edit_form,
    build_drone_edit_form,
    create_bateria,
    create_drone,
    delete_bateria,
    delete_drone,
    list_active_equipes,
    list_baterias,
    list_drones,
    list_drones_for_baterias,
    list_equipamentos_dashboard,
    list_equipamentos_manutencao,
    send_drone_to_manutencao,
    update_bateria,
    update_bateria_ciclos,
    update_drone,
    validate_bateria_form,
    validate_drone_form,
)
from app.shared.access import apply_prefeitura_scope, normalize_role


def _require_admin_or_operario():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"}:
        abort(403)


def _get_scoped_drone_or_404(drone_id: int):
    query = apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id)
    return query.filter(Drones.id == drone_id).first_or_404()


def _get_scoped_bateria_or_404(bateria_id: int):
    query = apply_prefeitura_scope(Baterias.query, current_user, Baterias.prefeitura_id)
    return query.filter(Baterias.id == bateria_id).first_or_404()


def register_routes(bp):
    @bp.route("/equipamentos", methods=["GET"], endpoint="listar_equipamentos")
    @login_required
    def listar_equipamentos():
        return render_template("equipamentos_listar.html", **list_equipamentos_dashboard(user=current_user))

    @bp.route("/equipamentos/drones", methods=["GET"], endpoint="listar_drones")
    @login_required
    def listar_drones_view():
        tipo_usuario = normalize_role(getattr(current_user, "tipo_usuario", None))
        return render_template(
            "drones_listar.html",
            drones=list_drones(user=current_user),
            is_admin=tipo_usuario in {"dev", "diretor", "admin"},
            can_manage=tipo_usuario in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"},
        )

    @bp.route("/equipamentos/baterias", methods=["GET"], endpoint="listar_baterias")
    @login_required
    def listar_baterias_view():
        tipo_usuario = normalize_role(getattr(current_user, "tipo_usuario", None))
        return render_template(
            "baterias_listar.html",
            baterias=list_baterias(user=current_user),
            is_admin=tipo_usuario in {"dev", "diretor", "admin"},
            can_manage=tipo_usuario in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"},
        )

    @bp.route("/drones/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_drone")
    @login_required
    def cadastrar_drone():
        _require_admin_or_operario()

        errors = {}
        form = {}
        equipes = list_active_equipes(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_drone_form(request.form, user=current_user)

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("cadastrar_drone.html", form=form, errors=errors, equipes=equipes)

            try:
                create_drone(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None))
                flash("Drone cadastrado com sucesso!", "success")
                return redirect(url_for("main.cadastrar_drone"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar drone.")
                flash("Erro interno ao cadastrar o drone. Tente novamente.", "danger")
                return render_template("cadastrar_drone.html", form=form, errors=errors, equipes=equipes)

        return render_template("cadastrar_drone.html", form=form, errors=errors, equipes=equipes)

    @bp.route("/drones/<int:drone_id>/editar", methods=["GET", "POST"], endpoint="editar_drone")
    @login_required
    def editar_drone(drone_id):
        _require_admin_or_operario()

        drone = _get_scoped_drone_or_404(drone_id)
        errors = {}
        equipes = list_active_equipes(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_drone_form(request.form, existing_drone=drone, user=current_user)

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "editar_drone.html",
                    drone=drone,
                    form=form,
                    errors=errors,
                    equipes=equipes,
                )

            try:
                update_drone(drone, cleaned)
                flash("Drone atualizado com sucesso!", "success")
                return redirect(url_for("main.listar_drones"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar drone %s.", drone.id)
                flash("Erro interno ao atualizar o drone. Tente novamente.", "danger")
                return render_template(
                    "editar_drone.html",
                    drone=drone,
                    form=form,
                    errors=errors,
                    equipes=equipes,
                )

        return render_template(
            "editar_drone.html",
            drone=drone,
            form=build_drone_edit_form(drone),
            errors=errors,
            equipes=equipes,
        )

    @bp.route("/drones/<int:drone_id>/deletar", methods=["POST"], endpoint="deletar_drone")
    @login_required
    def deletar_drone_view(drone_id):
        _require_admin_or_operario()

        drone = _get_scoped_drone_or_404(drone_id)
        try:
            delete_drone(drone)
            flash("Drone removido com sucesso.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao deletar drone %s.", drone.id)
            flash("Erro ao remover drone. Verifique vinculos (baterias/OS) e tente novamente.", "danger")

        return redirect(url_for("main.listar_drones"))

    @bp.route("/baterias/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_bateria")
    @login_required
    def cadastrar_bateria():
        _require_admin_or_operario()

        errors = {}
        form = {}
        drones = list_drones_for_baterias(user=current_user)
        drone_id_pre = request.args.get("drone_id", type=int)

        if request.method == "POST":
            form, cleaned, errors = validate_bateria_form(request.form, user=current_user)

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("cadastrar_bateria.html", form=form, errors=errors, drones=drones)

            try:
                create_bateria(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None))
                flash("Bateria cadastrada com sucesso!", "success")
                return redirect(url_for("main.listar_baterias"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar bateria.")
                flash("Erro interno ao cadastrar a bateria. Tente novamente.", "danger")
                return render_template("cadastrar_bateria.html", form=form, errors=errors, drones=drones)

        if drone_id_pre and apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id).filter(Drones.id == drone_id_pre).first():
            form["drone_id"] = str(drone_id_pre)

        return render_template("cadastrar_bateria.html", form=form, errors=errors, drones=drones)

    @bp.route("/baterias/<int:bateria_id>/editar", methods=["GET", "POST"], endpoint="editar_bateria")
    @login_required
    def editar_bateria(bateria_id):
        _require_admin_or_operario()

        bateria = _get_scoped_bateria_or_404(bateria_id)
        drones = list_drones_for_baterias(user=current_user)
        errors = {}

        if request.method == "POST":
            form, cleaned, errors = validate_bateria_form(request.form, existing_bateria=bateria, user=current_user)

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "editar_bateria.html",
                    bateria=bateria,
                    form=form,
                    errors=errors,
                    drones=drones,
                )

            try:
                update_bateria(bateria, cleaned)
                flash("Bateria atualizada com sucesso!", "success")
                return redirect(url_for("main.listar_baterias"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar bateria %s.", bateria.id)
                flash("Erro interno ao atualizar a bateria. Tente novamente.", "danger")
                return render_template(
                    "editar_bateria.html",
                    bateria=bateria,
                    form=form,
                    errors=errors,
                    drones=drones,
                )

        return render_template(
            "editar_bateria.html",
            bateria=bateria,
            form=build_bateria_edit_form(bateria),
            errors=errors,
            drones=drones,
        )

    @bp.route("/baterias/<int:bateria_id>/deletar", methods=["POST"], endpoint="deletar_bateria")
    @login_required
    def deletar_bateria_view(bateria_id):
        _require_admin_or_operario()

        bateria = _get_scoped_bateria_or_404(bateria_id)
        try:
            delete_bateria(bateria)
            flash("Bateria removida com sucesso.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover bateria %s.", bateria.id)
            flash("Erro interno ao remover a bateria. Tente novamente.", "danger")

        return redirect(url_for("main.listar_baterias"))

    @bp.route("/equipamentos/em-manutencao", methods=["GET"], endpoint="equipamentos_manutencao")
    @login_required
    def equipamentos_manutencao():
        equipamentos = list_equipamentos_manutencao(user=current_user)
        return render_template(
            "equipamentos_manutencao.html",
            equipamentos=equipamentos,
            total=len(equipamentos),
        )

    @bp.route("/equipamentos/baterias/update_ciclos/<int:id>", methods=["POST"], endpoint="update_ciclos")
    @login_required
    def update_ciclos(id):
        _require_admin_or_operario()
        bateria = _get_scoped_bateria_or_404(id)
        return jsonify(update_bateria_ciclos(bateria, request.get_json() or {}))

    @bp.route("/drones/<int:drone_id>/manutencao", methods=["POST"], endpoint="enviar_manutencao_drone")
    @login_required
    def enviar_manutencao_drone(drone_id):
        _require_admin_or_operario()

        drone = _get_scoped_drone_or_404(drone_id)
        try:
            if not send_drone_to_manutencao(drone):
                flash("Este drone ja esta em manutencao.", "warning")
                return redirect(url_for("main.listar_drones"))

            flash(f"Drone {drone.renomacao} enviado para manutencao.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao enviar drone %s para manutencao.", drone.id)
            flash("Erro ao enviar o drone para manutencao.", "danger")

        return redirect(url_for("main.listar_drones"))
