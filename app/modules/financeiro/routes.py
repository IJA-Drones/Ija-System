from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from requests import RequestException
from app.shared.skybox import SkyboxError, stream_skybox_file
from app.modules.financeiro.logos import upload_company_logo, cleanup_company_logo
from app.extensions import db
from app.models import FinanceiroEmpresaPerfil
from app.shared.formatters import only_digits
from app.shared.validators import validate_cnpj

from flask import flash, redirect, abort, current_app, g, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.financeiro.service import build_financeiro_empresas, build_financeiro_menu
from app.shared.access import can_access_financeiro_panel, can_manage_financeiro_settings, is_agro_finance_user
from app.shared.financeiro_navigation import is_financeiro_endpoint, is_financeiro_legacy_endpoint, is_financeiro_settings_endpoint


COMPANY_CONSULTATION_ENDPOINTS = {
    "relacionamentos": "main.agro_clientes_menu",
    "clientes": "main.agro_clientes_listar",
    "fornecedores": "main.agro_fornecedores_listar",
    "orcamentos": "main.agro_orcamentos_listar",
    "mapeamentos": "main.agro_orcamentos_template_mapeamento",
    "contratos": "main.agro_contratos_listar",
}
SHARED_FINANCE_ENDPOINTS = {
    "main.agro_contrato_comprovante_pagamento",
    "main.agro_contrato_comprovante_pagamento_upload",
    "main.agro_contrato_comprovante_pagamento_remover",
    "main.agro_contrato_pdf", "main.agro_orcamento_pdf", "main.agro_orcamento_anexo",
    "main.agro_fornecedores_listar", "main.agro_fornecedor_novo",
    "main.agro_fornecedor_editar", "main.agro_fornecedor_deletar",
}
PREFEITURA_MAP_ENDPOINTS = {
    "main.mapa_relatorio", "main.heatmap_data", "main.consultar_endereco_geolocalizacao",
}


def _require_financeiro_access():
    if not can_access_financeiro_panel(current_user):
        abort(403)


def _resolve_empresa(empresa_slug, *, existing_data=False):
    _require_financeiro_access()
    empresa = next((item for item in build_financeiro_empresas(current_user)
                    if item["slug"] == empresa_slug), None)
    if empresa is None:
        abort(404)
    if not empresa["disponivel"] or (existing_data and empresa["slug"] != "ija"):
        abort(403)
    return empresa


def _consulta_url(endpoint, **values):
    empresa = getattr(g, "financeiro_empresa", None)
    if empresa is None:
        return url_for(endpoint, **values)
    if endpoint == "main.admin_agro":
        return url_for("main.financeiro_empresa", empresa_slug=empresa["slug"])
    tipo = next((tipo for tipo, original in COMPANY_CONSULTATION_ENDPOINTS.items() if original == endpoint), None)
    if tipo is None:
        return url_for(endpoint, **values)
    params = {**values, "empresa_slug": empresa["slug"]}
    if tipo in {"relacionamentos", "clientes", "fornecedores"}:
        params.pop("aba", None)
        return url_for("main.financeiro_empresa_" + tipo, **params)
    params["aba"] = tipo
    return url_for("main.financeiro_empresa_comercial", **params)


def register_routes(bp):
    @bp.before_request
    def restrict_financial_users_to_finance():
        if not current_user.is_authenticated or not is_agro_finance_user(current_user):
            return None
        endpoint = request.endpoint or ""
        if endpoint in SHARED_FINANCE_ENDPOINTS:
            # Shared files/suppliers are needed by the existing finance screens.
            g.financeiro_empresa = _resolve_empresa("ija", existing_data=True)
            return None
        if endpoint in PREFEITURA_MAP_ENDPOINTS or (endpoint.startswith("main.agro_") and not is_financeiro_legacy_endpoint(endpoint)):
            abort(403)

    @bp.before_request
    def authorize_existing_financial_views():
        if not is_financeiro_legacy_endpoint(request.endpoint):
            return None
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        _require_financeiro_access()
        empresa = next((item for item in build_financeiro_empresas(current_user) if item["slug"] == "ija"), None)
        if empresa is None or not empresa["disponivel"]:
            abort(403)
        if is_financeiro_settings_endpoint(request.endpoint) and not can_manage_financeiro_settings(current_user):
            abort(403)
        g.financeiro_empresa = empresa

    @bp.app_context_processor
    def inject_financeiro_access():
        return {
            "can_access_financeiro_panel": can_access_financeiro_panel,
            "can_manage_financeiro_settings": can_manage_financeiro_settings,
            "is_financeiro_endpoint": lambda endpoint: is_financeiro_endpoint(endpoint) or getattr(g, "financeiro_empresa", None) is not None or is_agro_finance_user(current_user),
            "financeiro_empresa_atual": getattr(g, "financeiro_empresa", None),
            "build_financeiro_menu": build_financeiro_menu,
            "financeiro_consulta_url": _consulta_url,
        }

    @bp.after_request
    def prevent_financeiro_cache(response):
        if is_financeiro_endpoint(request.endpoint) or getattr(g, "financeiro_empresa", None) is not None:
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/financeiro", methods=["GET"], endpoint="financeiro_central")
    @login_required
    def financeiro_central():
        _require_financeiro_access()
        empresas = build_financeiro_empresas(current_user)
        return render_template(
            "financeiro_central.html",
            empresas=empresas,
            total_empresas_disponiveis=sum(empresa["disponivel"] for empresa in empresas),
        )

    @bp.route("/financeiro/empresas/<empresa_slug>", methods=["GET"], endpoint="financeiro_empresa")
    @login_required
    def financeiro_empresa(empresa_slug):
        empresa = _resolve_empresa(empresa_slug)
        # The company is resolved on every request from the URL and permissions.
        # No shared selected-company cookie can change another tab's context.
        return render_template("financeiro_empresa.html", empresa=empresa)

    @bp.route("/financeiro/empresas/<empresa_slug>/logo", methods=["GET"], endpoint="financeiro_empresa_logo")
    @login_required
    def financeiro_empresa_logo(empresa_slug):
        _resolve_empresa(empresa_slug)
        perfil = db.session.get(FinanceiroEmpresaPerfil, empresa_slug)
        if not perfil or not perfil.logo_path:
            abort(404)
        try:
            response = stream_skybox_file(perfil.logo_path, request.headers.get("Range"), as_attachment=False)
        except (SkyboxError, RequestException):
            current_app.logger.exception("Falha ao carregar logo da empresa no Skybox.")
            abort(502)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.route("/financeiro/empresas/<empresa_slug>/configuracoes", methods=["GET"], endpoint="financeiro_empresa_configuracoes")
    @login_required
    def financeiro_empresa_configuracoes(empresa_slug):
        g.financeiro_empresa = _resolve_empresa(empresa_slug)
        if not can_manage_financeiro_settings(current_user):
            abort(403)
        secao = request.args.get("secao", "dados")
        if secao == "competencias" and empresa_slug == "ija":
            return current_app.view_functions["main.agro_financeiro_configuracoes"]()
        if secao not in {"dados", "layout"}:
            secao = "dados"
        return render_template("agro_financeiro_configuracoes.html", secao=secao, competencias=[], competencias_configuradas=[])

    @bp.route("/financeiro/empresas/<empresa_slug>/configuracoes", methods=["POST"], endpoint="financeiro_empresa_configuracoes_salvar")
    @login_required
    def financeiro_empresa_configuracoes_salvar(empresa_slug):
        _resolve_empresa(empresa_slug)
        if not can_manage_financeiro_settings(current_user):
            abort(403)
        secao = request.form.get("secao")
        destino = url_for("main.financeiro_empresa_configuracoes", empresa_slug=empresa_slug, secao=secao)
        perfil = db.session.get(FinanceiroEmpresaPerfil, empresa_slug)
        novo = perfil is None
        if novo:
            perfil = FinanceiroEmpresaPerfil(empresa_slug=empresa_slug)
        old_logo_path = perfil.logo_path
        uploaded_path = None
        try:
            if secao == "dados":
                nome = request.form.get("nome", "").strip()
                razao = request.form.get("razao_social", "").strip()
                cnpj = only_digits(request.form.get("cnpj", ""))
                if not nome or len(nome) > 120 or not razao or len(razao) > 180:
                    raise ValueError("Preencha o nome (até 120 caracteres) e a razão social (até 180).")
                # Preserve the initial demonstration document until replaced.
                demo = cnpj == "11111111000111" and not perfil.cnpj and empresa_slug == "ija"
                if not demo and not validate_cnpj(cnpj):
                    raise ValueError("Informe um CNPJ válido.")
                perfil.nome, perfil.razao_social = nome, razao
                perfil.cnpj = None if demo else cnpj
            elif secao == "layout":
                arquivo = request.files.get("logo")
                if request.form.get("remover_logo") == "1":
                    perfil.logo_path, perfil.tem_logo = None, False
                elif arquivo and arquivo.filename:
                    data = arquivo.stream.read(2 * 1024 * 1024 + 1)
                    if len(data) > 2 * 1024 * 1024:
                        raise ValueError("A logo deve ter no máximo 2 MB.")
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("error", Image.DecompressionBombWarning)
                            with Image.open(BytesIO(data)) as img:
                                if img.format not in {"PNG", "JPEG", "WEBP"} or img.width * img.height > 16000000:
                                    raise ValueError("Use uma imagem PNG, JPG ou WebP de até 16 megapixels.")
                                img.thumbnail((512, 512))
                                out = BytesIO()
                                img.convert("RGBA").save(out, format="PNG")
                                uploaded_path = upload_company_logo(empresa_slug, out.getvalue())
                                perfil.logo_path, perfil.tem_logo = uploaded_path, True
                    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                        raise ValueError("Não foi possível ler a imagem. Use PNG, JPG ou WebP.")
                else:
                    raise ValueError("Selecione uma imagem para salvar a logo.")
            else:
                abort(400)
            if novo:
                db.session.add(perfil)
            db.session.commit()
        except (ValueError, SQLAlchemyError, SkyboxError) as exc:
            db.session.rollback()
            cleanup_company_logo(uploaded_path)
            if isinstance(exc, (ValueError, SkyboxError)):
                message = str(exc)
            elif isinstance(exc, IntegrityError):
                message = "Este CNPJ já está cadastrado em outra empresa."
            else:
                current_app.logger.exception("Falha ao salvar configurações da empresa.")
                message = "Não foi possível salvar. Tente novamente."
            flash(message, "warning")
            return redirect(destino)
        if secao == "layout" and old_logo_path != perfil.logo_path:
            cleanup_company_logo(old_logo_path)
        flash("Configurações da empresa salvas.", "success")
        return redirect(destino)

    def render_company_consulta(empresa_slug, tipo):
        empresa = _resolve_empresa(empresa_slug, existing_data=True)
        g.financeiro_empresa = empresa
        # Reuse the original controllers/templates; only company navigation changes.
        return current_app.view_functions[COMPANY_CONSULTATION_ENDPOINTS[tipo]]()

    @bp.route("/financeiro/empresas/<empresa_slug>/clientes", methods=["GET"], endpoint="financeiro_empresa_clientes")
    @login_required
    def financeiro_empresa_clientes(empresa_slug):
        return render_company_consulta(empresa_slug, "clientes")

    @bp.route("/financeiro/empresas/<empresa_slug>/relacionamentos", methods=["GET"], endpoint="financeiro_empresa_relacionamentos")
    @login_required
    def financeiro_empresa_relacionamentos(empresa_slug):
        return render_company_consulta(empresa_slug, "relacionamentos")

    @bp.route("/financeiro/empresas/<empresa_slug>/fornecedores", methods=["GET"], endpoint="financeiro_empresa_fornecedores")
    @login_required
    def financeiro_empresa_fornecedores(empresa_slug):
        return render_company_consulta(empresa_slug, "fornecedores")

    @bp.route("/financeiro/empresas/<empresa_slug>/comercial", methods=["GET"], endpoint="financeiro_empresa_comercial")
    @login_required
    def financeiro_empresa_comercial(empresa_slug):
        tipo = request.args.get("aba", "orcamentos")
        if tipo not in {"orcamentos", "mapeamentos", "contratos"}:
            abort(404)
        return render_company_consulta(empresa_slug, tipo)
