"""Provider usage is measured; currency values are estimates at saved rates/FX."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
import hashlib
import hmac
import json
import re
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from flask import current_app, g, has_request_context, request, session
from flask_login import current_user

from app.modules.chatbot import control_store, settings

NANO = Decimal(1_000_000_000)
MILLION = Decimal(1_000_000)
TZ = ZoneInfo('America/Sao_Paulo')
COUNTERS = ('input_text','cached_text','output_text','input_audio','cached_audio','output_audio','total_tokens','web_calls')


def nano(value):
    return int((Decimal(str(value))*NANO).to_integral_value(rounding=ROUND_CEILING))


def field(value, name, default=None):
    return value.get(name,default) if isinstance(value,dict) else getattr(value,name,default)


def number(value):
    return int(value) if type(value) in (int,float) and 0 <= value <= 10**12 else 0


def identity():
    endpoint = request.endpoint or ''
    public = (endpoint.startswith(('main.portal_','main.mobile_','main.whatsapp_','main.telegram_'))
              or (endpoint=='main.azul_audio_event' and bool(request.headers.get('X-Portal-Chat-Token')))
              or not hasattr(current_app,'login_manager') or not current_user.is_authenticated)
    actor = 'public' if public else 'user:'+str(current_user.get_id())
    if not session.get('azul_meter_session'):
        session['azul_meter_session'] = uuid4().hex
    label = request.headers.get('X-Azul-Conversation','')
    if not re.fullmatch(r'[a-f0-9]{32}',label):
        label = session['azul_meter_session']
    binding = session.get('portal_chat_token','') if public else session.get('azul_chat_id','')
    secret = current_app.secret_key
    if not isinstance(secret,bytes):
        secret = str(secret).encode()
    conversation = hmac.new(secret,json.dumps([actor,binding,label]).encode(),hashlib.sha256).hexdigest()
    return dict(actor=actor,channel='public' if public else 'internal',conversation=conversation)


def estimate_reservation(kind, rate, payload, audio_seconds=0):
    if kind == 'transcription':
        return Decimal(str(audio_seconds))/60*Decimal(rate.get('minute','0'))
    # UTF-8 byte count + framing is a conservative input-token ceiling.
    inputs = len(json.dumps(payload,ensure_ascii=False,default=lambda _:None).encode())+512
    outputs = payload.get('max_output_tokens',3000)
    output_rate = max(Decimal(rate.get('output','0')),Decimal(rate.get('audio_output','0')))
    total = Decimal(inputs)*Decimal(rate.get('input','0'))/MILLION+Decimal(outputs)*output_rate/MILLION
    if kind == 'text':
        if any(field(tool,'type')=='web_search' for tool in payload.get('tools',[])):
            total += Decimal(str(settings.get('web_search_usd')))*payload.get('max_tool_calls',0)
    return total


def start(kind, model, payload=None, audio_seconds=0):
    if not has_request_context():
        return None
    cfg = settings.current()
    if not cfg['enabled']:
        raise control_store.BudgetExceeded('A geração da AZUL foi pausada pelo desenvolvedor. Use os guias locais.')
    rate = cfg['rates'].get(model)
    if rate is None:
        raise control_store.BudgetExceeded('Configure um modelo com tarifa conhecida antes de usar a IA.')
    reserved = nano(estimate_reservation(kind,rate,payload or {},audio_seconds)*Decimal(cfg['usd_brl']))
    now = datetime.now(TZ)
    day = int(now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    month = int(now.replace(day=1,hour=0,minute=0,second=0,microsecond=0).timestamp())
    store = control_store.current()
    event_id = uuid4().hex
    who = identity()
    with store.connection(write=True) as conn:
        # Recheck mutable kill switches and budgets under the cross-worker lock.
        row = conn.execute(sa.select(control_store.configuration.c.data).where(control_store.configuration.c.id==1)).scalar_one()
        latest = {**settings.defaults(),**json.loads(row)}
        if not latest['enabled'] or (kind=='voice' and not latest['sound_enabled']) or (kind=='transcription' and not latest['microphone_enabled']):
            raise control_store.BudgetExceeded('Esta operação foi pausada nas configurações da AZUL.')
        if (kind=='transcription' and request.headers.get('X-Azul-Voice-Mode','conversation')!='dictation'
                and (not latest['sound_enabled'] or not latest['conversation_enabled'])):
            raise control_store.BudgetExceeded('A conversa por voz foi desativada nas configurações da AZUL.')
        limit_key = who['channel']+'_daily_'+{'text':'text','voice':'voice','transcription':'transcribe'}[kind]
        count = conn.execute(sa.select(sa.func.count()).select_from(control_store.events).where(
            control_store.events.c.created_at>=day,control_store.events.c.channel==who['channel'],
            control_store.events.c.operation==kind,control_store.events.c.source=='ai')).scalar_one()
        if latest[limit_key]<=0 or count>=latest[limit_key]:
            raise control_store.BudgetExceeded('O limite diário desta operação da AZUL foi atingido.')
        charge = sa.func.coalesce(control_store.events.c.cost_brl,control_store.events.c.reserved_brl)
        for threshold,cap,label in ((day,latest['daily_budget_brl'],'diário'),(month,latest['monthly_budget_brl'],'mensal')):
            limit = nano(cap)
            if limit:
                spent = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(charge),0)).where(
                    control_store.events.c.created_at>=threshold)).scalar_one()
                if spent+reserved > limit:
                    raise control_store.BudgetExceeded('O saldo do limite '+label+' não permite iniciar esta operação da AZUL. Use os guias locais ou procure o dev.')
        conn.execute(control_store.events.insert().values(id=event_id,created_at=int(time.time()),
            **who,operation=kind,source='ai',status='pending',model=model,
            pricing=json.dumps({**rate,'web_call':cfg['web_search_usd']}),fx=cfg['usd_brl'],
            reserved_brl=reserved,audio_seconds=audio_seconds))
    g.azul_paid_calls = getattr(g,'azul_paid_calls',0)+1
    return event_id


def finish(event_id, response=None, *, usage=None, failed=False, audio_seconds=0):
    if not event_id:
        return
    if usage is None:
        usage = field(response,'usage')
    values = {key:0 for key in COUNTERS}
    has_usage = ((type(field(usage,'input_tokens')) is int and type(field(usage,'output_tokens')) is int)
                 or type(field(usage,'seconds')) in (int,float))
    store = control_store.current()
    with store.connection(write=True) as conn:
        event = conn.execute(sa.select(control_store.events).where(control_store.events.c.id==event_id)).mappings().one()
        if event['status'] != 'pending':
            return
        kind = event['operation']
        known = has_usage
        if kind == 'voice':
            inputs = field(usage,'input_token_details',{})
            outputs = field(usage,'output_token_details',{})
            cached = field(inputs,'cached_tokens_details',{})
            values.update(input_text=number(field(inputs,'text_tokens',field(usage,'input_tokens'))),
                          cached_text=number(field(cached,'text_tokens')),
                          input_audio=number(field(inputs,'audio_tokens')),
                          cached_audio=number(field(cached,'audio_tokens')),
                          output_text=number(field(outputs,'text_tokens')),
                          output_audio=number(field(outputs,'audio_tokens')))
            values['output_text'] = max(values['output_text'],number(field(usage,'output_tokens'))-values['output_audio'])
            known = has_usage and type(field(outputs,'audio_tokens')) is int
        else:
            values.update(input_text=number(field(usage,'input_tokens')),
                cached_text=number(field(field(usage,'input_tokens_details',{}),'cached_tokens')),
                output_text=number(field(usage,'output_tokens')))
        values['total_tokens'] = number(field(usage,'total_tokens'))
        if not values['total_tokens']:
            values['total_tokens'] = values['input_text']+values['input_audio']+values['output_text']+values['output_audio']
        values['web_calls'] = sum(1 for item in (field(response,'output',[]) or [])
                                  if field(item,'type')=='web_search_call')
        rate = json.loads(event['pricing'])
        usd = None
        seconds = audio_seconds or event['audio_seconds']
        if kind == 'transcription' and not failed:
            # Completed WAV duration is known even when the provider omits usage.
            reported = field(usage,'seconds')
            seconds = reported if type(reported) in (int,float) and reported>0 else seconds
            usd = Decimal(str(seconds))/60*Decimal(rate.get('minute','0'))
        elif known:
            usd = (Decimal(max(0,values['input_text']-values['cached_text']))*Decimal(rate.get('input','0'))
                +Decimal(values['cached_text'])*Decimal(rate.get('cached_input','0'))
                +Decimal(values['output_text'])*Decimal(rate.get('output','0'))
                +Decimal(max(0,values['input_audio']-values['cached_audio']))*Decimal(rate.get('audio_input','0'))
                +Decimal(values['cached_audio'])*Decimal(rate.get('cached_audio_input','0'))
                +Decimal(values['output_audio'])*Decimal(rate.get('audio_output','0')))/MILLION
            usd += Decimal(values['web_calls'])*Decimal(rate.get('web_call','0'))
        provider_id = field(response,'id')
        conn.execute(control_store.events.update().where(control_store.events.c.id==event_id).values(
            **values,status='failed' if failed else 'complete' if usd is not None else 'unknown',
            measured=has_usage,audio_seconds=seconds,
            provider_id=provider_id[:180] if isinstance(provider_id,str) else None,
            cost_usd=nano(usd) if usd is not None else None,
            cost_brl=nano(usd*Decimal(event['fx'])) if usd is not None else None))


def complete(event_id, response=None, **kwargs):
    try:
        finish(event_id,response,**kwargs)
    except control_store.StoreError:
        current_app.logger.warning('AZUL: consumo pendente de medição')


def respond(client, **payload):
    event = start('text',payload['model'],payload)
    try:
        response = client.responses.create(**payload)
    except Exception:
        complete(event,failed=True)
        raise
    complete(event,response,failed=field(response,'status','completed')!='completed')
    return response


def free(operation, source, event_id=None):
    if not has_request_context():
        return
    try:
        store = control_store.current()
        who = identity()
        key = hashlib.sha256((who['conversation']+event_id).encode()).hexdigest() if event_id else uuid4().hex
        with store.connection(write=True) as conn:
            if conn.execute(sa.select(control_store.events.c.id).where(control_store.events.c.id==key)).first():
                return
            # Bound client playback telemetry; it can never create paid events.
            if event_id:
                count = conn.execute(sa.select(sa.func.count()).select_from(control_store.events).where(
                    control_store.events.c.conversation==who['conversation'],
                    control_store.events.c.created_at>=int(time.time())-3600)).scalar_one()
                if count>=200:
                    return
            conn.execute(control_store.events.insert().values(id=key,created_at=int(time.time()),**who,
                operation=operation,source=source,status='complete',model='',pricing='{}',fx='0',
                reserved_brl=0,cost_usd=0,cost_brl=0,measured=True))
    except control_store.StoreError:
        current_app.logger.warning('AZUL: evento gratuito não registrado')


def summary(days=30, channel='all'):
    now = datetime.now(TZ)
    start = now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=days-1)
    table = control_store.events
    filters = [table.c.created_at>=int(start.timestamp())]
    if channel in ('public','internal'):
        filters.append(table.c.channel==channel)
    totals = [sa.func.count().label('events'),sa.func.count(sa.distinct(table.c.conversation)).label('conversations'),
              sa.func.coalesce(sa.func.sum(table.c.cost_brl),0).label('cost_brl'),
              sa.func.coalesce(sa.func.sum(table.c.total_tokens),0).label('tokens'),
              sa.func.coalesce(sa.func.sum(sa.case((table.c.cost_brl.is_(None),table.c.reserved_brl),else_=0)),0).label('reserved_brl'),
              sa.func.sum(sa.case((table.c.cost_brl.is_(None),1),else_=0)).label('unknown')]
    with control_store.current().connection() as conn:
        overall = dict(conn.execute(sa.select(*totals).where(*filters)).mappings().one())
        groups = [dict(row) for row in conn.execute(sa.select(table.c.operation,table.c.source,
            sa.func.count().label('count'),sa.func.coalesce(sa.func.sum(table.c.total_tokens),0).label('tokens'),
            sa.func.coalesce(sa.func.sum(table.c.cost_brl),0).label('cost_brl')).where(*filters)
            .group_by(table.c.operation,table.c.source)).mappings()]
        sessions = [dict(row) for row in conn.execute(sa.select(table.c.conversation,table.c.actor,table.c.channel,
            sa.func.max(table.c.created_at).label('last_at'),sa.func.count().label('events'),
            sa.func.coalesce(sa.func.sum(table.c.total_tokens),0).label('tokens'),
            sa.func.coalesce(sa.func.sum(table.c.cost_brl),0).label('cost_brl'),
            sa.func.sum(sa.case((table.c.cost_brl.is_(None),1),else_=0)).label('unknown'))
            .where(*filters).group_by(table.c.conversation,table.c.actor,table.c.channel)
            .order_by(sa.desc('last_at')).limit(30)).mappings()]
        recent = [dict(row) for row in conn.execute(sa.select(
            table.c.created_at,table.c.channel,table.c.operation,table.c.source,table.c.status,
            table.c.model,table.c.total_tokens,table.c.cost_brl,table.c.measured,table.c.audio_seconds)
            .where(*filters).order_by(table.c.created_at.desc()).limit(50)).mappings()]
        first = conn.execute(sa.select(sa.func.min(table.c.created_at))).scalar_one()
    overall['unknown'] = overall['unknown'] or 0
    return dict(totals=overall,groups=groups,conversations=sessions,recent=recent,first_event_at=first,
                days=days,channel=channel)
