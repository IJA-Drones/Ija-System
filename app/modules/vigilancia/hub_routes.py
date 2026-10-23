"""Entrada da vigilância: navegação autorizada, sem consultar as bases dos módulos."""

from flask import abort, current_app, render_template, request, redirect, url_for
from flask_login import current_user, login_required

from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import is_admin_global_user, is_prefeitura_admin_user
from .access import can_coordinate_field
from .results import municipality_ibge


def register_routes(bp):
    @bp.app_context_processor
    def field_coordination_navigation():
        coordinator = can_coordinate_field(current_user)
        navigation = []
        if current_user.is_authenticated and coordinator:
            for key, endpoint, label, icon, enabled in (
                ("sinan", "main.vigilancia_sinan", "SINAN", "bi-activity", current_app.config.get("SINAN_ENABLED", True)),
                ("campo", "main.vigilancia_planejamento", "LIRAa e focal", "bi-clipboard-check", current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False)),
                ("resultados", "main.vigilancia_resultados", "Resultados", "bi-bar-chart", current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False)),
                ("risco", "main.vigilancia_risco", "Mapa de risco", "bi-map", current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False)),
            ):
                if enabled and can_access_endpoint(current_user, endpoint, "GET", legacy=coordinator):
                    navigation.append(dict(key=key, endpoint=endpoint, label=label, icon=icon))
        prefeitura = getattr(current_user, "prefeitura_id", None)
        if is_admin_global_user(current_user):
            raw = request.args.get("prefeitura_id", "")
            prefeitura = int(raw) if raw.isascii() and raw.isdecimal() and len(raw) <= 10 else None
        ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
        return {"vigilancia_coordena_campo": coordinator, "vigilancia_navigation": navigation,
                "vigilancia_context_prefeitura": prefeitura, "vigilancia_context_ibge": ibge}

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
        legacy = can_coordinate_field(current_user)
        administration = is_admin_global_user(current_user) or is_prefeitura_admin_user(current_user)
        if not route_access(current_user, legacy):
            abort(403)

        def allowed(endpoint, default=legacy):
            return can_access_endpoint(current_user, endpoint, "GET", legacy=default)

        cards = []
        if allowed("main.vigilancia_sinan"):
            cards.append({
                "id": "sinan", "eyebrow": "Epidemiologia", "title": "SINAN · Arboviroses",
                "icon": "bi-activity",
                "description": "Consultar e importar notificações de dengue, zika e chikungunya.",
                "endpoint": "main.vigilancia_sinan" if current_app.config.get("SINAN_ENABLED", True) else None,
                "action": "Acessar SINAN", "secondary": None,
            })
        if allowed("main.vigilancia_campo"):
            cards.append({
                "id": "campo", "eyebrow": "Campo e indicadores", "title": "Focal e LIRAa",
                "icon": "bi-clipboard-data",
                "description": "Planejar o levantamento, atribuir agentes e registrar visitas.",
                "endpoint": "main.vigilancia_campo" if current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) else None,
                "action": "Acessar Focal e LIRAa", "secondary": None,
            })
        if allowed("main.vigilancia_resultados"):
            cards.append({
                "id": "resultados", "eyebrow": "Análise territorial", "title": "Resultados da vigilância",
                "icon": "bi-map",
                "description": "Conferir IIP, Breteau, recipientes e comparações com o SINAN.",
                "endpoint": "main.vigilancia_resultados" if current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) else None,
                "action": "Consultar resultados", "secondary": None,
            })
        if legacy and allowed("main.vigilancia_risco"):
            cards.append({
                "id": "risco", "eyebrow": "Prioridade territorial", "title": "Mapa de risco",
                "icon": "bi-layers",
                "description": "Ver as visitas e o IIP no território, ou analisar o histórico de casos.",
                "endpoint": "main.vigilancia_risco" if current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) else None,
                "action": "Consultar mapa de risco", "secondary": None,
            })
        if allowed("main.vigilancia_pendentes"):
            cards.append({
                "id": "pendentes", "eyebrow": "Redução de pendências", "title": "Imóveis pendentes",
                "icon": "bi-house-exclamation",
                "description": "Imóveis fechados, recusados ou desabitados, com fotos e vídeos da tentativa de inspeção.",
                "endpoint": "main.vigilancia_pendentes", "action": "Ver imóveis pendentes", "secondary": None,
            })
        if "main.integracoes_esus" in current_app.view_functions and allowed("main.integracoes_esus"):
            cards.append({
                "id": "esus", "eyebrow": "Integração Ministério da Saúde", "title": "e-SUS APS (PEC)",
                "icon": "bi-hospital",
                "description": "Visitas de ACS/ACE e cadastro de domicílios sincronizados do PEC, com API para terceiros.",
                "endpoint": "main.integracoes_esus", "action": "Abrir integração e-SUS", "secondary": None,
            })
        can_import = allowed("main.vigilancia_importacoes")
        can_preview = allowed("main.vigilancia_validacao", administration)
        if can_import or can_preview:
            import_enabled = can_import and current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False)
            preview_enabled = can_preview and current_app.config.get("VIGILANCIA_PREVIEW_ENABLED", False)
            endpoint = "main.vigilancia_importacoes" if import_enabled else "main.vigilancia_validacao" if preview_enabled else None
            cards.append({
                "id": "arquivos", "eyebrow": "Gestão dos dados", "title": "Importação e validação",
                "icon": "bi-file-earmark-check",
                "description": "Importar CSV, revisar inconsistências e confirmar cargas.",
                "endpoint": endpoint,
                "action": "Acessar arquivos" if import_enabled else "Validar arquivo",
                "secondary": "main.vigilancia_validacao" if import_enabled and preview_enabled else None,
            })
        if allowed("main.vigilancia_migracao"):
            cards.append({
                "id": "migracao", "eyebrow": "Gestão dos dados", "title": "Migração de dados",
                "icon": "bi-database-up",
                "description": "Extrair, validar e carregar dados dos sistemas legados (SISPNCD, SISLOC, SINAN e planilhas da SMS).",
                "endpoint": "main.vigilancia_migracao" if current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) else None,
                "action": "Migrar dados", "secondary": None,
            })
        if current_app.config.get('ACOES_PUBLICAS_ENABLED', False):
            from app.modules.acoes_publicas.service import allowed as actions_allowed, ready
            if actions_allowed() and ready():
                cards.append({
                    'id': 'acoes-publicas', 'eyebrow': 'Divulgação municipal', 'title': 'Ações realizadas',
                    'icon': 'bi-megaphone', 'description': 'Prepare rascunhos, revise fotos e vídeos e publique as atividades autorizadas no Portal do Cidadão.',
                    'endpoint': 'main.acoes_listar', 'action': 'Gerenciar ações', 'secondary': None,
                })
        return render_template("vigilancia_central.html", vigilancia_cards=cards,
            can_plan=current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False) and allowed("main.vigilancia_planejamento"))
