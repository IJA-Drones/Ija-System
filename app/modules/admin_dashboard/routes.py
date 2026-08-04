from datetime import datetime

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models import Solicitacao, Usuario
from app.modules.admin_dashboard.service import (
    apply_admin_update_fields,
    build_active_teams,
    build_admin_canceladas_query,
    build_admin_dashboard_export,
    build_admin_dashboard_query,
    build_admin_historico_os_export,
    build_admin_historico_os_query,
    build_equipe_uvis_names_select,
    build_status_order,
    build_uvis_select,
    can_access_admin_panel,
    can_edit_admin_panel,
    get_google_maps_key,
    save_admin_attachment,
)
from app.shared.access import apply_regiao_scope, apply_solicitacao_prefeitura_scope
from app.shared.os_history_filters import get_os_history_filters
from app.shared.query_filters import get_multi_values, multi_value_to_query, query_args_without_page
from app.shared.redirects import redirect_back
from app.shared.retorno_ciclo import build_retorno_ciclo_context, build_retorno_ciclo_summaries


ADMIN_PER_PAGE_OPTIONS = (10, 25, 50, 100, 250)


def _prefers_html_response():
    return request.accept_mimetypes.accept_html and not request.is_json


def _redirect_back_to_admin():
    return redirect_back("main.admin_dashboard")


def _query_args_without_page():
    return query_args_without_page(request.args)


def _get_admin_per_page():
    try:
        per_page = int(request.args.get("per_page") or 25)
    except (TypeError, ValueError):
        per_page = 25
    return per_page if per_page in ADMIN_PER_PAGE_OPTIONS else 25


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


def _has_equipe_uvis_os():
    return or_(
        Solicitacao.ordem_servico_equipe_uvis.has(),
        and_(
            Solicitacao.equipe_uvis_nome.isnot(None),
            func.trim(Solicitacao.equipe_uvis_nome) != "",
        ),
    )


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
        filtro_unidade = get_multi_values(request.args, "unidade")
        filtro_regiao = (request.args.get("regiao") or "").strip()
        filtro_apoio_cet = (request.args.get("apoio_cet") or "").strip().upper()
        filtro_protocolo = (request.args.get("protocolo") or "").strip()
        filtro_endereco = (request.args.get("endereco") or "").strip()
        filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
        filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
        filtro_foco = get_multi_values(request.args, "foco")
        filtro_data_ini = (request.args.get("data_ini") or "").strip()
        filtro_data_fim = (request.args.get("data_fim") or "").strip()
        filtro_data_criacao_ini = (request.args.get("data_criacao_ini") or "").strip()
        filtro_data_criacao_fim = (request.args.get("data_criacao_fim") or "").strip()
        filtro_retorno_automatico = (request.args.get("retorno_automatico") or "").strip().upper()

        if filtro_status == "CANCELADO":
            return redirect(
                url_for(
                    "main.admin_canceladas",
                    unidade=multi_value_to_query(filtro_unidade),
                    regiao=filtro_regiao,
                    tipo_visita=filtro_tipo_visita,
                    tipo_imovel=filtro_tipo_imovel,
                    foco=multi_value_to_query(filtro_foco),
                    protocolo=filtro_protocolo,
                    endereco=filtro_endereco,
                    data_ini=filtro_data_ini,
                    data_fim=filtro_data_fim,
                    data_criacao_ini=filtro_data_criacao_ini,
                    data_criacao_fim=filtro_data_criacao_fim,
                    retorno_automatico=filtro_retorno_automatico,
                )
            )

        page = request.args.get("page", 1, type=int)
        per_page = _get_admin_per_page()
        query = build_admin_dashboard_query(
            current_user,
            filtro_status=filtro_status,
            filtro_unidade=filtro_unidade,
            filtro_regiao=filtro_regiao,
            filtro_apoio_cet=filtro_apoio_cet,
            filtro_protocolo=filtro_protocolo,
            filtro_endereco=filtro_endereco,
            filtro_tipo_visita=filtro_tipo_visita,
            filtro_tipo_imovel=filtro_tipo_imovel,
            filtro_foco=filtro_foco,
            filtro_data_ini=filtro_data_ini,
            filtro_data_fim=filtro_data_fim,
            filtro_data_criacao_ini=filtro_data_criacao_ini,
            filtro_data_criacao_fim=filtro_data_criacao_fim,
            filtro_retorno_automatico=filtro_retorno_automatico,
        )
        paginacao = query.order_by(build_status_order(), Solicitacao.data_criacao.desc()).paginate(
            page=page,
            per_page=per_page,
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
            admin_return_url=request.full_path.rstrip("?"),
            per_page_options=ADMIN_PER_PAGE_OPTIONS,
            retorno_ciclos=build_retorno_ciclo_summaries(current_user, paginacao.items),
            filtros_multi={
                "unidade": filtro_unidade,
                "foco": filtro_foco,
            },
        )

    @bp.route("/admin/exportar_excel")
    @login_required
    def exportar_excel():
        if not can_access_admin_panel(current_user):
            flash("Permissao negada para exportar.", "danger")
            return redirect(url_for("main.admin_dashboard"))

        try:
            filtro_status = (request.args.get("status") or "").strip()
            filtro_unidade = get_multi_values(request.args, "unidade")
            filtro_regiao = (request.args.get("regiao") or "").strip()
            filtro_apoio_cet = (request.args.get("apoio_cet") or "").strip().upper()
            filtro_protocolo = (request.args.get("protocolo") or "").strip()
            filtro_endereco = (request.args.get("endereco") or "").strip()
            filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
            filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
            filtro_foco = get_multi_values(request.args, "foco")
            filtro_data_ini = (request.args.get("data_ini") or "").strip()
            filtro_data_fim = (request.args.get("data_fim") or "").strip()
            filtro_data_criacao_ini = (request.args.get("data_criacao_ini") or "").strip()
            filtro_data_criacao_fim = (request.args.get("data_criacao_fim") or "").strip()
            filtro_retorno_automatico = (request.args.get("retorno_automatico") or "").strip().upper()

            output = build_admin_dashboard_export(
                user=current_user,
                filtro_status=filtro_status,
                filtro_unidade=filtro_unidade,
                filtro_regiao=filtro_regiao,
                filtro_apoio_cet=filtro_apoio_cet,
                filtro_protocolo=filtro_protocolo,
                filtro_endereco=filtro_endereco,
                filtro_tipo_visita=filtro_tipo_visita,
                filtro_tipo_imovel=filtro_tipo_imovel,
                filtro_foco=filtro_foco,
                filtro_data_ini=filtro_data_ini,
                filtro_data_fim=filtro_data_fim,
                filtro_data_criacao_ini=filtro_data_criacao_ini,
                filtro_data_criacao_fim=filtro_data_criacao_fim,
                filtro_retorno_automatico=filtro_retorno_automatico,
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

        filtro_unidade = get_multi_values(request.args, "unidade")
        filtro_regiao = (request.args.get("regiao") or "").strip()
        filtro_foco = get_multi_values(request.args, "foco")
        filtro_tipo_visita = (request.args.get("tipo_visita") or "").strip()
        filtro_tipo_imovel = (request.args.get("tipo_imovel") or "").strip()
        filtro_protocolo = (request.args.get("protocolo") or "").strip()
        filtro_endereco = (request.args.get("endereco") or "").strip()
        filtro_data_ini = (request.args.get("data_ini") or "").strip()
        filtro_data_fim = (request.args.get("data_fim") or "").strip()
        page = request.args.get("page", 1, type=int)

        query = build_admin_canceladas_query(
            current_user,
            filtro_unidade=filtro_unidade,
            filtro_regiao=filtro_regiao,
            filtro_foco=filtro_foco,
            filtro_protocolo=filtro_protocolo,
            filtro_endereco=filtro_endereco,
            filtro_tipo_visita=filtro_tipo_visita,
            filtro_tipo_imovel=filtro_tipo_imovel,
            filtro_data_ini=filtro_data_ini,
            filtro_data_fim=filtro_data_fim,
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
            filtros_multi={
                "unidade": filtro_unidade,
                "foco": filtro_foco,
            },
        )

    @bp.route("/admin/historico-os")
    @login_required
    def admin_historico_os():
        if not can_access_admin_panel(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        filtros = get_os_history_filters(request.args, status_key="status_os")
        filtro_status_os = filtros["status"]
        filtro_tipo_os = "piloto"
        filtro_equipe = (request.args.get("equipe") or "").strip()
        filtros["equipe"] = filtro_equipe
        page = request.args.get("page", 1, type=int)

        query = build_admin_historico_os_query(
            current_user,
            filtros,
            filtro_tipo_os,
            filtro_equipe,
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
            equipes_select=build_active_teams(current_user),
            equipes_uvis_select=build_equipe_uvis_names_select(current_user),
            filtro_status_os=filtro_status_os,
            filtro_tipo_os=filtro_tipo_os,
            filtros=filtros,
            filtros_historico={
                key: value
                for key, value in _query_args_without_page().items()
                if key != "tipo_os"
            },
            pagination_args=_query_args_without_page(),
            retorno_ciclos=build_retorno_ciclo_summaries(current_user, paginacao.items),
        )

    @bp.route("/admin/historico-os/exportar-excel")
    @login_required
    def admin_historico_os_exportar_excel():
        if not can_access_admin_panel(current_user):
            flash("Permissao negada para exportar.", "danger")
            return redirect(url_for("main.dashboard"))

        filtro_tipo_os = "piloto"

        filtros = get_os_history_filters(request.args, status_key="status_os")
        filtro_equipe = (request.args.get("equipe") or "").strip()
        if (request.args.get("all") or "").strip().lower() in {"1", "true", "sim", "yes"}:
            filtros = {key: "" for key in filtros}
            filtro_equipe = ""

        try:
            output, download_name = build_admin_historico_os_export(
                current_user,
                filtros,
                filtro_tipo_os,
                filtro_equipe,
            )
            return send_file(
                output,
                download_name=download_name,
                as_attachment=True,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"ERRO EXPORTAR HISTORICO OS EXCEL: {exc}")
            flash("Erro ao gerar o Excel do historico de OS.", "danger")
            return redirect(url_for("main.admin_historico_os", tipo_os=filtro_tipo_os))

    @bp.route("/admin/os/<int:os_id>/equipe-uvis-formulario", methods=["GET"], endpoint="admin_equipe_uvis_os_formulario_view")
    @login_required
    def admin_equipe_uvis_os_formulario_view(os_id):
        if not can_access_admin_panel(current_user):
            flash("Acesso restrito.", "danger")
            return redirect(url_for("main.dashboard"))

        query = (
            Solicitacao.query
            .options(
                db.selectinload(Solicitacao.usuario),
                db.selectinload(Solicitacao.equipe),
                db.selectinload(Solicitacao.ordem_servico_equipe_uvis),
            )
            .join(Usuario)
        )
        query = apply_solicitacao_prefeitura_scope(query, current_user)
        query = apply_regiao_scope(query, current_user, Usuario.regiao)
        solicitacao = query.filter(Solicitacao.id == os_id).first_or_404()
        ordem = solicitacao.ordem_servico_equipe_uvis

        if ordem is None:
            flash("A equipe UVIS ainda nao preencheu o formulario desta solicitacao.", "warning")
            return redirect(url_for("main.admin_historico_os", tipo_os="equipe_uvis"))

        retorno_existente = (
            Solicitacao.query
            .filter(
                Solicitacao.origem_retorno_id == solicitacao.id,
                Solicitacao.gerada_automaticamente.is_(True),
            )
            .order_by(Solicitacao.id.desc())
            .first()
        )

        return render_template(
            "equipe_uvis_os_formulario.html",
            solicitacao=solicitacao,
            ordem=ordem,
            modo_visualizacao=True,
            nome_equipe=ordem.equipe_uvis_nome or solicitacao.equipe_uvis_nome or "",
            uvis_nome=getattr(getattr(solicitacao, "usuario", None), "nome_uvis", "") or "",
            endereco_os=(
                f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
                f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
            ),
            respondido_por_padrao=ordem.respondido_por or "",
            respondido_em_value=(
                ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
                if ordem.respondido_em else ""
            ),
            retorno_existente=retorno_existente,
            retorno_monitoramento_value=(
                ordem.retorno_monitoramento_em.strftime("%Y-%m-%dT%H:%M")
                if ordem.retorno_monitoramento_em else ""
            ),
            retorno_ciclo=build_retorno_ciclo_context(current_user, os_id),
            url_voltar=url_for("main.admin_historico_os", tipo_os="equipe_uvis"),
            form_action="#",
        )
