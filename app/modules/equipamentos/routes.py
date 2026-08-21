from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.equipamentos.exporters import XLSX_MIME, build_manutencao_pdf, build_manutencoes_excel, build_pecas_usadas_excel
from app.models import Baterias, Drones
from app.modules.equipamentos.service import (
    build_bateria_edit_form,
    build_drone_edit_form,
    create_bateria,
    create_drone,
    delete_bateria,
    delete_drone,
    encerrar_manutencao_drone,
    get_manutencao_aberta,
    get_manutencao_scoped_or_404,
    list_active_equipes,
    list_baterias,
    list_drones,
    list_drones_for_baterias,
    list_equipamentos_dashboard,
    list_equipamentos_manutencao,
    list_historico_manutencoes,
    list_historico_pecas_usadas,
    list_pecas_disponiveis_manutencao,
    list_pecas_usadas_manutencao,
    registrar_pecas_usadas_manutencao,
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

    @bp.route("/equipamentos/manutencoes/historico", methods=["GET"], endpoint="equipamentos_manutencoes_historico")
    @login_required
    def equipamentos_manutencoes_historico():
        _require_admin_or_operario()
        return render_template(
            "equipamentos_manutencoes_historico.html",
            manutencoes=list_historico_manutencoes(user=current_user),
        )

    @bp.route("/equipamentos/manutencoes/historico/excel", methods=["GET"], endpoint="equipamentos_manutencoes_historico_excel")
    @login_required
    def equipamentos_manutencoes_historico_excel():
        _require_admin_or_operario()
        output, filename = build_manutencoes_excel(list_historico_manutencoes(user=current_user))
        return send_file(output, mimetype=XLSX_MIME, as_attachment=True, download_name=filename)

    @bp.route("/equipamentos/manutencoes/pecas/historico", methods=["GET"], endpoint="equipamentos_manutencoes_pecas_historico")
    @login_required
    def equipamentos_manutencoes_pecas_historico():
        _require_admin_or_operario()
        return render_template(
            "equipamentos_manutencoes_pecas_historico.html",
            usos=list_historico_pecas_usadas(user=current_user),
        )

    @bp.route("/equipamentos/manutencoes/pecas/historico/excel", methods=["GET"], endpoint="equipamentos_manutencoes_pecas_historico_excel")
    @login_required
    def equipamentos_manutencoes_pecas_historico_excel():
        _require_admin_or_operario()
        output, filename = build_pecas_usadas_excel(list_historico_pecas_usadas(user=current_user))
        return send_file(output, mimetype=XLSX_MIME, as_attachment=True, download_name=filename)

    @bp.route("/equipamentos/manutencoes/<int:manutencao_id>", methods=["GET"], endpoint="equipamento_manutencao_detalhe")
    @login_required
    def equipamento_manutencao_detalhe(manutencao_id):
        _require_admin_or_operario()
        manutencao = get_manutencao_scoped_or_404(manutencao_id, current_user)
        return render_template(
            "equipamento_manutencao_detalhe.html",
            manutencao=manutencao,
            usos=manutencao.pecas_usadas,
        )

    @bp.route("/equipamentos/<int:drone_id>/manutencao/pecas", methods=["GET", "POST"], endpoint="equipamento_manutencao_pecas")
    @login_required
    def equipamento_manutencao_pecas(drone_id):
        _require_admin_or_operario()
        drone = _get_scoped_drone_or_404(drone_id)

        if (drone.status or "").strip() not in {"Em Manutenção", "Manutenção", "Manutencao", "Em Manutencao"}:
            flash("Este drone nao esta em manutencao.", "warning")
            return redirect(url_for("main.equipamentos_manutencao"))

        errors = {}
        if request.method == "POST":
            try:
                usos, errors = registrar_pecas_usadas_manutencao(drone, request.form, user=current_user)
                if not errors:
                    flash(f"{len(usos)} peca(s) registrada(s) na manutencao.", "success")
                    return redirect(url_for("main.equipamentos_manutencao"))
                flash("Corrija os campos destacados.", "warning")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao registrar pecas usadas na manutencao do drone %s.", drone.id)
                flash("Erro interno ao registrar as pecas usadas.", "danger")

        return render_template(
            "equipamento_manutencao_pecas.html",
            drone=drone,
            manutencao=get_manutencao_aberta(drone, user=current_user),
            pecas=list_pecas_disponiveis_manutencao(drone, user=current_user),
            usos=list_pecas_usadas_manutencao(drone, user=current_user),
            errors=errors,
        )

    @bp.route("/equipamentos/<int:drone_id>/manutencao/pdf", methods=["GET"], endpoint="equipamento_manutencao_pdf")
    @login_required
    def equipamento_manutencao_pdf(drone_id):
        _require_admin_or_operario()
        drone = _get_scoped_drone_or_404(drone_id)
        usos = list_pecas_usadas_manutencao(drone, user=current_user)
        try:
            path = build_manutencao_pdf(drone, usos, manutencao=get_manutencao_aberta(drone, user=current_user))
            filename = f"manutencao_{drone.renomacao or drone.id}.pdf".replace("/", "-").replace("\\", "-")
            return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)
        except Exception:
            current_app.logger.exception("Erro ao gerar PDF de manutencao do drone %s.", drone.id)
            flash("Erro ao gerar o PDF da manutencao.", "danger")
            return redirect(url_for("main.equipamentos_manutencao"))

    @bp.route("/equipamentos/manutencoes/<int:manutencao_id>/pdf", methods=["GET"], endpoint="equipamento_manutencao_historico_pdf")
    @login_required
    def equipamento_manutencao_historico_pdf(manutencao_id):
        _require_admin_or_operario()
        manutencao = get_manutencao_scoped_or_404(manutencao_id, current_user)
        try:
            path = build_manutencao_pdf(manutencao.drone, manutencao.pecas_usadas, manutencao=manutencao)
            filename = f"manutencao_{manutencao.id}_{manutencao.drone.renomacao or manutencao.drone_id}.pdf".replace("/", "-").replace("\\", "-")
            return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)
        except Exception:
            current_app.logger.exception("Erro ao gerar PDF da manutencao %s.", manutencao.id)
            flash("Erro ao gerar o PDF da manutencao.", "danger")
            return redirect(url_for("main.equipamentos_manutencoes_historico"))

    @bp.route("/equipamentos/<int:drone_id>/manutencao/encerrar", methods=["POST"], endpoint="equipamento_manutencao_encerrar")
    @login_required
    def equipamento_manutencao_encerrar(drone_id):
        _require_admin_or_operario()
        drone = _get_scoped_drone_or_404(drone_id)
        try:
            if not encerrar_manutencao_drone(drone, user=current_user):
                flash("Este drone nao esta em manutencao.", "warning")
            else:
                flash(f"Manutencao do drone {drone.renomacao} encerrada com sucesso.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao encerrar manutencao do drone %s.", drone.id)
            flash("Erro ao encerrar a manutencao.", "danger")
        return redirect(url_for("main.equipamentos_manutencao"))

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
            if not send_drone_to_manutencao(drone, user=current_user):
                flash("Este drone ja esta em manutencao.", "warning")
                return redirect(url_for("main.listar_drones"))

            flash(f"Drone {drone.renomacao} enviado para manutencao.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao enviar drone %s para manutencao.", drone.id)
            flash("Erro ao enviar o drone para manutencao.", "danger")

        return redirect(url_for("main.listar_drones"))
