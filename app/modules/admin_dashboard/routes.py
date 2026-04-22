from datetime import datetime

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from app.extensions import db
from app.models import Solicitacao
from app.modules.admin_dashboard.service import (
    apply_admin_update_fields,
    build_active_teams,
    build_admin_canceladas_query,
    build_admin_dashboard_export,
    build_admin_dashboard_query,
    build_status_order,
    build_uvis_select,
    can_access_admin_panel,
    can_edit_admin_panel,
    get_google_maps_key,
    save_admin_attachment,
)
from app.shared.access import apply_solicitacao_prefeitura_scope


def _prefers_html_response():
    return request.accept_mimetypes.accept_html and not request.is_json


def _redirect_back_to_admin():
    return redirect(request.referrer or url_for("main.admin_dashboard"))


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _get_scoped_solicitacao_or_404(solicitacao_id: int):
    query = apply_solicitacao_prefeitura_scope(Solicitacao.query, current_user)
    return query.filter(Solicitacao.id == solicitacao_id).first_or_404()


HISTORICO_OS_ANDAMENTO_STATUSES = (
    "APROVADO",
    "APROVADA",
    "APROVADO COM RECOMENDACOES",
    "APROVADA COM RECOMENDACOES",
    "APROVADO COM RECOMENDAÇÕES",
    "APROVADA COM RECOMENDAÇÕES",
)
HISTORICO_OS_CONCLUIDAS_STATUSES = ("CONCLUIDO", "CONCLUÍDO")


def _admin_update_error(message: str, status_code: int, category: str):
    if _prefers_html_response():
        flash(message, category)
        return _redirect_back_to_admin()
    return jsonify({"error": message}), status_code


def register_routes(bp):
    @bp.route("/admin")
    @login_required
    def admin_dashboard():
        if not can_access_admin_panel(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        filtro_status = (request.args.get("status") or "").strip()
        filtro_unidade = (request.args.get("unidade") or "").strip()
        filtro_regiao = (request.args.get("regiao") or "").strip()
        filtro_apoio_cet = (request.args.get("apoio_cet") or "").strip().upper()
        filtro_protocolo = (request.args.get("protocolo") or "").strip()
        filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
        filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
        filtro_foco = (request.args.get("foco") or "").strip()

        if filtro_status == "CANCELADO":
            return redirect(
                url_for(
                    "main.admin_canceladas",
                    unidade=filtro_unidade,
                    regiao=filtro_regiao,
                    tipo_visita=filtro_tipo_visita,
                    tipo_imovel=filtro_tipo_imovel,
                    foco=filtro_foco,
                    protocolo=filtro_protocolo,
                )
            )

        page = request.args.get("page", 1, type=int)
        query = build_admin_dashboard_query(
            current_user,
            filtro_status=filtro_status,
            filtro_unidade=filtro_unidade,
            filtro_regiao=filtro_regiao,
            filtro_apoio_cet=filtro_apoio_cet,
            filtro_protocolo=filtro_protocolo,
            filtro_tipo_visita=filtro_tipo_visita,
            filtro_tipo_imovel=filtro_tipo_imovel,
            filtro_foco=filtro_foco,
        )
        paginacao = query.order_by(build_status_order(), Solicitacao.data_criacao.desc()).paginate(
            page=page,
            per_page=6,
            error_out=False,
        )

        return render_template(
            "admin.html",
            pedidos=paginacao.items,
            paginacao=paginacao,
            is_editable=can_edit_admin_panel(current_user),
            now=datetime.now(),
            equipes=build_active_teams(current_user),
            unidades_select=build_uvis_select(current_user),
            google_maps_key=get_google_maps_key(),
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/admin/exportar_excel")
    @login_required
    def exportar_excel():
        if not can_access_admin_panel(current_user):
            flash("Permissao negada para exportar.", "danger")
            return redirect(url_for("main.admin_dashboard"))

        try:
            filtro_status = (request.args.get("status") or "").strip()
            filtro_unidade = (request.args.get("unidade") or "").strip()
            filtro_regiao = (request.args.get("regiao") or "").strip()
            filtro_apoio_cet = (request.args.get("apoio_cet") or "").strip().upper()
            filtro_protocolo = (request.args.get("protocolo") or "").strip()
            filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
            filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
            filtro_foco = (request.args.get("foco") or "").strip()

            output = build_admin_dashboard_export(
                user=current_user,
                filtro_status=filtro_status,
                filtro_unidade=filtro_unidade,
                filtro_regiao=filtro_regiao,
                filtro_apoio_cet=filtro_apoio_cet,
                filtro_protocolo=filtro_protocolo,
                filtro_tipo_visita=filtro_tipo_visita,
                filtro_tipo_imovel=filtro_tipo_imovel,
                filtro_foco=filtro_foco,
            )

            return send_file(
                output,
                download_name="relatorio_solicitacoes.xlsx",
                as_attachment=False,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"ERRO EXPORTAR EXCEL: {exc}")
            flash("Erro ao gerar o Excel. Verifique se os dados estao corretos.", "danger")
            return redirect(url_for("main.admin_dashboard"))

    @bp.route("/admin/atualizar/<int:id>", methods=["POST"])
    @login_required
    def atualizar(id):
        if not can_edit_admin_panel(current_user):
            return _admin_update_error("Permissao negada.", 403, "danger")

        pedido = _get_scoped_solicitacao_or_404(id)

        try:
            equipe_nome = apply_admin_update_fields(pedido, request.form, user=current_user)
        except ValueError as exc:
            return _admin_update_error(str(exc), 400, "warning")

        uploaded_file = request.files.get("anexo")
        if uploaded_file and uploaded_file.filename:
            try:
                save_admin_attachment(pedido, uploaded_file)
            except ValueError as exc:
                return _admin_update_error(str(exc), 400, "warning")
            except Exception as exc:
                current_app.logger.error(f"Erro ao salvar arquivo fisico: {exc}")
                return _admin_update_error("Falha ao salvar o arquivo no servidor.", 500, "danger")

        try:
            db.session.commit()

            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
            if is_ajax:
                return jsonify(
                    {
                        "ok": True,
                        "message": "Solicitacao atualizada com sucesso!",
                        "anexo_nome": pedido.anexo_nome,
                        "equipe_id": pedido.equipe_id,
                        "equipe_nome": equipe_nome,
                    }
                ), 200

            flash("Solicitacao atualizada com sucesso!", "success")
            return _redirect_back_to_admin()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Erro de Banco (Atualizar ID {id}): {exc}")
            return _admin_update_error("Erro ao gravar dados no banco de dados.", 500, "danger")

    @bp.post("/admin/solicitacao/<int:id>/cancelar")
    @login_required
    def cancelar_solicitacao_admin(id):
        solicitacao = _get_scoped_solicitacao_or_404(id)

        if not can_edit_admin_panel(current_user) and solicitacao.usuario_id != current_user.id:
            abort(403)

        if solicitacao.status == "CANCELADO":
            flash("Essa solicitacao ja esta cancelada.", "info")
            return redirect(request.referrer or url_for("main.admin_dashboard"))

        solicitacao.status = "CANCELADO"
        db.session.commit()

        flash("Solicitacao cancelada.", "success")
        return redirect(request.referrer or url_for("main.admin_dashboard"))

    @bp.route("/admin/canceladas")
    @login_required
    def admin_canceladas():
        if not can_access_admin_panel(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        filtro_unidade = (request.args.get("unidade") or "").strip()
        filtro_regiao = (request.args.get("regiao") or "").strip()
        filtro_foco = (request.args.get("foco") or "").strip()
        filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
        filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
        filtro_protocolo = (request.args.get("protocolo") or "").strip()
        page = request.args.get("page", 1, type=int)

        query = build_admin_canceladas_query(
            current_user,
            filtro_unidade=filtro_unidade,
            filtro_regiao=filtro_regiao,
            filtro_foco=filtro_foco,
            filtro_protocolo=filtro_protocolo,
            filtro_tipo_visita=filtro_tipo_visita,
            filtro_tipo_imovel=filtro_tipo_imovel,
        )
        paginacao = query.order_by(Solicitacao.data_criacao.desc()).paginate(
            page=page,
            per_page=6,
            error_out=False,
        )

        return render_template(
            "admin_canceladas.html",
            pedidos=paginacao.items,
            paginacao=paginacao,
            now=datetime.now(),
            unidades_select=build_uvis_select(current_user),
            google_maps_key=get_google_maps_key(),
            foco_selecionado=filtro_foco,
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/admin/historico-os")
    @login_required
    def admin_historico_os():
        if not can_access_admin_panel(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        filtro_status_os = (request.args.get("status_os") or "").strip().upper()
        filtro_unidade = (request.args.get("unidade") or "").strip()
        filtro_regiao = (request.args.get("regiao") or "").strip()
        page = request.args.get("page", 1, type=int)

        query = build_admin_dashboard_query(
            current_user,
            filtro_status="",
            filtro_unidade=filtro_unidade,
            filtro_regiao=filtro_regiao,
            filtro_apoio_cet="",
            filtro_protocolo="",
            filtro_tipo_visita="",
            filtro_tipo_imovel="",
            filtro_foco="",
        )

        if filtro_status_os == "EM_ANDAMENTO":
            query = query.filter(
                and_(
                    Solicitacao.status.in_(HISTORICO_OS_ANDAMENTO_STATUSES),
                    Solicitacao.equipe_id.isnot(None),
                )
            )
        elif filtro_status_os == "CONCLUIDAS":
            query = query.filter(Solicitacao.status.in_(HISTORICO_OS_CONCLUIDAS_STATUSES))
        else:
            query = query.filter(
                or_(
                    Solicitacao.status.in_(HISTORICO_OS_CONCLUIDAS_STATUSES),
                    and_(
                        Solicitacao.status.in_(HISTORICO_OS_ANDAMENTO_STATUSES),
                        Solicitacao.equipe_id.isnot(None),
                    ),
                )
            )

        paginacao = query.order_by(
            build_status_order(),
            Solicitacao.data_criacao.desc(),
            Solicitacao.id.desc(),
        ).paginate(page=page, per_page=6, error_out=False)

        return render_template(
            "admin_historico_os.html",
            pedidos=paginacao.items,
            paginacao=paginacao,
            unidades_select=build_uvis_select(current_user),
            filtro_status_os=filtro_status_os,
            pagination_args=_query_args_without_page(),
        )
