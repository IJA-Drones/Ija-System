from flask import jsonify, request
from flask_login import current_user, login_required

from app.modules.chatbot.service import (
    ChatKitConfigurationError,
    ChatKitRequestError,
    build_admin_chatkit_session,
    build_login_chatkit_session,
    build_uvis_chatkit_session,
    can_access_admin_chatbot,
)


def register_routes(bp):
    @bp.route("/api/login/chatkit/session", methods=["POST"], endpoint="login_chatkit_session")
    def login_chatkit_session():
        try:
            return jsonify(build_login_chatkit_session()), 200
        except ChatKitConfigurationError as exc:
            return jsonify({"error": str(exc)}), 503
        except ChatKitRequestError as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.route("/api/uvis/chatkit/session", methods=["POST"], endpoint="uvis_chatkit_session")
    @login_required
    def uvis_chatkit_session():
        user_identifier = f"uvis_{getattr(current_user, 'id', 'anon')}"
        try:
            return jsonify(build_uvis_chatkit_session(user_identifier=user_identifier)), 200
        except ChatKitConfigurationError as exc:
            return jsonify({"error": str(exc)}), 503
        except ChatKitRequestError as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.route("/api/uvis/chatbot", methods=["POST"], endpoint="uvis_chatbot")
    @login_required
    def uvis_chatbot_legacy():
        return jsonify({"answer": "O assistente UVIS antigo foi substituido. Atualize esta tela para usar ChatKit."}), 410

    @bp.route("/api/admin/chatkit/session", methods=["POST"], endpoint="admin_chatkit_session")
    @login_required
    def admin_chatkit_session():
        if not can_access_admin_chatbot(current_user):
            return jsonify({"error": "Acesso negado para este assistente."}), 403

        user_identifier = f"admin_{getattr(current_user, 'id', 'anon')}"
        try:
            return jsonify(build_admin_chatkit_session(user_identifier=user_identifier)), 200
        except ChatKitConfigurationError as exc:
            return jsonify({"error": str(exc)}), 503
        except ChatKitRequestError as exc:
            return jsonify({"error": str(exc)}), 502

    @bp.route("/api/admin/chatbot", methods=["POST"], endpoint="admin_chatbot")
    @login_required
    def admin_chatbot_legacy():
        if not can_access_admin_chatbot(current_user):
            return jsonify({"answer": "Acesso negado para este assistente."}), 403
        return jsonify({"answer": "O assistente admin antigo foi substituido. Atualize esta tela para usar ChatKit."}), 410
