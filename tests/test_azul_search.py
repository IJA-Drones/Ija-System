import json
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
from types import SimpleNamespace
import pytest
from werkzeug.exceptions import Forbidden
from app.extensions import db
from app.models import Usuario
from app.modules.chatbot import search, azul
from app.modules.consultas.service import QueryError
from app.modules.admin_dashboard.service import build_admin_dashboard_query, build_admin_export_query
from tests.test_azul_operations import seed
from tests.test_azul_exports import app, client


def plan(**changes):
    return dict(dict.fromkeys(search.FIELDS, ''), **changes)


def test_search_matches_scoped_list_and_export(app):
    seed(app)
    with app.test_request_context():
        user=db.session.get(Usuario,3)
        answer, links=search.execute(user,plan(status='PENDENTE',bairro='centro'))
        assert 'Encontrei 2 solicitações' in answer
        args={k:v[0] for k,v in parse_qs(urlsplit(links[0]['url']).query).items()}
        assert args['bairro']=='centro'
        assert args['per_page']=='25'
        for builder in (build_admin_dashboard_query,build_admin_export_query):
            assert builder(user,args['status'],'','','','',filtro_bairro=args['bairro']).count()==2


def test_denied_search_never_queries(app):
    seed(app)
    with app.test_request_context(), patch.object(search,'build_admin_dashboard_query') as query:
        with pytest.raises(Forbidden):
            search.execute(db.session.get(Usuario,4),plan())
        query.assert_not_called()


@pytest.mark.parametrize('changes', [{'inicio':'invalid'}, {'inicio':'2026-11-01','fim':'2026-10-01'}, {'status':'CANCELADO'}, {'bairro':['Centro']}, {'bairro':'a'*121}, {'sql':'select *'}])
def test_invalid_filters_are_rejected(app, changes):
    seed(app)
    with app.test_request_context(), pytest.raises(QueryError):
        search.execute(db.session.get(Usuario,3),plan(**changes))


def test_tool_returns_results_without_sending_records_to_model(app):
    seed(app)
    app.config['OPENAI_API_KEY']='test'
    with patch.object(azul,'OpenAI') as sdk:
        create=sdk.return_value.__enter__.return_value.responses.create
        create.return_value=SimpleNamespace(status='completed',output_text='',output=[SimpleNamespace(type='function_call',name='buscar_solicitacoes',arguments=json.dumps(plan(bairro='Centro',status='PENDENTE')))])
        response=client(app,3).post('/api/azul/ajuda',json={'message':'Encontre solicitações pendentes do Centro'})
        assert create.call_count==1
        assert response.json['mode']=='busca'
        assert 'Encontrei 2 solicitações' in response.json['answer']
        assert response.json['export_preview'] is None
