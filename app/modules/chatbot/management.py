"""Developer-only control panel plus a deliberately minimal public audio policy."""
import hmac
import json
import re
import secrets

import sqlalchemy as sa
from flask import abort, g, jsonify, make_response, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.shared.access import is_dev_user
from app.modules.chatbot import control_store, metering, recordings, settings
from app.modules.chatbot.scope import chat_key
from app.modules.gestao_ti.permissions import can_access_endpoint


def require_dev():
    if not is_dev_user(current_user):
        abort(403,description='Somente o perfil dev pode gerenciar a AZUL.')


def csrf():
    if not session.get('azul_control_csrf'):
        session['azul_control_csrf'] = secrets.token_urlsafe(32)
    return session['azul_control_csrf']


def body(limit=40000):
    if not request.is_json:
        abort(415)
    raw = request.stream.read(limit+1)
    if len(raw)>limit:
        abort(413)
    try:
        data = json.loads(raw)
    except (ValueError,UnicodeError):
        abort(400)
    if not isinstance(data,dict):
        abort(400)
    return data


def register_routes(bp):
    @bp.app_errorhandler(control_store.BudgetExceeded)
    def budget_error(error):
        return jsonify(error=str(error),answer=str(error),code='azul_budget'),429

    @bp.app_errorhandler(control_store.Conflict)
    def conflict_error(error):
        return jsonify(error=str(error)),409

    @bp.app_errorhandler(control_store.StoreError)
    def store_error(error):
        return jsonify(error=str(error),answer=str(error)),503

    @bp.get('/azul/configuracoes',endpoint='azul_settings')
    @login_required
    def page():
        require_dev()
        cfg = settings.current()
        with control_store.current().connection() as conn:
            history = [dict(row) for row in conn.execute(sa.select(control_store.audit)
                .order_by(control_store.audit.c.created_at.desc()).limit(10)).mappings()]
        for row in history:
            row['fields'] = ', '.join(json.loads(row['fields'])) or 'Sem mudança de valores'
        return render_template('azul_settings.html',azul_settings=cfg,control_csrf=csrf(),
            text_models=settings.TEXT_MODELS,voice_models=settings.VOICE_MODELS,
            transcribe_models=settings.TRANSCRIBE_MODELS,voices=settings.VOICES,history=history)

    @bp.route('/api/azul/configuracoes',methods=['GET','POST'],endpoint='azul_settings_api')
    @login_required
    def config_api():
        require_dev()
        if request.method=='GET':
            return jsonify(settings.current())
        token = request.headers.get('X-Azul-Config-CSRF','')
        expected = session.get('azul_control_csrf','')
        if not expected or not hmac.compare_digest(expected,token):
            return jsonify(error='Recarregue as configurações antes de salvar.'),403
        data = body()
        if set(data)!={'revision','settings'}:
            return jsonify(error='Envie a versão e as configurações.'),400
        try:
            saved = settings.save(data['settings'],data['revision'],current_user.get_id())
        except settings.ValidationError as error:
            return jsonify(error=str(error)),400
        return jsonify(settings=saved,message='Configurações da AZUL salvas.')

    @bp.get('/api/azul/consumo',endpoint='azul_usage')
    @login_required
    def usage():
        require_dev()
        try:
            days = int(request.args.get('days','30'))
        except ValueError:
            abort(400)
        channel = request.args.get('channel','all')
        if not 1<=days<=90 or channel not in ('all','public','internal'):
            abort(400)
        return jsonify(metering.summary(days,channel))

    @bp.get('/api/azul/politica',endpoint='azul_audio_policy')
    def policy():
        return jsonify(settings.policy(public=request.args.get('audience')=='public'))

    @bp.post('/api/azul/audio-evento',endpoint='azul_audio_event')
    def audio_event():
        public_token = request.headers.get('X-Portal-Chat-Token')
        if public_token:
            expected = session.get('portal_chat_token','')
            if not expected or not hmac.compare_digest(expected,public_token):
                abort(403)
        else:
            if not current_user.is_authenticated:
                abort(401)
            if not can_access_endpoint(current_user,'main.azul_help','POST',legacy=True):
                abort(403)
            if not hmac.compare_digest(request.headers.get('X-Azul-Chat-Key',''),chat_key(current_user)):
                abort(409)
        data = body(1024)
        clip,event_id = data.get('clip',''),data.get('event_id','')
        if (set(data)!={'clip','event_id'} or not isinstance(clip,str) or not isinstance(event_id,str)
                or not re.fullmatch(r'[a-f0-9]{32}',event_id)):
            abort(400)
        known = clip in ('/static/audio/azul-inicio-chamada.wav','/static/audio/azul-escopo-chamada.wav')
        match = re.fullmatch(r'/static/audio/azul-falas/([a-f0-9]{64})\.wav(?:\?v=[a-f0-9]{12})?',clip)
        if match:
            path = recordings.DIRECTORY/(match[1]+'.wav')
            known = path.is_file()
        if not known:
            abort(400)
        if settings.policy()['sound_enabled']:
            metering.free('voice','recorded',event_id)
        return '',204

    @bp.after_app_request
    def management_headers(response):
        if request.endpoint in {'main.azul_settings','main.azul_settings_api','main.azul_usage',
                                'main.azul_audio_policy','main.azul_audio_event'}:
            response.headers['Cache-Control']='private, no-store'
            response.headers['X-Content-Type-Options']='nosniff'
        return response
