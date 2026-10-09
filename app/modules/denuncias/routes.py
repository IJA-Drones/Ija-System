import os
from datetime import date

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app.modules.denuncias.service import (
    build_denuncias_query,
    can_access_denuncias,
    COORDENADORIAS_DENUNCIA,
    arquivar_denuncia,
    build_denuncias_coordenadoria_query,
    build_denuncias_uvis_query,
    build_solicitacao_form_from_denuncia,
    build_uvis_options_for_denuncia,
    can_access_denuncia,
    designar_denuncia_para_uvis,
    encaminhar_denuncia_para_coordenadoria,
    get_anexo_or_404,
    get_denuncia_or_404,
    get_denuncia_scoped_or_404,
    resolve_denuncia_local_media,
)
from app.modules.solicitacoes.service import (
    NovoCadastroValidationError,
    can_use_custom_visit_other,
    create_nova_solicitacao,
)
from app.shared.access import is_regional_user
from app.shared.skybox import SkyboxError, is_skybox_path, stream_skybox_file


DENUNCIAS_PER_PAGE = 20


def register_routes(bp):
    @bp.route("/denuncias", methods=["GET"], endpoint="denuncias_listar")
    @login_required
    def denuncias_listar():
        if not can_access_denuncias(current_user):
            abort(403)
        if is_regional_user(current_user):
            return redirect(url_for("main.coordenadoria_denuncias_listar"))
        if getattr(current_user, "tipo_usuario", None) == "uvis":
            return redirect(url_for("main.uvis_denuncias_listar"))

        paginacao = build_denuncias_query(request.args).paginate(
            page=request.args.get("page", 1, type=int),
            per_page=DENUNCIAS_PER_PAGE,
            error_out=False,
        )
        return render_template(
            "denuncias_listar.html",
            denuncias=paginacao.items,
            paginacao=paginacao,
            view_mode="covisa",
            list_endpoint="main.denuncias_listar",
            detail_endpoint="main.denuncia_detalhe",
            clear_url=url_for("main.denuncias_listar"),
            back_url=url_for("main.admin_dashboard"),
            filters={
                "q": (request.args.get("q") or "").strip(),
                "status": (request.args.get("status") or "").strip(),
                "tipo_visita": (request.args.get("tipo_visita") or "").strip(),
            },
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )

    @bp.route("/denuncias/<int:denuncia_id>", methods=["GET"], endpoint="denuncia_detalhe")
    @login_required
    def denuncia_detalhe(denuncia_id):
        if not can_access_denuncias(current_user):
            abort(403)

        denuncia = get_denuncia_scoped_or_404(denuncia_id, current_user)
        return render_template(
            "denuncia_detalhe.html",
            denuncia=denuncia,
            view_mode="covisa",
            back_url=url_for("main.denuncias_listar"),
            coordenadorias=COORDENADORIAS_DENUNCIA,
            uvis_options=[],
        )

    @bp.route("/coordenadoria/denuncias", methods=["GET"], endpoint="coordenadoria_denuncias_listar")
    @login_required
    def coordenadoria_denuncias_listar():
        if not is_regional_user(current_user):
            abort(403)

        paginacao = build_denuncias_coordenadoria_query(current_user, request.args).paginate(
            page=request.args.get("page", 1, type=int),
            per_page=DENUNCIAS_PER_PAGE,
            error_out=False,
        )
        return render_template(
            "denuncias_listar.html",
            denuncias=paginacao.items,
            paginacao=paginacao,
            view_mode="coordenadoria",
            list_endpoint="main.coordenadoria_denuncias_listar",
            detail_endpoint="main.coordenadoria_denuncia_detalhe",
            clear_url=url_for("main.coordenadoria_denuncias_listar"),
            back_url=url_for("main.admin_dashboard"),
            filters={
                "q": (request.args.get("q") or "").strip(),
                "status": (request.args.get("status") or "").strip(),
                "tipo_visita": (request.args.get("tipo_visita") or "").strip(),
            },
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )

    @bp.route("/coordenadoria/denuncias/<int:denuncia_id>", methods=["GET"], endpoint="coordenadoria_denuncia_detalhe")
    @login_required
    def coordenadoria_denuncia_detalhe(denuncia_id):
        if not is_regional_user(current_user):
            abort(403)

        denuncia = get_denuncia_scoped_or_404(denuncia_id, current_user)
        return render_template(
            "denuncia_detalhe.html",
            denuncia=denuncia,
            view_mode="coordenadoria",
            back_url=url_for("main.coordenadoria_denuncias_listar"),
            coordenadorias=COORDENADORIAS_DENUNCIA,
            uvis_options=build_uvis_options_for_denuncia(denuncia),
        )

    @bp.route("/denuncias/<int:denuncia_id>/encaminhar-coordenadoria", methods=["POST"], endpoint="denuncia_encaminhar_coordenadoria")
    @login_required
    def denuncia_encaminhar_coordenadoria(denuncia_id):
        if not can_access_denuncias(current_user):
            abort(403)

        denuncia = get_denuncia_or_404(denuncia_id)
        try:
            encaminhar_denuncia_para_coordenadoria(
                denuncia,
                request.form.get("coordenadoria"),
                current_user,
            )
            flash("Denúncia encaminhada para a coordenadoria responsável.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")

        return redirect(url_for("main.denuncia_detalhe", denuncia_id=denuncia.id))

    @bp.route("/coordenadoria/denuncias/<int:denuncia_id>/designar-uvis", methods=["POST"], endpoint="coordenadoria_denuncia_designar_uvis")
    @login_required
    def coordenadoria_denuncia_designar_uvis(denuncia_id):
        if not is_regional_user(current_user):
            abort(403)

        denuncia = get_denuncia_scoped_or_404(denuncia_id, current_user)
        try:
            designar_denuncia_para_uvis(denuncia, request.form.get("uvis_usuario_id"), current_user)
            flash("Denúncia encaminhada para a UVIS responsável.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")

        return redirect(url_for("main.coordenadoria_denuncia_detalhe", denuncia_id=denuncia.id))

    @bp.route("/uvis/denuncias", methods=["GET"], endpoint="uvis_denuncias_listar")
    @login_required
    def uvis_denuncias_listar():
        if getattr(current_user, "tipo_usuario", None) != "uvis":
            abort(403)

        paginacao = build_denuncias_uvis_query(current_user, request.args).paginate(
            page=request.args.get("page", 1, type=int),
            per_page=DENUNCIAS_PER_PAGE,
            error_out=False,
        )
        return render_template(
            "denuncias_listar.html",
            denuncias=paginacao.items,
            paginacao=paginacao,
            view_mode="uvis",
            list_endpoint="main.uvis_denuncias_listar",
            detail_endpoint="main.uvis_denuncia_detalhe",
            clear_url=url_for("main.uvis_denuncias_listar"),
            back_url=url_for("main.dashboard"),
            filters={
                "q": (request.args.get("q") or "").strip(),
                "status": (request.args.get("status") or "").strip(),
                "tipo_visita": (request.args.get("tipo_visita") or "").strip(),
            },
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )

    @bp.route("/uvis/denuncias/<int:denuncia_id>", methods=["GET", "POST"], endpoint="uvis_denuncia_detalhe")
    @login_required
    def uvis_denuncia_detalhe(denuncia_id):
        if getattr(current_user, "tipo_usuario", None) != "uvis":
            abort(403)

        denuncia = get_denuncia_scoped_or_404(denuncia_id, current_user)
        if request.method == "POST":
            if denuncia.solicitacao_id:
                flash("Esta denúncia já foi convertida em solicitação.", "warning")
                return redirect(url_for("main.uvis_denuncia_detalhe", denuncia_id=denuncia.id))

            try:
                solicitacao = create_nova_solicitacao(current_user, request.form)
                denuncia.solicitacao_id = solicitacao.id
                denuncia.status = denuncia.STATUS_CONVERTIDA_SOLICITACAO
                denuncia.triado_por_id = getattr(current_user, "id", None)
                from app.extensions import db

                db.session.commit()
                flash("Solicitação criada a partir da denúncia.", "success")
                return redirect(url_for("main.dashboard"))
            except NovoCadastroValidationError as exc:
                flash(exc.message, exc.category)
            except Exception:
                current_app.logger.exception("Erro ao converter denuncia %s em solicitacao.", denuncia.id)
                flash("Erro ao criar solicitação a partir da denúncia.", "danger")

        return render_template(
            "denuncia_uvis_detalhe.html",
            denuncia=denuncia,
            form=build_solicitacao_form_from_denuncia(denuncia, request.form if request.method == "POST" else None),
            back_url=url_for("main.uvis_denuncias_listar"),
            hoje=date.today().isoformat(),
            allow_custom_visit_other=can_use_custom_visit_other(current_user),
            google_maps_key=current_app.config.get("Maps_KEY_FRONT") or os.getenv("KEY_API_GOOGLE_MAPS"),
        )

    @bp.route("/denuncias/<int:denuncia_id>/arquivar", methods=["POST"], endpoint="denuncia_arquivar")
    @login_required
    def denuncia_arquivar(denuncia_id):
        if not can_access_denuncias(current_user):
            abort(403)

        denuncia = get_denuncia_or_404(denuncia_id)
        try:
            arquivar_denuncia(denuncia, request.form.get("motivo"), current_user)
            flash("Denúncia arquivada com sucesso.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")

        return redirect(url_for("main.denuncia_detalhe", denuncia_id=denuncia.id))

    @bp.route("/denuncias/anexos/<int:anexo_id>", methods=["GET"], endpoint="denuncia_anexo")
    @login_required
    def denuncia_anexo(anexo_id):
        if not can_access_denuncias(current_user):
            abort(403)

        anexo = get_anexo_or_404(anexo_id)
        if not can_access_denuncia(current_user, anexo.denuncia):
            abort(403)
        if is_skybox_path(anexo.arquivo_path):
            try:
                return stream_skybox_file(
                    anexo.arquivo_path,
                    request.headers.get("Range"),
                    as_attachment=False,
                    conditional_headers=request.headers,
                )
            except SkyboxError:
                abort(404)

        try:
            upload_folder, rel, download_name = resolve_denuncia_local_media(anexo)
        except FileNotFoundError:
            abort(404)

        return send_from_directory(
            upload_folder,
            rel,
            as_attachment=False,
            download_name=download_name,
        )
