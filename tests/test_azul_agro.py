import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from werkzeug.exceptions import Forbidden
from app.extensions import db
from app.models import (Usuario, Prefeitura, ClienteAgro, EquipeAgro, PilotoAgro,
                        OrcamentoAgro, ContratoAgro, OrdemServicoAgro, RdMapeamentoAgro,
                        CentralTiPerfilConfiguracao, CentralTiSelecao)
from app.modules.chatbot import agro, agro_help, azul
from app.modules.consultas.service import QueryError
from tests.test_azul_exports import app, client


def seed(app):
    for _, endpoint, _ in agro.SOURCES.values():
        app.add_url_rule('/agro/' + endpoint, endpoint='main.' + endpoint, view_func=lambda: '')
    for suffix in ('os', 'mapeamentos'):
        app.add_url_rule('/agro/piloto/' + suffix, endpoint='main.agro_piloto_' + suffix + '_listar', view_func=lambda: '')
    with app.app_context():
        db.session.add(Prefeitura(id=2, nome='Outra', slug='outra'))
        user = db.session.get(Usuario, 3)
        user.tipo_usuario = 'operario'
        user.trabalha_agro = True
        for i in (1, 2):
            db.session.add(ClienteAgro(id=i, prefeitura_id=i, nome='Cliente ' + str(i)))
            db.session.add(EquipeAgro(id=i, prefeitura_id=i, nome='Equipe ' + str(i)))
            db.session.add(PilotoAgro(id=i, prefeitura_id=i, equipe_agro_id=i, nome='Piloto ' + str(i)))
        db.session.flush()
        db.session.get(Usuario, 4).piloto_agro_id = 1
        for i in range(1, 7):
            team = 1 if i <= 3 else 2
            budget = OrcamentoAgro(id=i, prefeitura_id=team, cliente_nome='Cliente', nome_fazenda='Fazenda', mapeamento=True, cep='00000000', logradouro='Rua', numero='1', bairro='Centro', cidade='Cidade', uf='SP')
            db.session.add(budget)
            db.session.flush()
            if i in (3, 6):
                db.session.add(RdMapeamentoAgro(id=i, prefeitura_id=team, orcamento_agro_id=i, equipe_agro_id=team, cliente_nome="Cliente", propriedade_nome="Fazenda", municipio="Cidade"))
                continue
            required = {c.name: 'Teste' for c in ContratoAgro.__table__.columns
                        if not c.nullable and isinstance(c.type, db.String) and not c.default}
            contract = ContratoAgro(id=i, prefeitura_id=team, orcamento_agro_id=i, equipe_agro_id=team,
                                    **{**required, 'status': ContratoAgro.STATUS_APROVADO})
            db.session.add(contract)
            db.session.flush()
            if i in (1, 4):
                db.session.add(OrdemServicoAgro(id=i, prefeitura_id=team, contrato_agro_id=i, orcamento_agro_id=i,
                    equipe_agro_id=team, identificador_os='OS-' + str(i), cliente_nome='Cliente', propriedade_nome='Fazenda'))
        db.session.commit()


def plan(source='os', **kwargs):
    return dict({'fonte': source, 'q': '', 'status': ''}, **kwargs)


def test_admin_queries_reuse_tenant_scope(app):
    seed(app)
    with app.test_request_context():
        user = db.session.get(Usuario, 3)
        for source, expected in [('clientes', 1), ('orcamentos', 3), ('contratos', 2), ('os', 1)]:
            answer, links = agro.execute(user, plan(source))
            assert f': {expected} registro(s)' in answer
            assert links
        user.prefeitura_id = None
        user.tipo_usuario = 'prefeitura_admin'
        # Even a caller with endpoint access cannot broaden a missing tenant.
        with patch.object(agro, 'allowed_sources', return_value=['clientes']):
            assert agro.query_for(user, 'clientes').count() == 0


def test_pilot_only_sees_team_and_approved_contracts_without_os(app):
    seed(app)
    with app.test_request_context():
        user = db.session.get(Usuario, 4)
        assert agro.allowed_sources(user) == ['contratos', 'os', 'mapeamentos']
        for source in agro.allowed_sources(user):
            answer, links = agro.execute(user, plan(source))
            assert ': 1 registro(s)' in answer
            assert '#4' not in answer and '#5' not in answer and '#6' not in answer
            assert '/agro/piloto/' in links[0]['url']
        assert 'AGUARDANDO_OS' in agro.execute(user, plan('contratos'))[1][0]['url']
        with pytest.raises(Forbidden):
            agro.execute(user, plan('clientes'))
        user.piloto_agro.equipe_agro_id = None
        assert agro.tools(user) == []
        with pytest.raises(Forbidden):
            agro.execute(user, plan())


def test_pilot_inactive_is_denied(app):
    seed(app)
    with app.test_request_context():
        user = db.session.get(Usuario, 4)
        user.piloto_agro.ativo = False
        assert agro.allowed_sources(user) == []


def test_summary_without_ai_and_no_municipal_fallback(app):
    seed(app)
    with patch.object(azul, 'OpenAI') as ai, patch.object(azul.operations, 'summarize') as municipal:
        response = client(app, 4).post('/api/azul/ajuda', json={'message': 'Resumo de pendências do Agro', 'intent': 'agro_attention'})
    assert response.status_code == 200
    assert response.json['mode'] == 'operacional'
    answer = response.json['answer']
    assert 'Mapeamentos pendentes: 1.' in answer
    assert 'Contratos aprovados sem OS: 1.' in answer
    assert 'OS planejadas: 1.' in answer
    assert 'OS em execução: 0.' in answer
    assert 'todas as datas' in answer
    assert response.headers['Cache-Control'] == 'private, no-store'
    ai.assert_not_called()
    municipal.assert_not_called()


@pytest.mark.parametrize('bad', [{'status': 'TODAS'}, {'inicio': '2026-01-01'}, {'q': []}, {'q': 'a' * 121}])
def test_invalid_filters_do_not_run_queries(app, bad):
    seed(app)
    with app.test_request_context(), patch.object(agro, 'query_for') as query:
        with pytest.raises(QueryError):
            agro.execute(db.session.get(Usuario, 4), plan(**bad))
        query.assert_not_called()


def test_tool_dispatch_returns_scoped_data_without_second_model_call(app):
    seed(app)
    app.config['OPENAI_API_KEY'] = 'test'
    with patch.object(azul, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='', output=[
            SimpleNamespace(type='function_call', name='buscar_agro', arguments=json.dumps(plan(status='PLANEJADA')))])
        response = client(app, 4).post('/api/azul/ajuda', json={'message': 'Busque OS planejadas no Agro'})
    assert response.status_code == 200
    assert response.json['mode'] == 'busca'
    assert ': 1 registro(s)' in response.json['answer']
    assert create.call_count == 1
    assert response.json['export_preview'] is None


def test_screen_guidance_without_ai(app):
    seed(app)
    with patch.object(azul, 'OpenAI') as sdk, patch.object(agro, 'query_for') as query:
        response = client(app, 4).post('/api/azul/ajuda', json={'message': 'Como usar esta tela?', 'page': '/agro/piloto/os'})
    assert response.status_code == 200
    assert response.json['mode'] == 'guided'
    assert 'equipe vinculada' in response.json['answer']
    sdk.assert_not_called()
    query.assert_not_called()
    context = {'atalhos': [{'modulo': 'agro.os', 'url': '/agro/piloto/os'}]}
    assert agro_help.current_topic(context, '/agro/contratos') is None
    assert len(agro_help.available(context)) == 1


def test_central_ti_partial_access_omits_other_modules(app):
    seed(app)
    app.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='piloto_agro', versao=2, atualizado_por_id=1))
        db.session.flush()
        for code in ('area:agro', 'agro.os.consultar'):
            db.session.add(CentralTiSelecao(perfil_codigo='piloto_agro', codigo=code))
        db.session.commit()
    with app.test_request_context():
        user = db.session.get(Usuario, 4)
        assert agro.allowed_sources(user) == ['os']
        answer, links = agro.summarize(user)
        assert 'OS planejadas: 1.' in answer
        assert 'Contratos aprovados' not in answer
        assert 'Mapeamentos pendentes' not in answer
        with pytest.raises(Forbidden):
            agro.execute(user, plan('contratos'))
        with pytest.raises(Forbidden):
            agro.execute(user, plan('mapeamentos'))


def test_admin_mapping_matches_screen_and_includes_missing_rd(app):
    seed(app)
    with app.test_request_context():
        user = db.session.get(Usuario, 1)
        user.trabalha_agro = True
        answer, _ = agro.execute(user, plan('mapeamentos'))
        assert ': 2 registro(s)' in answer
        db.session.add(OrcamentoAgro(id=7, prefeitura_id=1, cliente_nome='Novo', nome_fazenda='Nova', mapeamento=True,
            cep='00000000', logradouro='Rua', numero='1', bairro='Centro', cidade='Cidade', uf='SP'))
        db.session.flush()
        answer, _ = agro.summarize(user)
        assert 'Mapeamentos pendentes (inclui RD não criada): 3.' in answer
        db.session.get(RdMapeamentoAgro, 3).status = RdMapeamentoAgro.STATUS_PREENCHIDO
        db.session.flush()
        assert 'Mapeamentos pendentes (inclui RD não criada): 2.' in agro.summarize(user)[0]


def test_denied_source_never_queries(app):
    seed(app)
    with app.test_request_context(), patch.object(agro, 'query_for') as query:
        user = db.session.get(Usuario, 3)
        user.trabalha_agro = False
        assert agro.tools(user) == []
        with pytest.raises(Forbidden):
            agro.execute(user, plan())
        query.assert_not_called()


def test_form_help_only_for_recognized_authorized_routes(app):
    seed(app)
    app.add_url_rule('/agro/os/<int:os_id>/editar', endpoint='main.agro_os_editar', view_func=lambda os_id: '')
    with app.test_request_context():
        user = db.session.get(Usuario, 1)
        user.trabalha_agro = True
        context = azul.help_context(user, '/agro/os/123/editar')
        assert agro_help.current_topic(context, '/agro/os/123/editar')['module'] == 'agro.os'
        assert agro_help.form_module(user, 'https://example.com/agro/os/123/editar') is None
        assert agro_help.form_module(user, '/agro/unknown') is None
        assert agro_help.form_module(user, 'http://[') is None
        assert agro_help.current_topic(context, 'http://[') is None
        pilot = db.session.get(Usuario, 4)
        pilot_context = azul.help_context(pilot, '/agro/os/1/editar')
        assert agro_help.current_topic(pilot_context, '/agro/os/1/editar')['module'] == 'agro.os'
