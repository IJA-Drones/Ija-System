from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from werkzeug.exceptions import Forbidden
from app.extensions import db
from app.models import Usuario, OrdemServicoAgro
from app.modules.chatbot import agro, agro_details, agro_help, azul
from app.modules.consultas.service import QueryError
from tests.test_azul_agro import seed, plan
from tests.test_azul_exports import app, client


def test_details_do_not_disclose_other_team_or_missing_ids(app):
    seed(app)
    with app.test_request_context():
        pilot = db.session.get(Usuario, 4)
        for source, own, other in [('os', 1, 4), ('mapeamentos', 3, 6)]:
            own_answer, links = agro_details.detail(pilot, {'fonte': source, 'id': own, 'conferir': False})
            assert 'Equipe 1' in own_answer and links
            for record_id in (other, 99999):
                answer, links = agro_details.detail(pilot, {'fonte': source, 'id': record_id, 'conferir': True})
                assert answer == 'Registro não encontrado no seu acesso.'
                assert not links
        pilot.piloto_agro.ativo = False
        with pytest.raises(Forbidden):
            agro_details.detail(pilot, {'fonte': 'os', 'id': 1, 'conferir': False})


def test_admin_detail_reuses_municipal_scope(app):
    seed(app)
    with app.test_request_context():
        user = db.session.get(Usuario, 3)
        assert 'OS #1' in agro_details.detail(user, {'fonte': 'os', 'id': 1, 'conferir': False})[0]
        assert 'não encontrado' in agro_details.detail(user, {'fonte': 'os', 'id': 4, 'conferir': False})[0]


def test_period_is_inclusive_and_excludes_undated(app):
    seed(app)
    with app.test_request_context():
        pilot = db.session.get(Usuario, 4)
        query = dict(plan(), inicio='2026-11-19', fim='2026-11-19')
        assert ': 0 registro(s)' in agro_details.search_period(pilot, query)[0]
        db.session.get(OrdemServicoAgro, 1).data_aplicacao = date(2026, 11, 19)
        db.session.get(OrdemServicoAgro, 4).data_aplicacao = date(2026, 11, 19)
        db.session.flush()
        answer, _ = agro_details.search_period(pilot, query)
        assert ': 1 registro(s)' in answer and '#4' not in answer
        assert 'data de aplicação' in answer and 'não aplica o período' in answer
        query['inicio'] = '2026-11-20'
        query['fim'] = ''
        assert ': 0 registro(s)' in agro_details.search_period(pilot, query)[0]


@pytest.mark.parametrize('changes', [{'inicio': '2026-02-30'}, {'inicio': '2026-12-01', 'fim': '2026-11-01'}, {'fim': None}, {'equipe': '2'}, {'inicio': '20261119'}])
def test_period_invalid_filters_are_rejected_before_query(app, changes):
    seed(app)
    with app.test_request_context(), patch.object(agro, 'query_for') as query:
        with pytest.raises(QueryError):
            agro_details.search_period(db.session.get(Usuario, 4), dict(plan(), inicio='', fim='', **{}) | changes)
        query.assert_not_called()


@pytest.mark.parametrize('source,record_id,expected', [('os', 1, 'Informe a data da aplicacao'), ('mapeamentos', 3, 'Informe a data da RD')])
def test_check_uses_screen_validation_without_writes_or_second_ai(app, source, record_id, expected):
    seed(app)
    app.config['OPENAI_API_KEY'] = 'test'
    with patch.object(azul, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='', output=[SimpleNamespace(
            type='function_call', name='detalhar_agro', arguments=json.dumps({'fonte': source, 'id': record_id, 'conferir': True}))])
        with patch.object(db.session, 'commit') as commit:
            response = client(app, 4).post('/api/azul/ajuda', json={'message': 'Confira o registro do Agro'})
        commit.assert_not_called()
    assert response.status_code == 200
    assert expected in response.json['answer']
    assert 'ainda não salvas' in response.json['answer']
    if source == 'os':
        assert 'Anexos opcionais' in response.json['answer']
    assert create.call_count == 1


def test_priorities_explain_reason_without_claiming_overdue(app):
    seed(app)
    with app.test_request_context():
        answer, _ = agro.summarize(db.session.get(Usuario, 4))
        assert 'Motivo da atenção' in answer
        assert '#4' not in answer and '#6' not in answer
        assert 'atrasada' not in answer


def test_form_steps_are_local_and_permission_aware(app):
    seed(app)
    with patch.object(azul, 'OpenAI') as sdk:
        response = client(app, 4).post('/api/azul/ajuda', json={'message': 'Como preencher a RD?', 'page': '/agro/piloto/mapeamentos'})
    assert response.status_code == 200
    assert 'poste com tirante' in response.json['answer']
    assert 'ID da RD' in response.json['answer']
    sdk.assert_not_called()
    assert agro_help.match('Como preencher a RD?', {'atalhos': []}) is None


def test_new_tools_recheck_partial_permissions(app):
    from app.models import CentralTiPerfilConfiguracao, CentralTiSelecao
    seed(app)
    app.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with app.app_context():
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='piloto_agro', versao=2, atualizado_por_id=1))
        db.session.flush()
        for code in ('area:agro', 'agro.os.consultar'):
            db.session.add(CentralTiSelecao(perfil_codigo='piloto_agro', codigo=code))
        db.session.commit()
    with app.test_request_context():
        pilot = db.session.get(Usuario, 4)
        assert agro_details.tools(pilot)[1]['parameters']['properties']['fonte']['enum'] == ['os']
        with pytest.raises(Forbidden):
            agro_details.detail(pilot, {'fonte': 'mapeamentos', 'id': 3, 'conferir': True})
        with pytest.raises(Forbidden):
            agro_details.search_period(pilot, dict(plan('contratos'), inicio='', fim=''))


@pytest.mark.parametrize('question', ['Como preencher a RD?', 'resuma a os 1', 'minhas os em andamento'])
def test_natural_agro_requests_pass_topic_gate(question):
    from app.modules.chatbot import topics
    assert topics.evaluate(question).kind == 'allowed'
