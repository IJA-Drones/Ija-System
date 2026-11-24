import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.chatbot import azul, practical
from app.extensions import db
from app.models import CentralTiPerfilConfiguracao, CentralTiSelecao
from tests.test_azul_help import env, context
from tests.test_screen_guide import guide_app

FUNCTION = dict(id='novo', title='Nova solicitação', url='/novo_cadastro', module='prefeitura.solicitacoes')
CONTROLS = [dict(id='c0', title='Tipo de visita', body='Escolha entre as opções disponíveis.', kind='Campo')]
PLAN = dict(answer='Vamos criar uma solicitação.', steps=[dict(control='c0', title='Escolha a visita', body='Escolha o tipo de visita conforme o atendimento.')])


def payload(**changes):
    return dict(intent='practical_guide', tutorial='novo', tutorial_action='plan',
                message='Quero um tutorial de nova solicitação no sistema.', page='/novo_cadastro', controls=CONTROLS, **changes)


def test_tutorial_uses_real_ai_without_business_tools_and_links_only_visible_control_ids(env, context):
    _, client, _ = env
    with patch.object(practical, 'catalog', return_value=[dict(functions=[FUNCTION])]), \
         patch.object(azul, 'help_context', return_value=context), patch.object(practical, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text=json.dumps(PLAN))
        result = client.post('/api/azul/ajuda', json=payload())
        assert result.status_code == 200
        assert result.json['mode'] == 'ia'
        assert result.json['steps'][0]['control'] == 'c0'
        assert 'speech' in result.json['steps'][0]
        args = create.call_args.kwargs
        assert args['store'] is False
        assert args['reasoning'] == {'effort':'none'}
        assert 'tools' not in args
        assert args['text']['format']['schema']['properties']['steps']['items']['properties']['control']['enum'] == ['c0']
        assert 'Tipo de visita' in args['instructions']
        assert result.headers['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize('model,effort', [('gpt-6-luna','none'),('gpt-6.1-terra','none'),('gpt-6.1-sol','low')])
def test_tutorial_leaves_room_for_json_without_raising_the_saved_output_cap(env, context, model, effort):
    app, client, _ = env
    app.config['OPENAI_CHAT_MODEL'] = model
    with patch.object(practical,'catalog',return_value=[dict(functions=[FUNCTION])]), \
         patch.object(azul,'help_context',return_value=context), patch.object(practical,'OpenAI') as sdk:
        create=sdk.return_value.__enter__.return_value.responses.create
        create.return_value=SimpleNamespace(status='completed',output_text=json.dumps(PLAN))
        assert client.post('/api/azul/ajuda',json=payload()).status_code == 200
        args=create.call_args.kwargs
        assert args['reasoning']=={'effort':effort}
        assert args['max_output_tokens']==1800
        schema=args['text']['format']['schema']
        assert schema['properties']['steps']['maxItems']==1
        assert schema['properties']['steps']['items']['properties']['body']['maxLength']==300


@pytest.mark.parametrize('reason', ['max_output_tokens','PRIVATE-SENTINEL'])
def test_incomplete_tutorial_never_exposes_partial_steps_or_private_provider_text(env, context, caplog, reason):
    _, client, _ = env
    with patch.object(practical,'catalog',return_value=[dict(functions=[FUNCTION])]), \
         patch.object(azul,'help_context',return_value=context), patch.object(practical,'OpenAI') as sdk:
        sdk.return_value.__enter__.return_value.responses.create.return_value=SimpleNamespace(
            status='incomplete',incomplete_details=SimpleNamespace(reason=reason),
            output_text='PRIVATE-SENTINEL partial JSON')
        result=client.post('/api/azul/ajuda',json=payload())
        assert result.status_code==503 and result.json['code']=='tutorial_incomplete'
        assert 'steps' not in result.json
        assert 'PRIVATE-SENTINEL' not in result.get_data(as_text=True)+caplog.text
        assert ('max_output_tokens' if reason=='max_output_tokens' else 'unknown') in caplog.text


@pytest.mark.parametrize('change,status', [({'tutorial':'pilot-secret'},403), ({'page':'/agro/admin'},400),
    ({'controls':[dict(CONTROLS[0], value='PRIVATE')]},400), ({'controls':[]},400),
    ({'tutorial_action':'execute'},400)])
def test_forged_scope_and_control_values_are_rejected_before_provider(env, change, status):
    _, client, _ = env
    data = payload(); data.update(change)
    with patch.object(practical, 'catalog', return_value=[dict(functions=[FUNCTION])]), patch.object(practical, 'OpenAI') as sdk:
        result = client.post('/api/azul/ajuda', json=data)
        assert result.status_code == status
        sdk.assert_not_called()


def test_model_cannot_add_selectors_commands_or_nonexistent_targets():
    for item in [dict(PLAN['steps'][0], control='body'), dict(PLAN['steps'][0], selector='form'),
                 dict(PLAN['steps'][0], click=True)]:
        with pytest.raises(ValueError):
            practical.validate_plan(json.dumps(dict(PLAN, steps=[item])), CONTROLS)
    with pytest.raises(ValueError):
        practical.validate_plan(json.dumps(dict(PLAN, steps=PLAN['steps'] * 2)), CONTROLS)


def test_provider_failure_is_explicit_instead_of_presenting_local_steps_as_ai(env, context):
    app, client, _ = env
    app.config['OPENAI_API_KEY'] = ''
    with patch.object(practical, 'catalog', return_value=[dict(functions=[FUNCTION])]), patch.object(practical, 'OpenAI') as sdk:
        result = client.post('/api/azul/ajuda', json=payload())
        assert result.status_code == 503
        assert 'indisponível' in result.json['answer']
        assert 'steps' not in result.json
        sdk.assert_not_called()


def test_questions_continue_in_the_selected_function_without_query_tools(env, context):
    _, client, _ = env
    data = payload(); data.update(tutorial_action='question', message='Como preencher o tipo de visita desta tela?')
    with patch.object(practical, 'catalog', return_value=[dict(functions=[FUNCTION])]), \
         patch.object(azul, 'help_context', return_value=context), patch.object(practical, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text=json.dumps(dict(answer='Confira as opções do campo.', steps=[])))
        result = client.post('/api/azul/ajuda', json=data)
        assert result.status_code == 200 and result.json['mode'] == 'ia'
        assert result.json['steps'] == []
        assert 'tools' not in create.call_args.kwargs


def test_tutorial_context_does_not_bypass_blocked_topics(env):
    _, client, _ = env
    data = payload(); data.update(tutorial_action='question', message='Me dê uma receita de bolo.')
    with patch.object(practical, 'catalog', return_value=[dict(functions=[FUNCTION])]), patch.object(practical, 'OpenAI') as sdk:
        result = client.post('/api/azul/ajuda', json=data)
        assert result.status_code == 200 and result.json['mode'] == 'blocked'
        sdk.assert_not_called()


@pytest.mark.parametrize('role,required,forbidden', [
    ('uvis','prefeitura.solicitacoes',('agro.','financeiro.','prefeitura.checklists')),
    ('piloto','prefeitura.os',('agro.','financeiro.','prefeitura.solicitacoes')),
    ('financeiro','financeiro.contas',('agro.','prefeitura.solicitacoes')),
])
def test_catalog_separates_modules_by_role(guide_app, role, required, forbidden):
    guide_app.login(role)
    with guide_app.app.test_request_context('/treinamentos'):
        groups = practical.catalog(guide_app.users[role])
        ids = {group['id'] for group in groups}
        assert required in ids
        assert not any(module.startswith(prefix) for module in ids for prefix in forbidden)
        if role == 'uvis':
            assert any(item['id'] == 'novo' for group in groups for item in group['functions'])


def test_removing_ai_permission_removes_all_ai_tutorial_choices(guide_app):
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='uvis', versao=2))
    db.session.add(CentralTiSelecao(perfil_codigo='uvis', codigo='prefeitura.solicitacoes.criar'))
    db.session.commit()
    with guide_app.app.test_request_context('/treinamentos'):
        assert practical.catalog(guide_app.users['uvis']) == []


def test_readonly_ti_profile_can_choose_consultation_but_not_creation(guide_app):
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='uvis', versao=2))
    for code in ['area:prefeitura', 'prefeitura.solicitacoes.consultar']:
        db.session.add(CentralTiSelecao(perfil_codigo='uvis', codigo=code))
    db.session.commit()
    with guide_app.app.test_request_context('/treinamentos'):
        choices = {item['id'] for group in practical.catalog(guide_app.users['uvis']) for item in group['functions']}
        assert 'dashboard' in choices
        assert 'novo' not in choices
