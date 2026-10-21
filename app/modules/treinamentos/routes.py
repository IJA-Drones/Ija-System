from flask import abort, current_app, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.modules.gestao_ti.permissions import can_access_endpoint, profile_code
from app.modules.vigilancia.access import can_coordinate_field
from .catalog import GUIDE_GROUPS, MATERIALS, RESOURCE_DIR, SECTIONS


def _module_url(section):
    endpoint = section["endpoint"]
    role = profile_code(current_user)
    if role == "agente_endemias" and section["id"] == "liraa":
        endpoint = "main.vigilancia_agente"
    if not current_app.config.get(section["flag"], section["flag"] == "SINAN_ENABLED"):
        return None
    if endpoint not in current_app.view_functions:
        return None
    legacy = can_coordinate_field(current_user)
    if section["id"] == "publicacoes":
        from app.modules.acoes_publicas.service import allowed, ready
        legacy = allowed() and ready()
    elif endpoint == "main.vigilancia_agente":
        legacy = True
    if not can_access_endpoint(current_user, endpoint, "GET", legacy=legacy):
        return None
    return url_for(endpoint, demo="true")


def register_routes(bp):
    @bp.after_request
    def training_private_cache(response):
        if (request.endpoint or "").startswith("main.treinamentos"):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.get("/treinamentos", endpoint="treinamentos")
    @login_required
    def index():
        sections = [dict(section, module_url=_module_url(section)) for section in SECTIONS]
        return render_template("treinamentos.html", sections=sections, guide_groups=GUIDE_GROUPS)

    @bp.get("/treinamentos/arquivos/<material_id>", endpoint="treinamentos_arquivo")
    @login_required
    def material(material_id):
        entry = MATERIALS.get(material_id)
        if entry is None:
            abort(404)
        relative_path, mimetype = entry
        path = RESOURCE_DIR / relative_path
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype=mimetype, download_name=path.name,
                         as_attachment=mimetype != "application/pdf" or request.args.get("baixar") == "1")

