from concurrent.futures import ThreadPoolExecutor
import base64
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Blueprint, Flask, session
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
import pytest
import sqlalchemy as sa

from app.modules.chatbot import azul, control_store, metering, settings, speech_input, voice
from app.modules.chatbot.routes import register_routes
from app.modules.portal_cidadao import chatbot
from app.modules.portal_cidadao.routes import register_routes as register_public
from tests.test_azul_help import User
from tests.test_azul_speech_input import wav

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {'perfil':'dev','permissoes_completas':True,'capacidades':[],
           'pagina_atual':'AZUL','atalhos':[]}


def make_app(tmp_path):
    app = Flask('azul-control-tests',instance_path=str(tmp_path),static_folder=str(ROOT/'app/static'),template_folder=str(ROOT/'app/templates'))
    app.config.update(TESTING=True,SECRET_KEY='management-test-secret',OPENAI_API_KEY='not-a-real-key',
        AZUL_CONTROL_DATABASE_URI='sqlite:///'+str(tmp_path/'control.sqlite'))
    user = User()
    manager = LoginManager(app)
    manager.user_loader(lambda uid:user)
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html':'''<!doctype html><html><head>{% block extra_styles %}{% endblock %}</head><body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>'''}),FileSystemLoader(str(ROOT/'app/templates'))])
    bp = Blueprint('main',__name__)
    register_routes(bp);register_public(bp);app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as state:
        state['_user_id']='9';state['_fresh']=True;state['azul_control_csrf']='control-test'
        state['portal_chat_token']='public-test'
    return app,client,user


@pytest.fixture
def env(tmp_path):
    with patch('app.modules.chatbot.guide.build',return_value=[]),patch.object(
            azul,'help_context',return_value=CONTEXT):
        yield make_app(tmp_path)


def save(client, changes):
    current = client.get('/api/azul/configuracoes').json or {'revision':0}
    return client.post('/api/azul/configuracoes',json={'revision':current['revision'],'settings':changes},
                       headers={'X-Azul-Config-CSRF':'control-test'})


def response(usage=True):
    return SimpleNamespace(id='resp_test',status='completed',output_text='Use o guia do sistema.',output=[],
        usage=SimpleNamespace(input_tokens=100,output_tokens=50,total_tokens=150,
                              input_tokens_details=SimpleNamespace(cached_tokens=20)) if usage else None)


@pytest.mark.parametrize('role',['diretor','admin','uvis','gestor_ti','piloto_agro'])
def test_management_is_fixed_dev_only_even_if_the_user_can_access_chat(env,role):
    _,client,user = env
    user.tipo_usuario=role
    for url in ('/azul/configuracoes','/api/azul/configuracoes','/api/azul/consumo'):
        assert client.get(url).status_code==403
    assert save(client,{'sound_enabled':False}).status_code==403


def test_controls_require_login_and_private_values_never_enter_the_public_policy(env):
    app,client,_ = env
    assert save(client,{'internal_context':'PRIVATE-CONTEXT-SENTINEL'}).status_code==200
    anonymous=app.test_client()
    for url in ('/api/azul/configuracoes','/api/azul/consumo'):
        assert anonymous.get(url).status_code==401
    policy=anonymous.get('/api/azul/politica')
    assert policy.status_code==200
    assert 'PRIVATE-CONTEXT-SENTINEL' not in policy.get_data(as_text=True)
    assert not set(policy.json)&{'internal_context','public_context','rates','internal_model','OPENAI_API_KEY'}


def test_settings_save_has_csrf_validation_and_conflict_detection(env):
    app,client,_ = env
    original=client.get('/api/azul/configuracoes').json
    data={'revision':original['revision'],'settings':{'sound_enabled':False}}
    assert client.post('/api/azul/configuracoes',json=data).status_code==403
    assert client.post('/api/azul/configuracoes',json=data,headers={'X-Azul-Config-CSRF':'wrong'}).status_code==403
    assert client.post('/api/azul/configuracoes',json=data,headers={'X-Azul-Config-CSRF':'control-test'}).status_code==200
    assert client.post('/api/azul/configuracoes',json=data,headers={'X-Azul-Config-CSRF':'control-test'}).status_code==409
    with app.app_context(),control_store.current().connection() as conn:
        history=conn.execute(sa.select(control_store.audit)).mappings().all()
    assert len(history)==1
    assert json.loads(history[0]['fields'])==['sound_enabled']


@pytest.mark.parametrize('changes',[
    {'sound_enabled':'false'},{'internal_model':'user-invented-model'},
    {'internal_context':'x'*6001},{'max_output_internal':10},{'session_minutes':100},
    {'daily_budget_brl':'NaN'},{'usd_brl':'0'},{'monthly_budget_brl':'-1'},
    {'name':'Jarvis'},{'rates':{}},{'fx_date':'bad-date'},
])
def test_invalid_controls_do_not_change_the_saved_revision(env,changes):
    _,client,_ = env
    before=client.get('/api/azul/configuracoes').json
    assert save(client,changes).status_code==400
    assert client.get('/api/azul/configuracoes').json['revision']==before['revision']


def test_configuration_survives_a_new_app_instance_without_touching_business_tables(env,tmp_path):
    app,client,_=env
    assert save(client,{'sound_enabled':False,'internal_context':'Orientação aprovada.'}).status_code==200
    other,other_client,_=make_app(tmp_path)
    assert other_client.get('/api/azul/configuracoes').json['internal_context']=='Orientação aprovada.'
    with other.app_context():
        assert set(sa.inspect(control_store.current().engine).get_table_names())=={
            'azul_configuracao','azul_configuracao_historico','azul_consumo'}


def test_runtime_model_context_and_response_limits_are_applied_and_metered(env):
    app,client,_=env
    assert save(client,{'internal_model':'gpt-6.1-terra','internal_context':'INTERNAL-REFERENCE',
                        'public_context':'PUBLIC-REFERENCE','max_output_internal':900}).status_code==200
    with patch.object(azul,'OpenAI') as sdk:
        call=sdk.return_value.__enter__.return_value.responses.create
        call.return_value=response()
        result=client.post('/api/azul/ajuda',json={'message':'Como usar o sistema?'},
                           headers={'X-Azul-Conversation':'a'*32})
    assert result.status_code==200
    kwargs=call.call_args.kwargs
    assert kwargs['model']=='gpt-6.1-terra' and kwargs['max_output_tokens']==900
    assert 'INTERNAL-REFERENCE' in kwargs['instructions'] and 'PUBLIC-REFERENCE' not in kwargs['instructions']
    assert 'nome permanente é AZUL' in kwargs['instructions']
    usage=client.get('/api/azul/consumo').json
    assert usage['totals']['tokens']==150 and usage['totals']['cost_brl']>0
    assert usage['recent'][0]['model']=='gpt-6.1-terra'
    with app.app_context(),control_store.current().connection() as conn:
        stored=json.dumps([dict(row) for row in conn.execute(sa.select(control_store.events)).mappings()])
    assert 'Como usar o sistema?' not in stored and 'INTERNAL-REFERENCE' not in stored


def test_public_model_only_receives_public_context_and_honors_search_switch(env):
    _,client,_=env
    assert save(client,{'public_model':'gpt-6.1-sol','internal_context':'PRIVATE-SENTINEL',
                        'public_context':'PUBLIC-SENTINEL','web_search_enabled':False,'max_output_public':800}).status_code==200
    with patch.object(chatbot,'OpenAI') as sdk:
        call=sdk.return_value.__enter__.return_value.responses.create
        call.return_value=response()
        result=client.post('/portal-cidadao/chatbot',json={'message':'Como prevenir dengue?'},
                           headers={'X-Portal-Chat-Token':'public-test'})
    assert result.status_code==200
    kwargs=call.call_args.kwargs
    assert kwargs['model']=='gpt-6.1-sol' and kwargs['max_output_tokens']==800
    assert 'PUBLIC-SENTINEL' in kwargs['instructions'] and 'PRIVATE-SENTINEL' not in kwargs['instructions']
    assert kwargs['tools']==[]


def test_cost_uses_cached_tokens_and_keeps_historical_fx_and_rates(env):
    _,client,_=env
    cfg=client.get('/api/azul/configuracoes').json
    rates=cfg['rates'];rates['gpt-6-luna']={'input':'1','cached_input':'0.1','output':'2'}
    assert save(client,{'usd_brl':'5','rates':rates}).status_code==200
    with patch.object(azul,'OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.return_value=response()
        assert client.post('/api/azul/ajuda',json={'message':'Como usar o sistema?'}).status_code==200
    assert save(client,{'usd_brl':'10'}).status_code==200
    usage=client.get('/api/azul/consumo').json
    assert usage['totals']['cost_brl']==910000


def test_global_sound_off_blocks_paid_narration_and_removes_offers_but_keeps_text(env):
    _,client,_=env
    signed=client.post('/api/azul/ajuda',json={'message':'Qual seu nome?'}).json['speech']
    assert save(client,{'sound_enabled':False}).status_code==200
    policy=client.get('/api/azul/politica').json
    assert not policy['sound_enabled'] and not policy['conversation_enabled'] and policy['microphone_enabled']
    with patch.object(voice,'synthesize') as provider:
        assert client.post('/api/azul/voz',json={'token':signed['token']}).status_code==503
        answer=client.post('/api/azul/ajuda',json={'message':'Qual seu nome?'}).json
    assert answer['speech'] is None and 'AZUL' in answer['answer']
    provider.assert_not_called()


def test_microphone_switch_and_shorter_audio_limit_are_enforced_on_the_server(env):
    _,client,_=env
    assert save(client,{'speech_seconds':3}).status_code==200
    headers={'X-Portal-Chat-Token':'public-test'}
    with patch.object(speech_input,'transcribe') as provider:
        assert client.post('/portal-cidadao/transcrever',data=wav(4),content_type='audio/wav',headers=headers).status_code==422
        assert save(client,{'microphone_enabled':False}).status_code==200
        assert client.post('/portal-cidadao/transcrever',data=wav(),content_type='audio/wav',headers=headers).status_code==503
        provider.assert_not_called()


def test_muted_call_cannot_spend_transcription_but_explicit_dictation_remains_available(env):
    _,client,_=env
    assert save(client,{'sound_enabled':False}).status_code==200
    headers={'X-Portal-Chat-Token':'public-test'}
    with patch.object(speech_input,'transcribe',return_value='Como usar o portal?') as provider:
        assert client.post('/portal-cidadao/transcrever',data=wav(),content_type='audio/wav',headers=headers).status_code==503
        assert client.post('/portal-cidadao/transcrever',data=wav(),content_type='audio/wav',
            headers={**headers,'X-Azul-Voice-Mode':'dictation'}).status_code==200
        provider.assert_called_once()


@pytest.mark.parametrize('budget_key',['daily_budget_brl','monthly_budget_brl'])
def test_daily_generation_limit_and_spend_limit_block_before_provider_calls(env,budget_key):
    _,client,_=env
    assert save(client,{'internal_daily_text':0}).status_code==200
    with patch.object(azul,'OpenAI') as sdk:
        result=client.post('/api/azul/ajuda',json={'message':'Como usar o sistema?'})
        sdk.assert_not_called();assert result.status_code==200 and result.json['mode']=='faq'
    assert save(client,{'internal_daily_text':500,budget_key:'0.000000001'}).status_code==200
    with patch.object(azul,'OpenAI') as sdk:
        result=client.post('/api/azul/ajuda',json={'message':'Como usar o sistema?'})
        sdk.return_value.__enter__.return_value.responses.create.assert_not_called()
    assert result.status_code==429 and result.json['code']=='azul_budget'


def test_parallel_reservations_cannot_spend_the_same_remaining_budget(env):
    app,client,_=env
    assert save(client,{'daily_budget_brl':'0.01'}).status_code==200
    def reserve(_):
        with app.test_request_context('/api/azul/ajuda'):
            try:
                return metering.start('text','gpt-6-luna',{'max_output_tokens':2500})
            except control_store.BudgetExceeded:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(reserve,range(2)))
    assert sum(value is not None for value in results)==1


def test_missing_usage_is_unknown_instead_of_zero_and_keeps_budget_reservation(env):
    _,client,_=env
    with patch.object(azul,'OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.return_value=response(usage=False)
        assert client.post('/api/azul/ajuda',json={'message':'Como usar o sistema?'}).status_code==200
    usage=client.get('/api/azul/consumo').json
    assert usage['totals']['unknown']==1 and usage['totals']['reserved_brl']>0
    assert usage['recent'][0]['cost_brl'] is None


def test_playback_telemetry_is_zero_cost_session_bound_and_idempotent(env):
    app,client,_=env
    data={'clip':'/static/audio/azul-inicio-chamada.wav','event_id':'b'*32}
    headers={'X-Portal-Chat-Token':'public-test','X-Azul-Conversation':'c'*32}
    for _ in range(2):
        assert client.post('/api/azul/audio-evento',json=data,headers=headers).status_code==204
    assert app.test_client().post('/api/azul/audio-evento',json=data,headers=headers).status_code==403
    assert client.post('/api/azul/audio-evento',json={**data,'clip':'https://external.test/a.wav'},headers=headers).status_code==400
    usage=client.get('/api/azul/consumo').json
    assert usage['totals']['events']==1 and usage['totals']['cost_brl']==0


def test_transcription_model_changes_and_audio_duration_are_metered(env):
    _,client,_=env
    assert save(client,{'transcribe_model':'gpt-4o-mini-transcribe'}).status_code==200
    with patch.object(speech_input,'OpenAI') as sdk:
        call=sdk.return_value.__enter__.return_value.audio.transcriptions.create
        call.return_value=SimpleNamespace(text='Como usar o sistema?')
        result=client.post('/portal-cidadao/transcrever',data=wav(),content_type='audio/wav',
                           headers={'X-Portal-Chat-Token':'public-test'})
    assert result.status_code==200
    assert call.call_args.kwargs['model']=='gpt-4o-mini-transcribe'
    assert call.call_args.kwargs['language']=='pt' and 'extra_body' not in call.call_args.kwargs
    usage=client.get('/api/azul/consumo').json
    assert usage['recent'][0]['operation']=='transcription'
    assert usage['recent'][0]['audio_seconds']==.5 and usage['recent'][0]['cost_brl']>0


def test_control_page_renders_the_management_sections_and_has_no_provider_secret(env):
    _,client,_=env
    result=client.get('/azul/configuracoes')
    assert result.status_code==200
    text=result.get_data(as_text=True)
    assert all(label in text for label in ('Consumo','Comportamento','Modelos','Limites','Tarifas e câmbio'))
    assert 'not-a-real-key' not in text


@pytest.mark.parametrize('transcript,expected_status',[('Olá! Use os filtros.',200),('Apague os registros.',503)])
def test_realtime_usage_is_recorded_even_when_the_narration_is_rejected(env,transcript,expected_status):
    app,client,_=env
    base=client.post('/api/azul/ajuda',json={'message':'Qual seu nome?'}).json['speech']
    with app.app_context():
        source=voice.serializer().loads(base['token'])
        token=voice.serializer().dumps({**source,'text':'Olá! Use os filtros.'})
    usage={'input_tokens':100,'output_tokens':220,'total_tokens':320,
           'input_token_details':{'text_tokens':100,'audio_tokens':0,'cached_tokens_details':{'text_tokens':20}},
           'output_token_details':{'text_tokens':20,'audio_tokens':200}}
    events=[{'type':'response.output_audio.delta','delta':base64.b64encode(b'\0\0'*2400).decode()},
            {'type':'response.output_audio_transcript.done','transcript':transcript},
            {'type':'response.done','response':{'id':'resp_audio','status':'completed','usage':usage}}]
    with patch('websockets.sync.client.connect') as connect:
        connect.return_value.__enter__.return_value.recv.side_effect=[json.dumps(event) for event in events]
        result=client.post('/api/azul/voz',json={'token':token})
    assert result.status_code==expected_status
    report=client.get('/api/azul/consumo').json
    event=next(item for item in report['recent'] if item['operation']=='voice')
    assert event['total_tokens']==320 and event['cost_brl']>0 and event['measured']
    assert event['status']==('complete' if expected_status==200 else 'failed')


def test_shared_count_limit_is_enforced_independently_of_legacy_host_counters(env):
    app,client,_=env
    assert save(client,{'internal_daily_text':1}).status_code==200
    with app.test_request_context('/api/azul/ajuda'):
        session['_user_id']='9'
        first=metering.start('text','gpt-6-luna',{'max_output_tokens':256})
        metering.finish(first,response())
    with app.test_request_context('/api/azul/ajuda'):
        session['_user_id']='9'
        with pytest.raises(control_store.BudgetExceeded):
            metering.start('text','gpt-6-luna',{'max_output_tokens':256})
