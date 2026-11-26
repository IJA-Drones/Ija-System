from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.equipamentos.exporters import XLSX_MIME, build_manutencao_pdf, build_manutencoes_excel, build_pecas_usadas_excel
from app.shared.skybox import SkyboxError, stream_skybox_file
from app.models import Baterias, Drones, ManutencaoEquipamento
from app.modules.equipamentos.service import (
    build_bateria_edit_form,
    build_drone_edit_form,
    create_bateria,
    create_drone,
    delete_bateria,
    delete_drone,
    encerrar_manutencao_drone,
    equipment_team_assignments,
    get_manutencao_aberta,
    get_manutencao_scoped_or_404,
    list_active_equipes,
    list_baterias,
    list_drones,
    list_drones_for_baterias,
    list_equipamentos_dashboard,
    list_equipamentos_manutencao,
    maintenance_overview,
    list_historico_manutencoes,
    list_historico_pecas_usadas,
    list_imagens_manutencao,
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
from app.shared.access import apply_prefeitura_scope, is_veiculos_supervisor, normalize_role


def _require_admin_or_operario():
    if not route_access(current_user, normalize_role(getattr(current_user, 'tipo_usuario', None)) in {'dev', 'diretor', 'admin', 'operario', 'operador', 'prefeitura_admin'} or is_veiculos_supervisor(current_user)):
        abort(403)


def _maintenance_legacy_access():
    return normalize_role(getattr(current_user, "tipo_usuario", None)) in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin", "manutencao"} or is_veiculos_supervisor(current_user)


def _require_maintenance_access():
    if not route_access(current_user, _maintenance_legacy_access()):
        abort(403)


def _get_scoped_drone_or_404(drone_id: int):
    query = apply_prefeitura_scope(Drones.query, current_user, Drones.prefeitura_id)
    return query.filter(Drones.id == drone_id).first_or_404()


def _get_scoped_bateria_or_404(bateria_id: int):
    query = apply_prefeitura_scope(Baterias.query, current_user, Baterias.prefeitura_id)
    return query.filter(Baterias.id == bateria_id).first_or_404()


def register_routes(bp):
    from app.modules.equipamentos.controles_routes import register_controle_routes
    register_controle_routes(bp)

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
            can_open_os=can_access_endpoint(current_user, "main.equipamento_manutencao_nova", legacy=_maintenance_legacy_access()),
            is_admin=tipo_usuario in {"dev", "diretor", "admin"} or is_veiculos_supervisor(current_user),
            can_manage=tipo_usuario in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"} or is_veiculos_supervisor(current_user),
        )

    @bp.route("/equipamentos/baterias", methods=["GET"], endpoint="listar_baterias")
    @login_required
    def listar_baterias_view():
        baterias = list_baterias(user=current_user, q=request.args.get("q"))
        tipo_usuario = normalize_role(getattr(current_user, "tipo_usuario", None))
        return render_template(
            "baterias_listar.html",
            baterias=baterias,
            responsabilidades=equipment_team_assignments(baterias, user=current_user),
            q=request.args.get("q", "").strip(),
            is_admin=tipo_usuario in {"dev", "diretor", "admin"} or is_veiculos_supervisor(current_user),
            can_manage=tipo_usuario in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"} or is_veiculos_supervisor(current_user),
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

    @bp.route("/equipamentos/manutencoes/nova", methods=["GET", "POST"], endpoint="equipamento_manutencao_nova")
    @login_required
    def equipamento_manutencao_nova():
        _require_maintenance_access()
        form = request.form if request.method == "POST" else request.args
        errors = {}
        if request.method == "POST":
            drone_id = request.form.get("drone_id", type=int)
            if drone_id is None:
                errors["drone_id"] = "Selecione o drone."
            if not (request.form.get("avarias_identificadas") or "").strip():
                errors["avarias_identificadas"] = "Informe o motivo da manutenção."
            if len(request.form.get("responsavel_manutencao", "").strip()) > 120:
                errors["responsavel_manutencao"] = "Use até 120 caracteres."
            drone = _get_scoped_drone_or_404(drone_id) if drone_id is not None else None
            if not errors:
                try:
                    opened = send_drone_to_manutencao(drone, user=current_user, form_data=request.form)
                    manutencao = get_manutencao_aberta(drone, user=current_user)
                    if not opened:
                        flash("Este drone já está em manutenção. Continue na OS existente.", "warning")
                    elif manutencao:
                        flash(f"OS de manutenção {manutencao.numero_os} aberta com sucesso.", "success")
                    return redirect(url_for("main.equipamento_manutencao_pecas", drone_id=drone.id))
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Erro ao abrir OS de manutenção.")
                    flash("Não foi possível abrir a OS de manutenção. Tente novamente.", "danger")
        return render_template("equipamento_manutencao_nova.html", drones=list_drones(user=current_user), form=form, errors=errors)

    @bp.route("/equipamentos/em-manutencao", methods=["GET"], endpoint="equipamentos_manutencao")
    @login_required
    def equipamentos_manutencao():
        equipamentos = list_equipamentos_manutencao(user=current_user)
        total = len(equipamentos)
        busca = (request.args.get('q') or '').strip()
        if busca:
            term = busca.casefold()
            equipamentos = [eq for eq in equipamentos if term in ' '.join(str(value or '') for value in (
                eq.renomacao, eq.modelo, eq.numero_serie, eq.equipe.nome_equipe if eq.equipe else '',
            )).casefold()]
        manutencoes = apply_prefeitura_scope(
            ManutencaoEquipamento.query.filter_by(status="aberta"), current_user, ManutencaoEquipamento.prefeitura_id
        ).order_by(ManutencaoEquipamento.aberta_em.asc()).all()
        return render_template(
            "equipamentos_manutencao.html",
            equipamentos=equipamentos,
            total=total, busca=busca, resumo=maintenance_overview(current_user),
            manutencoes_por_drone={m.drone_id: m for m in manutencoes},
            can_open_os=can_access_endpoint(current_user, "main.equipamento_manutencao_nova", legacy=_maintenance_legacy_access()),
        )

    @bp.route("/equipamentos/manutencoes/historico", methods=["GET"], endpoint="equipamentos_manutencoes_historico")
    @login_required
    def equipamentos_manutencoes_historico():
        _require_maintenance_access()
        return render_template(
            "equipamentos_manutencoes_historico.html",
            manutencoes=list_historico_manutencoes(user=current_user),
        )

    @bp.route("/equipamentos/manutencoes/historico/excel", methods=["GET"], endpoint="equipamentos_manutencoes_historico_excel")
    @login_required
    def equipamentos_manutencoes_historico_excel():
        _require_maintenance_access()
        output, filename = build_manutencoes_excel(list_historico_manutencoes(user=current_user))
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
        )

    @bp.route("/equipamentos/<int:drone_id>/manutencao/pecas", methods=["GET", "POST"], endpoint="equipamento_manutencao_pecas")
    @login_required
    def equipamento_manutencao_pecas(drone_id):
        _require_maintenance_access()
        drone = _get_scoped_drone_or_404(drone_id)

        if (drone.status or "").strip() not in {"Em Manutenção", "Manutenção", "Manutencao", "Em Manutencao"}:
            flash("Este drone nao esta em manutencao.", "warning")
            return redirect(url_for("main.equipamentos_manutencao"))

        errors = {}
        if request.method == "POST":
            try:
                usos, errors = registrar_pecas_usadas_manutencao(
                    drone, request.form, user=current_user, files_data=request.files
                )
                if not errors:
                    flash(f"Atendimento da OS de manutenção salvo: {len(usos)} peça(s) registrada(s).", "success")
                    return redirect(url_for("main.equipamentos_manutencao"))
                flash("Corrija os campos destacados.", "warning")
            except (ValueError, SkyboxError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao registrar pecas usadas na manutencao do drone %s.", drone.id)
                flash("Erro interno ao registrar as pecas usadas.", "danger")

        manutencao = get_manutencao_aberta(drone, user=current_user)
        return render_template(
            "equipamento_manutencao_pecas.html",
            drone=drone,
            manutencao=manutencao,
            imagens_manutencao=list_imagens_manutencao(manutencao),
            pecas=list_pecas_disponiveis_manutencao(drone, user=current_user),
            usos=list_pecas_usadas_manutencao(drone, user=current_user),
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
        _require_maintenance_access()
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
        _require_maintenance_access()
        drone = _get_scoped_drone_or_404(drone_id)
        try:
            if not encerrar_manutencao_drone(drone, user=current_user):
                flash("Este drone nao esta em manutencao.", "warning")
            else:
                flash(f"OS de manutenção do drone {drone.renomacao} encerrada com sucesso.", "success")
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
