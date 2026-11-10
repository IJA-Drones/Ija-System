from app.modules.gestao_ti.permissions import route_access, can_access_endpoint
from flask import abort, current_app, jsonify, make_response, render_template, request, url_for, session
from flask_login import current_user, login_required, user_logged_in, user_logged_out
from app.modules.chatbot.scope import chat_key

from app.modules.chatbot.azul import reply as azul_reply
from app.modules.chatbot import voice

from app.modules.chatbot.service import (
    can_access_admin_chatbot,
    can_access_agro_admin_chatbot,
    can_access_agro_piloto_chatbot,
)


def register_routes(bp):
    @bp.get('/azul/tutorial', endpoint='azul_tutorial')
    def azul_tutorial():
        from app.modules.chatbot.tutorial import page
        return page()

    @bp.record_once
    def chat_session_signals(state):
        def reset_chat_session(sender, **kwargs):
            session.pop('azul_chat_id', None)
        user_logged_in.connect(reset_chat_session, sender=state.app, weak=False)
        user_logged_out.connect(reset_chat_session, sender=state.app, weak=False)
    from app.modules.chatbot.exports import register_routes as register_exports
    register_exports(bp)
    @bp.after_app_request
    def azul_narration_offer(response):
        if (response.status_code == 200 and response.is_json and current_user.is_authenticated
                and request.endpoint in {'main.azul_help', 'main.uvis_chatbot', 'main.admin_chatbot',
                                         'main.agro_admin_chatbot', 'main.agro_piloto_chatbot'}):
            payload = response.get_json(silent=True)
            if (isinstance(payload, dict) and isinstance(payload.get('answer'), str)
                    and payload.get('mode') not in {'blocked', 'clarify'}):
                payload['speech'] = voice.offer(payload['answer'], current_user)
                response.set_data(current_app.json.dumps(payload))
        return response

    @bp.app_context_processor
    def azul_widget_context():
        from app.modules.portal_cidadao.companion import PAGES as public_pages
        allowed = (current_user.is_authenticated
                   and request.endpoint != 'main.azul_tutorial'
                   and request.endpoint not in public_pages
                   and not (request.endpoint or '').startswith(('main.portal_', 'auth.', 'main.mobile_'))
                   and can_access_endpoint(current_user, 'main.azul_help', 'POST', legacy=True))
        from app.modules.chatbot.exports import allowed_sources
        from app.modules.chatbot.operations import allowed as operations_allowed
        from app.modules.chatbot.search import allowed as search_allowed
        from app.modules.chatbot.guide import build as build_guide
        from app.modules.chatbot.speech_input import available as microphone_available
        return {'azul_chat_key': chat_key(current_user) if allowed else '',
                'azul_help_url': url_for('main.azul_help') if allowed else None,
                'azul_page_url': url_for('main.azul_chat') if allowed and can_access_endpoint(
                    current_user, 'main.azul_chat', 'GET', legacy=True) else None,
                'azul_can_export': bool(allowed_sources(current_user)) if allowed else False,
                'azul_can_view_operations': operations_allowed(current_user) if allowed else False,
                'azul_can_search': search_allowed(current_user) if allowed else False,
                'azul_guide': build_guide(current_user, request.path) if allowed else [],
                'azul_tutorial_url': url_for('main.azul_tutorial', publico='sistema') if allowed else None,
                'azul_transcribe_url': url_for('main.azul_transcribe') if allowed and microphone_available() else '',
                'azul_voice_available': voice.available() if allowed else False}

    @bp.post('/api/azul/voz', endpoint='azul_voice')
    @login_required
    def azul_voice():
        response = make_response(voice.reply())
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @bp.post('/api/azul/transcrever', endpoint='azul_transcribe')
    @login_required
    def azul_transcribe():
        from app.modules.chatbot.speech_input import reply
        response = make_response(reply())
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @bp.get('/azul', endpoint='azul_chat')
    @login_required
    def azul_chat():
        if (not route_access(current_user, True)
                or not can_access_endpoint(current_user, 'main.azul_help', 'POST', legacy=True)):
            abort(403, description='Seu perfil não tem acesso à Azul nesta área.')
        response = make_response(render_template('azul_chat.html'))
        response.headers['Cache-Control'] = 'private, no-store'
        return response

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
