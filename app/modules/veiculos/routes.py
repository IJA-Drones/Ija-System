import mimetypes
import os

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Veiculos
from app.modules.veiculos.service import (
    VEICULOS_ALLOWED_TYPES,
    VEICULOS_LOGS_ALLOWED_TYPES,
    VeiculoTurnoError,
    build_veiculo_form,
    build_veiculo_logs_detalhe_context,
    build_limpeza_alertas_admin_context,
    build_limpeza_alertas_operacionais_context,
    build_piloto_veiculos_context,
    build_veiculos_deleted_logs_context,
    build_veiculo_media_skybox_path,
    build_veiculos_export_response,
    build_veiculos_logs_export,
    create_veiculo,
    confirmar_alerta_limpeza_operacional,
    delete_veiculo_log,
    delete_veiculo,
    encerrar_turno_piloto,
    EQUIPE_OCEANO_USER_TYPE,
    iniciar_turno_piloto,
    get_abastecimento_for_media,
    get_veiculo_log_for_media,
    list_equipes_choices,
    list_veiculos,
    list_veiculos_limpezas,
    list_veiculos_logs,
    registrar_abastecimento_turno_piloto,
    registrar_limpeza_turno_piloto,
    update_veiculos_equipes,
    update_veiculo_log_km,
    update_veiculo,
    validate_veiculo_form,
)
from app.shared.access import apply_prefeitura_scope, normalize_role
from app.shared.skybox import SkyboxError, stream_skybox_file


def _require_admin_or_operario():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"}:
        abort(403)


def _require_admin():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "diretor", "admin"}:
        abort(403)


def _require_dev():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) != "dev":
        abort(403)


def _require_piloto():
    if getattr(current_user, "tipo_usuario", None) not in {"piloto", EQUIPE_OCEANO_USER_TYPE}:
        abort(403)


def _get_scoped_veiculo_or_404(veiculo_id: int):
    query = apply_prefeitura_scope(Veiculos.query, current_user, Veiculos.prefeitura_id)
    return query.filter(Veiculos.id == veiculo_id).first_or_404()


def _resolve_request_ip():
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip

    return request.remote_addr or None


def _send_local_veiculo_media(media_path):
    static_root = os.path.abspath(os.path.join(current_app.root_path, "static"))
    abs_path = os.path.abspath(os.path.join(static_root, str(media_path or "").replace("/", os.sep)))
    if os.path.commonpath([static_root, abs_path]) != static_root:
        abort(404)
    if not os.path.isfile(abs_path):
        abort(404)

    return send_file(
        abs_path,
        mimetype=mimetypes.guess_type(abs_path)[0] or "application/octet-stream",
        as_attachment=False,
        download_name=os.path.basename(abs_path),
        conditional=True,
    )


def _send_veiculo_media_from_skybox(media_path, placa):
    skybox_path = build_veiculo_media_skybox_path(media_path, placa)
    if not skybox_path:
        abort(404)

    try:
        return stream_skybox_file(skybox_path, request.headers.get("Range"))
    except SkyboxError:
        current_app.logger.info(
            "Falha ao servir midia de veiculo pelo Skybox. Usando arquivo local se existir.",
            exc_info=True,
        )
        return _send_local_veiculo_media(media_path)


def register_routes(bp):
    @bp.route("/veiculos/menu", methods=["GET"], endpoint="veiculos_menu")
    @login_required
    def veiculos_menu():
        tipo = normalize_role(getattr(current_user, "tipo_usuario", None))
        if tipo not in VEICULOS_ALLOWED_TYPES:
            abort(403)

        return render_template(
            "veiculos_menu.html",
            can_manage=tipo in {"dev", "diretor", "admin", "operario", "operador", "prefeitura_admin"},
            can_view_logs=tipo in VEICULOS_LOGS_ALLOWED_TYPES,
            can_view_checklist=tipo in {"dev", "diretor", "admin"},
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

    @bp.route("/veiculos/equipes", methods=["POST"], endpoint="atualizar_equipes_veiculos")
    @login_required
    def atualizar_equipes_veiculos():
        _require_admin_or_operario()

        redirect_args = {
            key: value
            for key, value in request.args.items()
            if key in {"q", "operacao", "frota", "status"}
        }
        try:
            flash(update_veiculos_equipes(current_user, request.form), "success")
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            db.session.rollback()
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao atualizar equipes dos veiculos em massa.")
            flash("Erro interno ao atualizar as equipes dos veiculos. Tente novamente.", "danger")

        return redirect(url_for("main.listar_veiculos", **redirect_args))

    @bp.route("/veiculos/logs", methods=["GET"], endpoint="veiculos_logs")
    @login_required
    def veiculos_logs_view():
        tipo = getattr(current_user, "tipo_usuario", None)
        try:
            return render_template("veiculos_logs.html", **list_veiculos_logs(tipo, request.args, user=current_user))
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/limpezas", methods=["GET"], endpoint="veiculos_limpezas")
    @login_required
    def veiculos_limpezas():
        tipo = getattr(current_user, "tipo_usuario", None)
        try:
            return render_template("veiculos_limpezas.html", **list_veiculos_limpezas(tipo, request.args, user=current_user))
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/limpeza/alertas", methods=["GET"], endpoint="veiculos_alertas_limpeza")
    @login_required
    def veiculos_alertas_limpeza():
        try:
            return render_template(
                "veiculos_alertas_limpeza.html",
                **build_limpeza_alertas_admin_context(current_user),
            )
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/logs/veiculo/<int:veiculo_id>", methods=["GET"], endpoint="veiculo_logs_detalhe")
    @login_required
    def veiculo_logs_detalhe(veiculo_id):
        tipo = getattr(current_user, "tipo_usuario", None)
        try:
            return render_template(
                "veiculo_logs_detalhe.html",
                **build_veiculo_logs_detalhe_context(tipo, veiculo_id, request.args, user=current_user),
            )
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

    @bp.route("/admin/veiculos/logs-excluidos", methods=["GET"], endpoint="veiculos_logs_excluidos")
    @login_required
    def veiculos_logs_excluidos():
        _require_dev()
        try:
            return render_template(
                "veiculos_logs_excluidos.html",
                **build_veiculos_deleted_logs_context(
                    getattr(current_user, "tipo_usuario", None),
                    request.args,
                ),
            )
        except PermissionError:
            abort(403)

    @bp.route("/veiculos/logs/<int:log_id>/corrigir-km", methods=["POST"], endpoint="corrigir_log_veiculo")
    @login_required
    def corrigir_log_veiculo(log_id):
        _require_admin_or_operario()

        redirect_args = {
            key: value
            for key, value in request.args.items()
            if key in {
                "page",
                "q",
                "data_inicio",
                "data_fim",
                "limpeza_realizada",
                "tipo_limpeza",
                "data_limpeza_inicio",
                "data_limpeza_fim",
                "valor_limpeza_min",
                "valor_limpeza_max",
            }
        }
        return_to = (request.args.get("return_to") or "").strip()
        veiculo_id = request.args.get("veiculo_id", type=int)
        try:
            flash(update_veiculo_log_km(current_user, log_id, request.form), "success")
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            db.session.rollback()
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao corrigir KM do log de veiculo %s.", log_id)
            flash("Erro interno ao corrigir o log de veiculo. Tente novamente.", "danger")

        if return_to == "veiculo" and veiculo_id:
            return redirect(
                url_for(
                    "main.veiculo_logs_detalhe",
                    veiculo_id=veiculo_id,
                    data_inicio=redirect_args.get("data_inicio"),
                    data_fim=redirect_args.get("data_fim"),
                )
            )
        return redirect(url_for("main.veiculos_logs", **redirect_args))

    @bp.route("/veiculos/logs/<int:log_id>/deletar", methods=["POST"], endpoint="deletar_log_veiculo")
    @login_required
    def deletar_log_veiculo(log_id):
        _require_admin()

        redirect_args = {
            key: value
            for key, value in request.args.items()
            if key in {
                "page",
                "q",
                "data_inicio",
                "data_fim",
                "limpeza_realizada",
                "tipo_limpeza",
                "data_limpeza_inicio",
                "data_limpeza_fim",
                "valor_limpeza_min",
                "valor_limpeza_max",
            }
        }
        try:
            flash(
                delete_veiculo_log(
                    current_user,
                    log_id,
                    request_info={
                        "path": request.path,
                        "ip": _resolve_request_ip(),
                        "user_agent": (request.headers.get("User-Agent") or "").strip() or None,
                        "referrer": (request.referrer or "").strip() or None,
                    },
                ),
                "success",
            )
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            db.session.rollback()
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao deletar log de veiculo %s.", log_id)
            flash("Erro interno ao deletar o log de veiculo. Tente novamente.", "danger")

        return redirect(url_for("main.veiculos_logs", **redirect_args))

    @bp.route("/veiculos/logs/<int:log_id>/midia/<tipo>", methods=["GET"], endpoint="veiculo_log_midia_skybox")
    @login_required
    def veiculo_log_midia_skybox(log_id, tipo):
        try:
            log = get_veiculo_log_for_media(current_user, log_id)
        except PermissionError:
            abort(403)
        if not log:
            abort(404)

        media_map = {
            "painel-inicial": log.foto_painel_path,
            "painel-final": getattr(log, "foto_painel_final_path", None),
        }
        media_path = media_map.get(tipo)
        if not media_path:
            abort(404)

        placa = log.veiculo.placa if log.veiculo else None
        return _send_veiculo_media_from_skybox(media_path, placa)

    @bp.route(
        "/veiculos/abastecimentos/<int:abastecimento_id>/midia/<tipo>",
        methods=["GET"],
        endpoint="veiculo_abastecimento_midia_skybox",
    )
    @login_required
    def veiculo_abastecimento_midia_skybox(abastecimento_id, tipo):
        try:
            abastecimento = get_abastecimento_for_media(current_user, abastecimento_id)
        except PermissionError:
            abort(403)
        if not abastecimento:
            abort(404)

        media_map = {
            "painel": getattr(abastecimento, "foto_painel_path", None),
            "nota": abastecimento.foto_nf_path,
        }
        media_path = media_map.get(tipo)
        if not media_path:
            abort(404)

        log = abastecimento.log_pai
        placa = log.veiculo.placa if log and log.veiculo else None
        return _send_veiculo_media_from_skybox(media_path, placa)

    @bp.route("/veiculos/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_veiculo")
    @login_required
    def cadastrar_veiculo():
        _require_admin_or_operario()

        errors = {}
        form = {}
        equipes = list_equipes_choices(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_veiculo_form(
                request.form,
                equipes=equipes,
            )

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "cadastrar_veiculo.html",
                    form=form,
                    errors=errors,
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
                    equipes=equipes,
                )

        return render_template(
            "cadastrar_veiculo.html",
            form=form,
            errors=errors,
            equipes=equipes,
        )

    @bp.route("/veiculos/<int:veiculo_id>/editar", methods=["GET", "POST"], endpoint="editar_veiculo")
    @login_required
    def editar_veiculo(veiculo_id):
        _require_admin_or_operario()

        veiculo = _get_scoped_veiculo_or_404(veiculo_id)
        errors = {}
        equipes = list_equipes_choices(user=current_user)

        if request.method == "POST":
            form, cleaned, errors = validate_veiculo_form(
                request.form,
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
                    equipes=equipes,
                )

        return render_template(
            "cadastrar_veiculo.html",
            form=build_veiculo_form(veiculo),
            errors=errors,
            veiculo=veiculo,
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
            km_inicial_referencias=context["km_inicial_referencias"],
            agora_brasilia=context["agora_brasilia"],
        )

    @bp.route("/piloto/caixa-entrada", methods=["GET"], endpoint="piloto_caixa_entrada")
    @login_required
    def piloto_caixa_entrada():
        _require_piloto()

        try:
            return render_template(
                "piloto_caixa_entrada.html",
                **build_limpeza_alertas_operacionais_context(current_user),
            )
        except PermissionError:
            abort(403)

    @bp.route(
        "/piloto/caixa-entrada/limpeza/<int:veiculo_id>/confirmar",
        methods=["POST"],
        endpoint="piloto_confirmar_alerta_limpeza",
    )
    @login_required
    def piloto_confirmar_alerta_limpeza(veiculo_id):
        _require_piloto()

        try:
            flash(confirmar_alerta_limpeza_operacional(current_user, veiculo_id), "success")
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            db.session.rollback()
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao confirmar ciencia de alerta de limpeza.")
            flash("Erro tecnico ao confirmar ciencia.", "danger")

        return redirect(url_for("main.piloto_caixa_entrada"))

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

    @bp.route(
        "/piloto/veiculos/<int:veiculo_id>/limpeza",
        methods=["POST"],
        endpoint="piloto_registrar_limpeza_turno",
    )
    @login_required
    def piloto_registrar_limpeza_turno(veiculo_id):
        _require_piloto()

        try:
            flash(
                registrar_limpeza_turno_piloto(
                    current_user,
                    veiculo_id,
                    request.form,
                ),
                "success",
            )
        except PermissionError:
            abort(403)
        except VeiculoTurnoError as exc:
            flash(str(exc), exc.category)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro tecnico ao registrar limpeza do turno.")
            flash("Erro tecnico ao registrar limpeza.", "danger")

        return redirect(url_for("main.piloto_veiculos"))

    @bp.route("/piloto/veiculos/<int:veiculo_id>/encerrar", methods=["POST"], endpoint="piloto_encerrar_turno")
    @login_required
    def piloto_encerrar_turno(veiculo_id):
        _require_piloto()

        try:
            flash(
                encerrar_turno_piloto(
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
            current_app.logger.exception("Erro tecnico ao encerrar turno de veiculo.")
            flash("Erro tecnico ao salvar.", "danger")
        return redirect(url_for("main.piloto_veiculos"))
