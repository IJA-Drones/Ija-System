from flask import jsonify, request
from flask_login import current_user, login_required

from app.modules.chatbot.service import (
    build_admin_chatbot_response,
    build_agro_admin_chatbot_response,
    build_agro_piloto_chatbot_response,
    build_uvis_chatbot_response,
    can_access_admin_chatbot,
    can_access_agro_admin_chatbot,
    can_access_agro_piloto_chatbot,
)


def register_routes(bp):
    @bp.route("/api/uvis/chatbot", methods=["POST"], endpoint="uvis_chatbot")
    @login_required
    def uvis_chatbot():
        payload = request.get_json(silent=True) or {}
        response_payload, status_code = build_uvis_chatbot_response(payload.get("message"))
        return jsonify(response_payload), status_code

    @bp.route("/api/admin/chatbot", methods=["POST"], endpoint="admin_chatbot")
    @login_required
    def admin_chatbot():
        if not can_access_admin_chatbot(current_user):
            return jsonify({"answer": "Acesso negado para este chatbot."}), 403

        payload = request.get_json(silent=True) or {}
        response_payload, status_code = build_admin_chatbot_response(payload.get("message"))
        return jsonify(response_payload), status_code

    @bp.route("/api/agro/admin/chatbot", methods=["POST"], endpoint="agro_admin_chatbot")
    @login_required
    def agro_admin_chatbot():
        if not can_access_agro_admin_chatbot(current_user):
            return jsonify({"answer": "Acesso negado para este chatbot do Agro."}), 403

        payload = request.get_json(silent=True) or {}
        response_payload, status_code = build_agro_admin_chatbot_response(payload.get("message"))
        return jsonify(response_payload), status_code

    @bp.route("/api/agro/piloto/chatbot", methods=["POST"], endpoint="agro_piloto_chatbot")
    @login_required
    def agro_piloto_chatbot():
        if not can_access_agro_piloto_chatbot(current_user):
            return jsonify({"answer": "Acesso negado para este chatbot do piloto Agro."}), 403

        payload = request.get_json(silent=True) or {}
        response_payload, status_code = build_agro_piloto_chatbot_response(payload.get("message"))
        return jsonify(response_payload), status_code
