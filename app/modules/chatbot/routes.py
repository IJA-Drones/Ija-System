from app.modules.gestao_ti.permissions import route_access, can_access_endpoint
from flask import jsonify, request, url_for, session
from flask_login import current_user, login_required, user_logged_in, user_logged_out
import secrets

from app.modules.chatbot.azul import reply as azul_reply

from app.modules.chatbot.service import (
    can_access_admin_chatbot,
    can_access_agro_admin_chatbot,
    can_access_agro_piloto_chatbot,
)


def register_routes(bp):
    @bp.record_once
    def chat_session_signals(state):
        def reset_chat_session(sender, **kwargs):
            session.pop('azul_chat_id', None)
        user_logged_in.connect(reset_chat_session, sender=state.app, weak=False)
        user_logged_out.connect(reset_chat_session, sender=state.app, weak=False)
    from app.modules.chatbot.exports import register_routes as register_exports
    register_exports(bp)
    @bp.app_context_processor
    def azul_widget_context():
        allowed = (current_user.is_authenticated
                   and not (request.endpoint or '').startswith(('main.portal_', 'auth.', 'main.mobile_'))
                   and can_access_endpoint(current_user, 'main.azul_help', 'POST', legacy=True))
        from app.modules.chatbot.exports import allowed_sources
        from app.modules.chatbot.operations import allowed as operations_allowed
        from app.modules.chatbot.search import allowed as search_allowed
        if allowed and not session.get('azul_chat_id'):
            session['azul_chat_id'] = secrets.token_urlsafe(24)
        return {'azul_chat_key': f"{current_user.get_id()}:{session['azul_chat_id']}" if allowed else '',
                'azul_help_url': url_for('main.azul_help') if allowed else None,
                'azul_can_export': bool(allowed_sources(current_user)) if allowed else False,
                'azul_can_view_operations': operations_allowed(current_user) if allowed else False,
                'azul_can_search': search_allowed(current_user) if allowed else False}

    @bp.route('/api/azul/ajuda', methods=['POST'], endpoint='azul_help')
    @login_required
    def azul_help():
        if not route_access(current_user, True):
            return jsonify(answer='Seu perfil não tem acesso à Azul nesta área.'), 403
        return azul_reply('sistema')

    @bp.route("/api/uvis/chatbot", methods=["POST"], endpoint="uvis_chatbot")
    @login_required
    def uvis_chatbot():
        if not route_access(current_user, current_user.tipo_usuario == "uvis"):
            return jsonify(answer="Seu perfil não tem acesso à Azul nesta área."), 403
        return azul_reply("uvis")

    @bp.route("/api/admin/chatbot", methods=["POST"], endpoint="admin_chatbot")
    @login_required
    def admin_chatbot():
        if not route_access(current_user, can_access_admin_chatbot(current_user)):
            return jsonify({"answer": "Acesso negado para este chatbot."}), 403

        return azul_reply("admin")

    @bp.route("/api/agro/admin/chatbot", methods=["POST"], endpoint="agro_admin_chatbot")
    @login_required
    def agro_admin_chatbot():
        if not route_access(current_user, can_access_agro_admin_chatbot(current_user)):
            return jsonify({"answer": "Acesso negado para este chatbot do Agro."}), 403

        return azul_reply("agro_admin")

    @bp.route("/api/agro/piloto/chatbot", methods=["POST"], endpoint="agro_piloto_chatbot")
    @login_required
    def agro_piloto_chatbot():
        if not route_access(current_user, can_access_agro_piloto_chatbot(current_user)):
            return jsonify({"answer": "Acesso negado para este chatbot do piloto Agro."}), 403

        return azul_reply("agro_piloto")
