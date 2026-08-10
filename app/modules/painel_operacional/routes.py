from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.modules.painel_operacional.service import (
    build_operational_context,
    can_access_operational_panel,
    get_operational_panel_maps_key,
)


def register_routes(bp):
    @bp.route("/diretor/painel-operacional", methods=["GET"], endpoint="painel_operacional")
    @login_required
    def painel_operacional():
        if not can_access_operational_panel(current_user):
            return render_template(
                "erro.html",
                codigo=403,
                titulo="Acesso restrito",
                mensagem="Você não tem permissão para acessar o Painel Operacional.",
            ), 403

        return render_template(
            "painel_operacional.html",
            google_maps_key=get_operational_panel_maps_key(),
        )

    @bp.route("/api/painel-operacional/contexto-local", methods=["POST"], endpoint="api_painel_operacional_contexto")
    @login_required
    def api_painel_operacional_contexto():
        if not can_access_operational_panel(current_user):
            return jsonify({"ok": False, "error": "Acesso restrito."}), 403

        data = request.get_json(silent=True) or {}
        address = (data.get("address") or "").strip()
        try:
            return jsonify(build_operational_context(current_user, address)), 200
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            current_app.logger.exception("Erro ao montar contexto operacional.")
            return jsonify({"ok": False, "error": "Não foi possível consultar o contexto local agora."}), 502
