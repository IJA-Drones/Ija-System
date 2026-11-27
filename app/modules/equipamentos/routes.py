from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.equipamentos.exporters import XLSX_MIME, build_manutencao_pdf, build_manutencoes_excel, build_pecas_usadas_excel
from app.shared.skybox import SkyboxError, stream_skybox_file
from app.models import Baterias, BateriaAtualizacao, Drones, ManutencaoEquipamento, Veiculos
from app.modules.equipamentos.checklist_notificacoes import checklist_defects, visible_vehicle_checklists
from app.modules.equipamentos.service import (
    MANUTENCAO_STATUS_ALIASES,
    build_bateria_edit_form,
    build_drone_edit_form,
    can_open_maintenance_os,
    create_bateria,
    create_drone,
    delete_bateria,
    delete_drone,
    equipment_team_assignments,
    get_manutencao_aberta,
    get_manutencao_scoped_or_404,
    list_active_equipes,
    list_baterias,
    list_drones,
    list_drones_for_baterias,
    list_equipamentos_dashboard,
    list_equipamentos_manutencao,
    maintenance_equipment_key,
    maintenance_legacy_access,
    maintenance_overview,
    maintenance_vehicles_query,
    list_historico_manutencoes,
    list_historico_pecas_usadas,
    list_imagens_manutencao,
    list_pecas_usadas_manutencao,
    open_equipment_maintenance,
    scope_maintenance_records,
    send_drone_to_manutencao,
    update_bateria,
    update_bateria_ciclos,
    update_drone,
    validate_bateria_form,
    validate_drone_form,
)
from app.shared.access import apply_prefeitura_scope, is_veiculos_supervisor, normalize_role
from app.shared.equipment_models import equipment_model_key
from app.modules.equipamentos.manutencao import (
    build_manutencao_form, salvar_atendimento_manutencao,
    CONDICOES_CHEGADA, CONDICOES_FINAIS, TIPOS_MANUTENCAO,
)
from app.modules.equipamentos.service import list_pecas_compativeis_manutencao


def _require_admin_or_operario():
    if not route_access(current_user, normalize_role(getattr(current_user, 'tipo_usuario', None)) in {'dev', 'diretor', 'admin', 'operario', 'operador', 'prefeitura_admin'} or is_veiculos_supervisor(current_user)):
        abort(403)


def _require_maintenance_access():
    if not route_access(current_user, maintenance_legacy_access(current_user)):
        abort(403)


# Product illustrations from DJI's product support pages.
_MAINTENANCE_MODEL_IMAGES = {
    "agrast10": "agras-t10",
    "agrast25": "agras-t25",
    "agrast25p": "agras-t25p",
    "m4": "matrice-4",
    "m4e": "matrice-4",
    "m4t": "matrice-4",
    "m30": "matrice-30",
    "m30t": "matrice-30",
    "m300": "matrice-300",
    "m300rtk": "matrice-300",
    "m350": "matrice-350",
    "m350rtk": "matrice-350",
    "m400": "matrice-400",
}


def _maintenance_model_image(model):
    key = equipment_model_key(model).removeprefix("dji ")
    key = "".join(key.replace("-", " ").split())
    if key.startswith("matrice"):
        key = "m" + key.removeprefix("matrice").removeprefix("m")
    image = _MAINTENANCE_MODEL_IMAGES.get(key)
    return f"img/equipamentos/{image}.png" if image else None


def _get_scoped_drone_or_404(drone_id: int):
    query = apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id)
    return query.filter(Drones.id == drone_id).first_or_404()


def _maintenance_id(data, key):
    if not data.get(key):
        return None
    value = data.get(key, type=int)
    if value is None or not 0 < value <= 2_147_483_647:
        abort(404)
    return value


def _get_scoped_maintenance_equipment_or_404(equipment_id):
    drones = apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id)
    drone = drones.filter(Drones.id == equipment_id).first()
    if drone:
        return drone
    return maintenance_vehicles_query(current_user).filter(Veiculos.id == equipment_id).first_or_404()


def _selected_maintenance_equipment(data):
    equipment_id = _maintenance_id(data, "equipamento_id")
    if equipment_id:
        return _get_scoped_maintenance_equipment_or_404(equipment_id)
    drone_id = _maintenance_id(data, "drone_id")
    return _get_scoped_drone_or_404(drone_id) if drone_id else None


def _maintenance_vehicle_choices():
    return maintenance_vehicles_query(current_user).order_by(Veiculos.placa, Veiculos.id).all()


def _maintenance_history(equipment):
    filters = {maintenance_equipment_key(equipment): equipment.id} if equipment else {}
    return list_historico_manutencoes(user=current_user, **filters)


def _get_scoped_bateria_or_404(bateria_id: int):
    query = apply_prefeitura_scope(Baterias.query, current_user, Baterias.prefeitura_id)
    return query.filter(Baterias.id == bateria_id).first_or_404()


def register_routes(bp):
    from app.modules.equipamentos.controles_routes import register_controle_routes
    register_controle_routes(bp)
    from app.modules.equipamentos.preventivas import register_preventiva_routes
    register_preventiva_routes(bp)

    @bp.route("/equipamentos", methods=["GET"], endpoint="listar_equipamentos")
    @login_required
    def listar_equipamentos():
        q = request.args.get("q", "").strip()
        return render_template(
            "equipamentos_listar.html", q=q,
            **list_equipamentos_dashboard(user=current_user, q=q),
        )

    @bp.route("/equipamentos/drones", methods=["GET"], endpoint="listar_drones")
    @login_required
    def listar_drones_view():
        drones = list_drones(user=current_user, q=request.args.get("q"))
        from app.modules.equipamentos.controles import list_controles
        controles_por_drone = {}
        for controle in list_controles(current_user):
            controles_por_drone.setdefault(controle.drone_id, []).append(controle)
        tipo_usuario = normalize_role(getattr(current_user, "tipo_usuario", None))
        return render_template(
            "drones_listar.html",
            controles_por_drone=controles_por_drone,
            drones=drones,
            responsabilidades=equipment_team_assignments(drones, user=current_user),
            q=request.args.get("q", "").strip(),
            can_open_os=can_open_maintenance_os(current_user),
            can_view_history=can_access_endpoint(current_user, "main.equipamentos_manutencoes_historico", legacy=maintenance_legacy_access(current_user)),
            is_admin=tipo_usuario in {"dev", "diretor", "admin"} or is_veiculos_supervisor(current_user),
            can_manage=tipo_usuario in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"} or is_veiculos_supervisor(current_user),
        )

    @bp.route("/equipamentos/baterias", methods=["GET"], endpoint="listar_baterias")
    @login_required
    def listar_baterias_view():
        from app.modules.equipamentos.baterias import battery_inventory
        filters = {key: request.args.get(key, "").strip() for key in (
            "q", "familia", "drone_id", "equipe_id", "responsavel_id", "veiculo_id", "status", "vinculo", "page")}
        legacy = normalize_role(current_user.tipo_usuario) in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin", "manutencao"} or is_veiculos_supervisor(current_user)
        return render_template("baterias_listar.html", filters=filters, q=filters["q"],
            filter_args={key:value for key,value in filters.items() if value and key!="page"},
            can_create=can_access_endpoint(current_user, "main.cadastrar_bateria", legacy=legacy),
            **battery_inventory(current_user, filters))

    @bp.route("/equipamentos/baterias/<int:bateria_id>", methods=["GET"], endpoint="bateria_detalhe")
    @login_required
    def bateria_detalhe(bateria_id):
        from app.modules.equipamentos.baterias import FIELD_LABELS
        bateria = _get_scoped_bateria_or_404(bateria_id)
        return render_template("bateria_detalhe.html", bateria=bateria,
            responsabilidades=equipment_team_assignments([bateria], user=current_user),
            historico=BateriaAtualizacao.query.filter_by(bateria_id=bateria.id).order_by(
                BateriaAtualizacao.criado_em.desc(), BateriaAtualizacao.id.desc()).limit(100).all(),
            field_labels=FIELD_LABELS,
            can_edit=can_access_endpoint(current_user, "main.editar_bateria", legacy=maintenance_legacy_access(current_user)))

    @bp.route("/baterias/<int:bateria_id>/conferir", methods=["POST"], endpoint="bateria_conferir")
    @login_required
    def bateria_conferir(bateria_id):
        _require_admin_or_operario()
        from app.modules.equipamentos.baterias import battery_snapshot, record_battery_update
        bateria = _get_scoped_bateria_or_404(bateria_id)
        try:
            record_battery_update(bateria, user=current_user, before=battery_snapshot(bateria), tipo="conferencia")
            db.session.commit()
            flash("Conferência do cadastro registrada. A leitura de ciclos não foi alterada.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")
        return redirect(url_for("main.bateria_detalhe", bateria_id=bateria.id))

    @bp.route("/baterias/<int:bateria_id>/ciclos", methods=["POST"], endpoint="bateria_registrar_ciclos")
    @login_required
    def bateria_registrar_ciclos(bateria_id):
        _require_admin_or_operario()
        bateria = _get_scoped_bateria_or_404(bateria_id)
        try:
            update_bateria_ciclos(bateria, {"operacao": "definir", "quantidade": request.form.get("ciclo", "")}, user=current_user)
            flash("Leitura manual de ciclos registrada.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")
        return redirect(url_for("main.bateria_detalhe", bateria_id=bateria.id))

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
                create_bateria(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None), user=current_user)
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
                update_bateria(bateria, cleaned, user=current_user)
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
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover bateria %s.", bateria.id)
            flash("Erro interno ao remover a bateria. Tente novamente.", "danger")

        return redirect(url_for("main.listar_baterias"))

    @bp.route("/equipamentos/manutencoes/nova", methods=["GET", "POST"], endpoint="equipamento_manutencao_nova")
    @login_required
    def equipamento_manutencao_nova():
        _require_maintenance_access()
        data = request.form if request.method == "POST" else request.args
        form = data.to_dict()
        equipment = _selected_maintenance_equipment(data)
        checklist = None
        checklist_id = _maintenance_id(data, "checklist_veiculo_id")
        if checklist_id:
            checklist = visible_vehicle_checklists(current_user).filter_by(id=checklist_id).first_or_404()
            if equipment and equipment.id != checklist.veiculo_id:
                abort(404)
            equipment = checklist.veiculo
            defects, report = checklist_defects(checklist)
            if not defects:
                flash("O checklist foi atualizado e está sem pendências.", "info")
                return redirect(url_for("main.equipamento_manutencao_nova", equipamento_id=equipment.id))
            if request.method == "GET":
                form.update(avarias_identificadas=report, tipo_manutencao="corretiva")
        if equipment:
            form["equipamento_id"] = equipment.id
        errors = {}
        if request.method == "GET" and form.get("tipo_manutencao") == "preventiva":
            form.setdefault("avarias_identificadas", "Manutenção preventiva programada.")
        if request.method == "POST":
            if equipment is None:
                errors["equipamento_id"] = "Selecione o drone ou veículo."
            report = form.get("avarias_identificadas", "").strip()
            if not report:
                errors["avarias_identificadas"] = "Informe o motivo da manutenção."
            elif len(report) > 20000:
                errors["avarias_identificadas"] = "Use até 20.000 caracteres."
            if len(form.get("responsavel_manutencao", "").strip()) > 120:
                errors["responsavel_manutencao"] = "Use até 120 caracteres."
            if form.get("tipo_manutencao") and form["tipo_manutencao"] not in TIPOS_MANUTENCAO:
                errors["tipo_manutencao"] = "Selecione um tipo de manutenção válido."
            if not errors:
                try:
                    manutencao, opened = open_equipment_maintenance(
                        equipment, user=current_user, form_data=form, checklist=checklist,
                    )
                    if manutencao and manutencao.status == "encerrada":
                        flash("Este checklist já tem uma OS concluída.", "info")
                        return redirect(url_for("main.equipamento_manutencao_detalhe", manutencao_id=manutencao.id))
                    if not opened:
                        flash("Este equipamento já está em manutenção. Continue na OS existente.", "warning")
                    elif manutencao:
                        flash(f"OS de manutenção {manutencao.numero_os} aberta com sucesso.", "success")
                    return redirect(url_for("main.equipamento_manutencao_pecas", drone_id=equipment.id))
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Erro ao abrir OS de manutenção.")
                    flash("Não foi possível abrir a OS de manutenção. Tente novamente.", "danger")
        drones = [] if checklist else list_drones(user=current_user)
        vehicles = [equipment] if checklist else _maintenance_vehicle_choices()
        return render_template(
            "equipamento_manutencao_nova.html",
            drones=drones,
            veiculos=vehicles,
            checklist=checklist,
            form=form,
            errors=errors,
            tipos_manutencao=TIPOS_MANUTENCAO,
            alocacoes=equipment_team_assignments(drones + vehicles, user=current_user),
            fotos_modelo={drone.id: _maintenance_model_image(drone.modelo) for drone in drones},
        )

    @bp.route("/equipamentos/em-manutencao", methods=["GET"], endpoint="equipamentos_manutencao")
    @login_required
    def equipamentos_manutencao():
        equipamentos = list_equipamentos_manutencao(user=current_user)
        total = len(equipamentos)
        busca = (request.args.get('q') or '').strip()
        if busca:
            term = busca.casefold()
            equipamentos = [eq for eq in equipamentos if term in ' '.join(str(value or '') for value in (
                eq.renomacao, eq.modelo, eq.numero_serie, getattr(eq, "placa", None),
                eq.equipe.nome_equipe if eq.equipe else '',
            )).casefold()]
        manutencoes = scope_maintenance_records(
            ManutencaoEquipamento.query.filter_by(status="aberta"), ManutencaoEquipamento, current_user,
        ).order_by(ManutencaoEquipamento.aberta_em.asc()).all()
        return render_template(
            "equipamentos_manutencao.html",
            equipamentos=equipamentos,
            total=total, busca=busca, resumo=maintenance_overview(current_user),
            manutencoes_por_equipamento={(m.veiculo_id or m.drone_id): m for m in manutencoes},
            can_open_os=can_open_maintenance_os(current_user),
        )

    @bp.route("/equipamentos/manutencoes/historico", methods=["GET"], endpoint="equipamentos_manutencoes_historico")
    @login_required
    def equipamentos_manutencoes_historico():
        _require_maintenance_access()
        equipment = _selected_maintenance_equipment(request.args)
        return render_template(
            "equipamentos_manutencoes_historico.html",
            manutencoes=_maintenance_history(equipment),
            drones=list_drones(user=current_user),
            veiculos=_maintenance_vehicle_choices(),
            equipamento_selecionado=equipment,
        )

    @bp.route("/equipamentos/manutencoes/historico/excel", methods=["GET"], endpoint="equipamentos_manutencoes_historico_excel")
    @login_required
    def equipamentos_manutencoes_historico_excel():
        _require_maintenance_access()
        equipment = _selected_maintenance_equipment(request.args)
        output, filename = build_manutencoes_excel(_maintenance_history(equipment))
        return send_file(output, mimetype=XLSX_MIME, as_attachment=True, download_name=filename)

    @bp.route("/equipamentos/manutencoes/pecas/historico", methods=["GET"], endpoint="equipamentos_manutencoes_pecas_historico")
    @login_required
    def equipamentos_manutencoes_pecas_historico():
        _require_maintenance_access()
        return render_template(
            "equipamentos_manutencoes_pecas_historico.html",
            usos=list_historico_pecas_usadas(user=current_user),
        )

    @bp.route("/equipamentos/manutencoes/pecas/historico/excel", methods=["GET"], endpoint="equipamentos_manutencoes_pecas_historico_excel")
    @login_required
    def equipamentos_manutencoes_pecas_historico_excel():
        _require_maintenance_access()
        output, filename = build_pecas_usadas_excel(list_historico_pecas_usadas(user=current_user))
        return send_file(output, mimetype=XLSX_MIME, as_attachment=True, download_name=filename)

    @bp.route("/equipamentos/manutencoes/<int:manutencao_id>", methods=["GET"], endpoint="equipamento_manutencao_detalhe")
    @login_required
    def equipamento_manutencao_detalhe(manutencao_id):
        _require_maintenance_access()
        manutencao = get_manutencao_scoped_or_404(manutencao_id, current_user)
        return render_template(
            "equipamento_manutencao_detalhe.html",
            manutencao=manutencao,
            imagens_manutencao=list_imagens_manutencao(manutencao),
            usos=manutencao.pecas_usadas,
            condicoes_chegada=CONDICOES_CHEGADA, condicoes_finais=CONDICOES_FINAIS, tipos_manutencao=TIPOS_MANUTENCAO,
        )

    @bp.route("/equipamentos/<int:drone_id>/manutencao/pecas", methods=["GET", "POST"], endpoint="equipamento_manutencao_pecas")
    @login_required
    def equipamento_manutencao_pecas(drone_id):
        _require_maintenance_access()
        equipment = _get_scoped_maintenance_equipment_or_404(drone_id)

        if request.method == "POST" and request.form.get("manutencao_id", type=int):
            submitted = get_manutencao_scoped_or_404(request.form.get("manutencao_id", type=int), current_user)
            if getattr(submitted, maintenance_equipment_key(equipment)) != equipment.id:
                abort(404)
            if submitted.status == "encerrada":
                flash("Esta OS já foi concluída. O estoque não foi descontado novamente.", "info")
                return redirect(url_for("main.equipamento_manutencao_detalhe", manutencao_id=submitted.id))

        if (equipment.status or "").strip() not in MANUTENCAO_STATUS_ALIASES:
            flash("Este equipamento está fora da manutenção.", "warning")
            return redirect(url_for("main.equipamentos_manutencao"))

        errors = {}
        if request.method == "POST":
            try:
                order, errors = salvar_atendimento_manutencao(
                    equipment, request.form, user=current_user, files_data=request.files
                )
                if not errors:
                    if order.status == "encerrada":
                        flash("OS concluída. Estoque e histórico do equipamento atualizados.", "success")
                        return redirect(url_for("main.equipamento_manutencao_detalhe", manutencao_id=order.id))
                    flash("Rascunho salvo. Nenhuma peça foi descontada do estoque.", "success")
                    return redirect(url_for("main.equipamento_manutencao_pecas", drone_id=equipment.id))
                flash("Corrija os campos destacados.", "warning")
            except (ValueError, SkyboxError) as exc:
                db.session.rollback()
                errors["geral"] = str(exc)
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao salvar OS de manutenção do equipamento %s.", equipment.id)
                errors["geral"] = "Não foi possível salvar a OS. Suas alterações continuam no formulário; tente novamente."

        manutencao = get_manutencao_aberta(equipment, user=current_user)
        catalog = list_pecas_compativeis_manutencao(equipment, user=current_user)
        form = build_manutencao_form(manutencao, request.form if request.method == "POST" else None)
        if isinstance(equipment, Veiculos) and not manutencao and request.method == "GET":
            form["km_recebimento"] = equipment.km_atual
        return render_template(
            "equipamento_manutencao_pecas.html",
            equipamento=equipment,
            manutencao=manutencao,
            imagens_manutencao=list_imagens_manutencao(manutencao),
            pecas=catalog,
            reenviar_imagens=bool(errors and request.files.getlist("imagens_ocorrido")),
            catalogo_pecas=[dict(id=p.id, nome=p.modelo_peca, codigo=p.codigo_dji or "", serie=p.numero_serie or "",
                                saldo=p.quantidade, disponivel=p.status == "disponivel_manutencao") for p in catalog],
            form=form,
            condicoes_chegada=CONDICOES_CHEGADA, condicoes_finais=CONDICOES_FINAIS, tipos_manutencao=TIPOS_MANUTENCAO,
            alocacao=equipment_team_assignments([equipment], user=current_user).get(equipment.id, {}),
            foto_modelo=_maintenance_model_image(equipment.modelo) if isinstance(equipment, Drones) else None,
            usos=list_pecas_usadas_manutencao(equipment, user=current_user),
            errors=errors,
        )

    @bp.route(
        "/equipamentos/manutencoes/<int:manutencao_id>/imagens/<int:index>",
        methods=["GET"], endpoint="equipamento_manutencao_imagem",
    )
    @login_required
    def equipamento_manutencao_imagem(manutencao_id, index):
        _require_maintenance_access()
        manutencao = get_manutencao_scoped_or_404(manutencao_id, current_user)
        images = list_imagens_manutencao(manutencao)
        if index < 0 or index >= len(images):
            abort(404)
        try:
            response = stream_skybox_file(images[index], request.headers.get("Range"))
        except SkyboxError:
            current_app.logger.exception(
                "Erro ao carregar imagem da manutencao %s no Skybox.", manutencao_id
            )
            abort(404)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/equipamentos/<int:drone_id>/manutencao/pdf", methods=["GET"], endpoint="equipamento_manutencao_pdf")
    @login_required
    def equipamento_manutencao_pdf(drone_id):
        _require_maintenance_access()
        equipment = _get_scoped_maintenance_equipment_or_404(drone_id)
        usos = list_pecas_usadas_manutencao(equipment, user=current_user)
        try:
            path = build_manutencao_pdf(equipment, usos, manutencao=get_manutencao_aberta(equipment, user=current_user))
            filename = f"manutencao_{equipment.renomacao or equipment.id}.pdf".replace("/", "-").replace("\\", "-")
            return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)
        except Exception:
            current_app.logger.exception("Erro ao gerar PDF de manutenção do equipamento %s.", equipment.id)
            flash("Erro ao gerar o PDF da manutencao.", "danger")
            return redirect(url_for("main.equipamentos_manutencao"))

    @bp.route("/equipamentos/manutencoes/<int:manutencao_id>/pdf", methods=["GET"], endpoint="equipamento_manutencao_historico_pdf")
    @login_required
    def equipamento_manutencao_historico_pdf(manutencao_id):
        _require_maintenance_access()
        manutencao = get_manutencao_scoped_or_404(manutencao_id, current_user)
        try:
            equipment = manutencao.equipamento
            path = build_manutencao_pdf(equipment, manutencao.pecas_usadas, manutencao=manutencao)
            filename = f"manutencao_{manutencao.id}_{equipment.renomacao or equipment.id}.pdf".replace("/", "-").replace("\\", "-")
            return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)
        except Exception:
            current_app.logger.exception("Erro ao gerar PDF da manutencao %s.", manutencao.id)
            flash("Erro ao gerar o PDF da manutencao.", "danger")
            return redirect(url_for("main.equipamentos_manutencoes_historico"))

    @bp.route("/equipamentos/<int:drone_id>/manutencao/encerrar", methods=["POST"], endpoint="equipamento_manutencao_encerrar")
    @login_required
    def equipamento_manutencao_encerrar(drone_id):
        _require_maintenance_access()
        equipment = _get_scoped_maintenance_equipment_or_404(drone_id)
        # Old bookmarked forms cannot finalize a newer OS for the equipment.
        # All completion data and the expected worksheet version go through the
        # unified page, which is also where stock movements are validated.
        flash("Confira os dados e conclua a OS na página de atendimento.", "info")
        return redirect(url_for("main.equipamento_manutencao_pecas", drone_id=equipment.id))

    @bp.route("/equipamentos/baterias/update_ciclos/<int:id>", methods=["POST"], endpoint="update_ciclos")
    @login_required
    def update_ciclos(id):
        _require_admin_or_operario()
        bateria = _get_scoped_bateria_or_404(id)
        try:
            return jsonify(update_bateria_ciclos(bateria, request.get_json(silent=True), user=current_user))
        except ValueError as exc:
            db.session.rollback()
            return jsonify(error=str(exc)), 400

    @bp.route("/drones/<int:drone_id>/manutencao", methods=["POST"], endpoint="enviar_manutencao_drone")
    @login_required
    def enviar_manutencao_drone(drone_id):
        _require_maintenance_access()

        drone = _get_scoped_drone_or_404(drone_id)
        try:
            if not send_drone_to_manutencao(drone, user=current_user):
                flash("Este drone ja esta em manutencao.", "warning")
                return redirect(url_for("main.listar_drones"))

            manutencao = get_manutencao_aberta(drone, user=current_user)
            flash(f"OS de manutenção {manutencao.numero_os} aberta para o drone {drone.renomacao}.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao enviar drone %s para manutencao.", drone.id)
            flash("Erro ao enviar o drone para manutencao.", "danger")

        return redirect(url_for("main.listar_drones"))
