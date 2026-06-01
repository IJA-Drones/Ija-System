from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from app.modules.drones_import.service import import_drone_spreadsheet
from app.shared.access import normalize_role


IMPORT_ALLOWED_ROLES = {"admin", "operario", "operador", "prefeitura_admin"}


def _require_import_permission():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in IMPORT_ALLOWED_ROLES:
        abort(403)


def _parse_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _resolve_prefeitura_id():
    raw_prefeitura_id = (request.form.get("prefeitura_id") or "").strip()
    try:
        prefeitura_id = int(raw_prefeitura_id)
    except (TypeError, ValueError):
        prefeitura_id = None

    user_prefeitura_id = getattr(current_user, "prefeitura_id", None)
    if normalize_role(getattr(current_user, "tipo_usuario", None)) != "admin":
        if user_prefeitura_id is None:
            abort(403)
        if prefeitura_id is not None and prefeitura_id != user_prefeitura_id:
            abort(403)
        return user_prefeitura_id

    return prefeitura_id


def _render_import_page(default_agro=False):
    _require_import_permission()
    return render_template(
        "drones_importar_planilha.html",
        default_agro=default_agro,
        default_prefeitura_id=getattr(current_user, "prefeitura_id", None),
    )


def register_routes(bp):
    @bp.route("/drones/importar-planilha", methods=["GET"], endpoint="importar_planilha_drones")
    @login_required
    def importar_planilha_drones():
        return _render_import_page(default_agro=False)

    @bp.route("/agro/equipamentos/importar-planilha", methods=["GET"], endpoint="agro_importar_planilha_drones")
    @login_required
    def agro_importar_planilha_drones():
        return _render_import_page(default_agro=True)

    @bp.route("/api/drones/importar-planilha", methods=["POST"], endpoint="importar_planilha_drones_api")
    @login_required
    def importar_planilha_drones_api():
        try:
            _require_import_permission()
            result = import_drone_spreadsheet(
                request.files.get("file"),
                agro=_parse_bool(request.form.get("agro")),
                prefeitura_id=_resolve_prefeitura_id(),
            )
        except HTTPException as exc:
            return jsonify({"success": False, "error": exc.description or "Acesso negado."}), exc.code or 403
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        return jsonify({"success": True, **result})
