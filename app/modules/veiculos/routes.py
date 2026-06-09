from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Veiculos
from app.modules.veiculos.service import (
    VEICULOS_ALLOWED_TYPES,
    VEICULOS_LOGS_ALLOWED_TYPES,
    VeiculoTurnoError,
    build_veiculo_form,
    build_piloto_veiculos_context,
    build_veiculos_export_response,
    build_veiculos_logs_export,
    create_veiculo,
    delete_veiculo,
    encerrar_turno_piloto,
    EQUIPE_OCEANO_USER_TYPE,
    iniciar_turno_piloto,
    list_equipes_choices,
    list_veiculos,
    list_veiculos_logs,
    list_responsaveis_choices,
    registrar_abastecimento_turno_piloto,
    update_veiculo,
    validate_veiculo_form,
)
from app.shared.access import apply_prefeitura_scope, normalize_role


def _require_admin_or_operario():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "admin", "operario", "operador", "prefeitura_admin"}:
        abort(403)


def _require_piloto():
    if getattr(current_user, "tipo_usuario", None) not in {"piloto", EQUIPE_OCEANO_USER_TYPE}:
        abort(403)


def _get_scoped_veiculo_or_404(veiculo_id: int):
    query = apply_prefeitura_scope(Veiculos.query, current_user, Veiculos.prefeitura_id)
    return query.filter(Veiculos.id == veiculo_id).first_or_404()


def register_routes(bp):
    @bp.route("/veiculos/menu", methods=["GET"], endpoint="veiculos_menu")
    @login_required
    def veiculos_menu():
        tipo = normalize_role(getattr(current_user, "tipo_usuario", None))
        if tipo not in VEICULOS_ALLOWED_TYPES:
            abort(403)

        return render_template(
            "veiculos_menu.html",
            can_manage=tipo in {"dev", "admin", "operario", "operador", "prefeitura_admin"},
            can_view_logs=tipo in VEICULOS_LOGS_ALLOWED_TYPES,
            can_view_checklist=tipo in {"dev", "admin"},
        )

    @bp.route("/veiculos", methods=["GET"], endpoint="listar_veiculos")
    @login_required
    def listar_veiculos_view():
        tipo = getattr(current_user, "tipo_usuario", None)
        export = (request.args.get("export") or "").strip()

        try:
            if export in ("1", "true", "yes", "xlsx"):
                return build_veiculos_export_response(tipo, request.args, user=current_user)
            return render_template("veiculos_listar.html", **list_veiculos(tipo, request.args, user=current_user))
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/logs", methods=["GET"], endpoint="veiculos_logs")
    @login_required
    def veiculos_logs_view():
        tipo = getattr(current_user, "tipo_usuario", None)
        try:
            return render_template("veiculos_logs.html", **list_veiculos_logs(tipo, request.args, user=current_user))
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/logs/exportar", methods=["GET"], endpoint="exportar_logs_veiculos_xlsx")
    @login_required
    def exportar_logs_veiculos_xlsx():
        tipo = getattr(current_user, "tipo_usuario", None)
        try:
            return build_veiculos_logs_export(tipo, request.args, user=current_user)
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_veiculo")
    @login_required
    def cadastrar_veiculo():
        _require_admin_or_operario()

        errors = {}
        form = {}
        responsaveis = list_responsaveis_choices(user=current_user)
        equipes = list_equipes_choices(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_veiculo_form(
                request.form,
                responsaveis=responsaveis,
                equipes=equipes,
            )

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "cadastrar_veiculo.html",
                    form=form,
                    errors=errors,
                    responsaveis=responsaveis,
                    equipes=equipes,
                )

            try:
                create_veiculo(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None))
                flash("Veículo cadastrado com sucesso!", "success")
                return redirect(url_for("main.listar_veiculos"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar veiculo.")
                flash("Erro interno ao cadastrar o veiculo. Tente novamente.", "danger")
                return render_template(
                    "cadastrar_veiculo.html",
                    form=form,
                    errors=errors,
                    responsaveis=responsaveis,
                    equipes=equipes,
                )

        return render_template(
            "cadastrar_veiculo.html",
            form=form,
            errors=errors,
            responsaveis=responsaveis,
            equipes=equipes,
        )

    @bp.route("/veiculos/<int:veiculo_id>/editar", methods=["GET", "POST"], endpoint="editar_veiculo")
    @login_required
    def editar_veiculo(veiculo_id):
        _require_admin_or_operario()

        veiculo = _get_scoped_veiculo_or_404(veiculo_id)
        errors = {}
        responsaveis = list_responsaveis_choices(user=current_user)
        equipes = list_equipes_choices(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_veiculo_form(
                request.form,
                responsaveis=responsaveis,
                equipes=equipes,
                existing_veiculo=veiculo,
            )

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "cadastrar_veiculo.html",
                    form=form,
                    errors=errors,
                    veiculo=veiculo,
                    responsaveis=responsaveis,
                    equipes=equipes,
                )

            try:
                update_veiculo(veiculo, cleaned)
                flash("Veículo atualizado!", "success")
                return redirect(url_for("main.listar_veiculos"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar veiculo %s.", veiculo.id)
                flash("Erro interno ao atualizar o veiculo. Tente novamente.", "danger")
                return render_template(
                    "cadastrar_veiculo.html",
                    form=form,
                    errors=errors,
                    veiculo=veiculo,
                    responsaveis=responsaveis,
                    equipes=equipes,
                )

        return render_template(
            "cadastrar_veiculo.html",
            form=build_veiculo_form(veiculo),
            errors=errors,
            veiculo=veiculo,
            responsaveis=responsaveis,
            equipes=equipes,
        )

    @bp.route("/veiculos/<int:veiculo_id>/deletar", methods=["POST"], endpoint="deletar_veiculo")
    @login_required
    def deletar_veiculo_view(veiculo_id):
        _require_admin_or_operario()

        veiculo = _get_scoped_veiculo_or_404(veiculo_id)
        try:
            delete_veiculo(veiculo)
            flash("Veículo removido!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover veiculo %s.", veiculo.id)
            flash("Erro interno ao remover o veiculo. Tente novamente.", "danger")

        return redirect(url_for("main.listar_veiculos"))

    @bp.route("/piloto/veiculos", methods=["GET"], endpoint="piloto_veiculos")
    @login_required
    def piloto_veiculos():
        _require_piloto()

        context = build_piloto_veiculos_context(current_user)
        if not context["piloto_vinculado"]:
            flash("Seu usuário piloto está sem vínculo completo. Contate o administrador.", "warning")

        return render_template(
            "piloto_veiculos.html",
            veiculos=context["veiculos"],
            turnos_abertos=context["turnos_abertos"],
        )

    @bp.route("/piloto/veiculos/<int:veiculo_id>/km", methods=["POST"], endpoint="piloto_atualizar_km_veiculo")
    @login_required
    def piloto_atualizar_km_veiculo(veiculo_id):
        _require_piloto()

        try:
            flash(
                iniciar_turno_piloto(
                    current_user,
                    veiculo_id,
                    request.form,
                    request.files,
                    current_app.root_path,
                ),
                "success",
            )
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro tecnico ao iniciar turno de veiculo.")
            flash("Erro tecnico ao salvar.", "danger")

        return redirect(url_for("main.piloto_veiculos"))

    @bp.route(
        "/piloto/veiculos/<int:veiculo_id>/abastecimento",
        methods=["POST"],
        endpoint="piloto_registrar_abastecimento_turno",
    )
    @login_required
    def piloto_registrar_abastecimento_turno(veiculo_id):
        _require_piloto()

        try:
            flash(
                registrar_abastecimento_turno_piloto(
                    current_user,
                    veiculo_id,
                    request.form,
                    request.files,
                    current_app.root_path,
                ),
                "success",
            )
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro tecnico ao registrar abastecimento do turno.")
            flash("Erro tecnico ao registrar abastecimento.", "danger")

        return redirect(url_for("main.piloto_veiculos"))

    @bp.route("/piloto/veiculos/<int:veiculo_id>/encerrar", methods=["POST"], endpoint="piloto_encerrar_turno")
    @login_required
    def piloto_encerrar_turno(veiculo_id):
        _require_piloto()

        try:
            flash(encerrar_turno_piloto(current_user, veiculo_id, request.form), "success")
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro tecnico ao encerrar turno de veiculo.")
            flash("Erro tecnico ao salvar.", "danger")

        return redirect(url_for("main.piloto_veiculos"))
