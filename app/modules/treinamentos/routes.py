from flask import abort, current_app, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.modules.gestao_ti.permissions import can_access_endpoint, profile_code
from app.modules.vigilancia.access import can_coordinate_field
from .catalog import GUIDE_GROUPS, MATERIALS, REQUEST_VIDEOS, RESOURCE_DIR, SECTIONS
from .access import POLICIES, can_read_material

TRAINING_ENDPOINTS = {"main.treinamentos", "main.agro_treinamentos", "main.financeiro_treinamentos",
                      "main.treinamentos_arquivo"}
AREAS = {"prefeitura": ("Prefeitura e Sistema", "main.treinamentos"),
         "agro": ("Agro", "main.agro_treinamentos"),
         "financeiro": ("Financeiro", "main.financeiro_treinamentos")}


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
    params = {"demo": "true"}
    if section["id"] == "liraa" and endpoint == "main.vigilancia_planejamento":
        params.update(fluxo="levantamento", etapa="1", _anchor="novo-levantamento")
    return url_for(endpoint, **params)


def register_routes(bp):
    @bp.after_request
    def training_private_cache(response):
        if request.endpoint in TRAINING_ENDPOINTS:
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.get("/treinamentos", endpoint="treinamentos")
    @login_required
    def index():
        return _index()

    @bp.get("/agro/treinamentos", endpoint="agro_treinamentos")
    @login_required
    def agro_index():
        return _index("agro")

    @bp.get("/financeiro/treinamentos", endpoint="financeiro_treinamentos")
    @login_required
    def financeiro_index():
        return _index("financeiro")

    @bp.get("/treinamentos/arquivos/<material_id>", endpoint="treinamentos_arquivo")
    @login_required
    def material(material_id):
        entry = MATERIALS.get(material_id)
        if entry is None:
            abort(404)
        if not can_read_material(current_user, material_id):
            abort(403)
        relative_path, mimetype = entry
        path = RESOURCE_DIR / relative_path
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype=mimetype, download_name=path.name,
                         as_attachment=mimetype not in {"application/pdf", "video/mp4"} or request.args.get("baixar") == "1")


def _index(area=None):
    from flask import redirect
    from app.modules.agro.service import can_access_agro_panel
    from app.shared.access import can_access_financeiro_panel
    allowed = {key for key in POLICIES if can_read_material(current_user, key)}
    areas = {POLICIES[key].area for key in allowed} - {"common"}
    if can_access_agro_panel(current_user) or profile_code(current_user) == "piloto_agro":
        areas.add("agro")
    if can_access_financeiro_panel(current_user):
        areas.add("financeiro")
    if not areas:
        areas.add("prefeitura")
    if area is None:
        area = next(key for key in AREAS if key in areas)
        if area != "prefeitura":
            return redirect(url_for(AREAS[area][1]))
    if area not in areas:
        abort(403)
    visible = {key for key in allowed if POLICIES[key].area in {area, "common"}}
    request_videos = [video for video in REQUEST_VIDEOS if video["id"] in visible]
    sections = [dict(section, module_url=_module_url(section)) for section in SECTIONS
                if section["manual"] in visible]
    groups = []
    for group in GUIDE_GROUPS:
        documents = tuple(doc for doc in group["documents"] if doc[0] in visible)
        if documents:
            groups.append(dict(group, documents=documents))
    tabs = [dict(id=key, title=label, url=url_for(endpoint))
            for key, (label, endpoint) in AREAS.items() if key in areas]
    return render_template("treinamentos.html", sections=sections, guide_groups=groups,
                           training_tabs=tabs, training_area=area, available_materials=visible,
                           request_videos=request_videos)

