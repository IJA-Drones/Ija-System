"""Indicadores públicos do SINAN, isolados dos dados operacionais da prefeitura."""

from datetime import datetime
from functools import wraps

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user

from app.modules.gestao_ti.permissions import route_access
from .access import can_coordinate_field

from . import sinan


def _access_required(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        is_api = request.path.startswith("/api/")
        status, message = None, None
        if not current_app.config.get("SINAN_ENABLED", True):
            status, message = 404, "Funcionalidade indisponível."
        elif not current_user.is_authenticated:
            if not is_api:
                return current_app.login_manager.unauthorized()
            status, message = 401, "Autenticação necessária."
        elif not route_access(current_user, can_coordinate_field(current_user)):
            status, message = 403, "Acesso restrito à administração responsável."
        if status:
            if is_api:
                return jsonify(error=message), status
            abort(status, description=message)
        return view(*args, **kwargs)
    return guarded


def register_routes(bp):
    from .sinan_workflow_routes import register_routes as register_workflow, token
    register_workflow(bp)

    @bp.after_request
    def vigilancia_sinan_no_cache(response):
        if (request.endpoint or "").startswith("main.vigilancia_sinan"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.get("/vigilancia/sinan", endpoint="vigilancia_sinan")
    @_access_required
    def vigilancia_sinan():
        from .results import municipality_ibge
        from app.shared.access import is_admin_global_user
        prefeitura = getattr(current_user, "prefeitura_id", None)
        raw_prefeitura = request.args.get("prefeitura_id", "")
        if is_admin_global_user(current_user) and raw_prefeitura.isascii() and raw_prefeitura.isdecimal() and len(raw_prefeitura) <= 10:
            prefeitura = int(raw_prefeitura)
        default_ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
        default_ibge = default_ibge or str(current_app.config.get("INFODENGUE_GEOCODE", "3550308"))
        selected_ibge = request.args.get("ibge") or default_ibge
        if selected_ibge not in sinan.MUNICIPALITIES_BY_IBGE:
            selected_ibge = "3550308"
        return render_template(
            "vigilancia_sinan.html", municipalities=sinan.MUNICIPALITIES,
            diseases=sinan.DISEASES, current_year=datetime.now().year,
            source_url=sinan.DISEASES["dengue"]["source_url"], region_url=sinan.REGION_URL,
            catalog_checked_at=sinan.CATALOG_CHECKED_AT,
            sinan_csrf_token=token(),
            sinan_import_enabled=current_app.config.get("SINAN_IMPORT_ENABLED", True),
            selected_ibge=selected_ibge,
        )

    @bp.get("/api/vigilancia/sinan", endpoint="vigilancia_sinan_api")
    @_access_required
    def vigilancia_sinan_api():
        if set(request.args) - {"ibge", "year", "offset", "disease"} or any(len(request.args.getlist(key)) != 1 for key in request.args):
            return jsonify(error="Parâmetros inválidos para a consulta."), 400
        disease = request.args.get("disease", "dengue")
        if disease not in sinan.DISEASES:
            return jsonify(error="Selecione dengue, zika ou chikungunya."), 400
        ibge = request.args.get("ibge", "")
        try:
            year = int(request.args.get("year", ""))
            offset = int(request.args.get("offset", "0"))
        except ValueError:
            return jsonify(error="Informe município, ano e posição válidos."), 400
        if ibge not in sinan.MUNICIPALITIES_BY_IBGE or not 2015 <= year <= datetime.now().year or not 0 <= offset < sinan.MAX_RECORDS or offset % sinan.PAGE_SIZE:
            return jsonify(error="Informe município, ano e posição válidos."), 400
        try:
            return jsonify(sinan.fetch_page(ibge=ibge, year=year, offset=offset, disease=disease))
        except sinan.SinanError as exc:
            return jsonify(error=str(exc)), 502
