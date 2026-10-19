"""Entrada da vigilância: navegação autorizada, sem consultar as bases dos módulos."""

from flask import abort, current_app, render_template, request, redirect, url_for
from flask_login import current_user, login_required

from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import is_admin_global_user, is_prefeitura_admin_user


def register_routes(bp):
    @bp.after_request
    def vigilancia_hub_no_cache(response):
        if request.endpoint == "main.vigilancia":
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.get("/vigilancia", endpoint="vigilancia")
    @login_required
    def hub():
        if current_user.tipo_usuario == "agente_endemias":
            return redirect(url_for("main.vigilancia_agente"))
        legacy = is_admin_global_user(current_user) or is_prefeitura_admin_user(current_user)
        if not route_access(current_user, legacy):
            abort(403)

        def allowed(endpoint):
            return can_access_endpoint(current_user, endpoint, "GET", legacy=legacy)

        cards = []
        if allowed("main.vigilancia_sinan"):
            cards.append({
                "id": "sinan", "eyebrow": "Epidemiologia", "title": "SINAN · Arboviroses",
                "icon": "bi-activity",
                "description": "Consulte notificações de dengue, zika e chikungunya. "
                               "Acesse os dados salvos, as exportações e o mapa.",
                "endpoint": "main.vigilancia_sinan" if current_app.config.get("SINAN_ENABLED", True) else None,
                "action": "Acessar SINAN", "secondary": None,
            })
        if allowed("main.vigilancia_campo"):
            cards.append({
                "id": "campo", "eyebrow": "Campo e indicadores", "title": "Focal e LIRAa",
                "icon": "bi-clipboard-data",
                "description": "Registre visitas e consulte os imóveis, os levantamentos "
                               "e os índices preliminares de infestação e recipientes.",
                "endpoint": "main.vigilancia_campo" if current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) else None,
                "action": "Acessar Focal e LIRAa", "secondary": None,
            })
        can_import = allowed("main.vigilancia_importacoes")
        can_preview = allowed("main.vigilancia_validacao")
        if can_import or can_preview:
            import_enabled = can_import and current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False)
            preview_enabled = can_preview and current_app.config.get("VIGILANCIA_PREVIEW_ENABLED", False)
            endpoint = "main.vigilancia_importacoes" if import_enabled else "main.vigilancia_validacao" if preview_enabled else None
            cards.append({
                "id": "arquivos", "eyebrow": "Gestão dos dados", "title": "Importação e validação",
                "icon": "bi-file-earmark-check",
                "description": "Confira arquivos de Focal e LIRAa, revise inconsistências "
                               "e acompanhe os lotes e suas confirmações.",
                "endpoint": endpoint,
                "action": "Acessar arquivos" if import_enabled else "Validar arquivo",
                "secondary": "main.vigilancia_validacao" if import_enabled and preview_enabled else None,
            })
        return render_template("vigilancia_central.html", vigilancia_cards=cards)
