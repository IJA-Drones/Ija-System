from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from unittest.mock import patch

from app.extensions import db
from app.models import Prefeitura, Usuario, Solicitacao
from app.modules.chatbot import operations, azul
from tests.test_azul_exports import app, client


def seed(app):
    app.add_url_rule('/admin', endpoint='main.admin_dashboard', view_func=lambda: '')
    app.add_url_rule('/dev', endpoint='main.dev_dashboard', view_func=lambda: '')
    app.add_url_rule('/feedback', endpoint='main.feedback_listar', view_func=lambda: '')
    with app.app_context():
        for user in Usuario.query.all():
            user.trabalha_oceano_azul = True
        today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        db.session.get(Usuario, 3).tipo_usuario = 'prefeitura_admin'
        row = db.session.get(Solicitacao, 1)
        row.data_agendamento = today
        db.session.add(Prefeitura(id=2, nome='Outra', slug='outra'))
        db.session.add(Usuario(id=5, login='other', nome_uvis='Outro', senha_hash='unused', tipo_usuario='uvis', prefeitura_id=2))
        db.session.flush()
        for sid, city, owner, status, day in [(2,2,5,'PENDENTE',today), (3,1,1,'PENDENTE',today-timedelta(days=1)), (4,1,1,'APROVADO',today), (5,1,1,'CANCELADO',today)]:
            db.session.add(Solicitacao(id=sid, prefeitura_id=city, usuario_id=owner, status=status,
                data_agendamento=day, hora_agendamento=row.hora_agendamento, foco='Piscina', tipo_visita='Aedes', cep='01000000', logradouro='Rua', bairro='Centro', cidade='Cidade', uf='SP'))
        db.session.commit()


def test_summary_real_counts_scoped_to_municipality_without_provider(app):
    seed(app)
    with patch.object(azul, 'OpenAI') as sdk:
        response = client(app, 3).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'})
    assert response.status_code == 200
    data = response.json
    assert data['mode'] == 'operacional'
    assert 'para hoje: 1.' in data['answer']
    assert 'anterior à referência: 1.' in data['answer']
    assert 'em qualquer data: 1.' in data['answer']
    assert '#2' not in data['answer'] and '#5' not in data['answer']
    assert len(data['links']) == 6
    sdk.assert_not_called()


def test_denied_summary_never_queries_records(app):
    seed(app)
    with patch.object(operations, 'build_admin_dashboard_query') as query:
        response = client(app, 4).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?', 'role':'dev'})
    assert 'não permite' in response.json['answer']
    query.assert_not_called()


def test_tool_summary_is_not_sent_back_to_provider(app):
    seed(app)
    app.config['OPENAI_API_KEY'] = 'test'
    with patch.object(azul, 'OpenAI') as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status='completed', output_text='', output=[SimpleNamespace(type='function_call', name='consultar_atencao_hoje', arguments='{}')])
        response = client(app,3).post('/api/azul/ajuda', json={'message':'Como está a operação hoje?'})
    assert response.json['mode'] == 'operacional'
    assert create.call_count == 1
    assert response.json['export_preview'] is None


def test_missing_tenant_does_not_inherit_global_scope(app):
    seed(app)
    with app.app_context():
        db.session.get(Usuario,3).prefeitura_id = None
        db.session.commit()
    response = client(app,3).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'})
    assert response.json['links'] == []
    assert 'para hoje: 0.' in response.json['answer']


def test_global_role_summary_and_quota(app):
    seed(app)
    c = client(app,2)
    data = c.post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'}).json
    assert 'para hoje: 2.' in data['answer']
    with patch.object(azul, 'consume_help_quota', return_value=False), patch.object(operations, 'summarize') as summary:
        assert c.post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'}).status_code == 429
        summary.assert_not_called()


def test_external_employee_cannot_get_summary_or_tool_even_when_dev(app):
    seed(app)
    with app.app_context():
        user = db.session.get(Usuario, 1)
        user.trabalha_oceano_azul = False
        db.session.commit()
        assert operations.tools(user) == []
    with patch.object(operations, 'summarize') as summary:
        response = client(app,1).post('/api/azul/ajuda', json={
            'message':'O que precisa da minha atenção hoje?', 'trabalha_oceano_azul':True})
        assert 'exclusivo' in response.json['answer']
        summary.assert_not_called()


def test_dev_gets_technical_attention_and_no_municipal_query(app):
    seed(app)
    from app.models import AuditoriaUsuario
    with app.app_context():
        db.session.add(AuditoriaUsuario(usuario_nome='Teste', metodo='GET', path='/test',
            status_code=500, tipo_evento='ERRO', criado_em=datetime.utcnow()))
        db.session.commit()
    with patch.object(operations, 'build_admin_dashboard_query') as municipal:
        response = client(app,1).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'})
    assert response.status_code == 200
    assert 'atenção como DEV' in response.json['answer']
    assert '24 horas: 1.' in response.json['answer']
    assert '7 dias: 1.' in response.json['answer']
    assert response.json['links'][0]['url'] == '/dev'
    municipal.assert_not_called()


def test_employee_still_needs_panel_permission(app):
    seed(app)
    with patch.object(operations, 'can_access_endpoint', return_value=False), patch.object(operations, 'build_admin_dashboard_query') as query:
        response = client(app,3).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'})
    assert 'não permite' in response.json['answer']
    query.assert_not_called()


def test_group_links_match_counts_and_paginate_with_scope(app):
    seed(app)
    from urllib.parse import urlsplit, parse_qs
    from app.modules.admin_dashboard import attention
    from app.modules.admin_dashboard.service import build_admin_dashboard_query, build_admin_export_query
    response = client(app,3).post('/api/azul/ajuda', json={'message':'O que precisa da minha atenção hoje?'})
    with app.app_context():
        user = db.session.get(Usuario,3)
        for link in response.json['links']:
            if not link['label'].startswith('Ver todas'):
                continue
            args = {k:v[0] for k,v in parse_qs(urlsplit(link['url']).query).items()}
            selection = attention.parse(args)
            query = attention.apply(build_admin_dashboard_query(user,'','','','',''), selection)
            page = query.order_by(Solicitacao.id).paginate(page=1,per_page=1,error_out=False)
            assert page.total == 1
            assert page.items[0].prefeitura_id == 1
            export = attention.apply(build_admin_export_query(user,'','','','',''), selection)
            assert {r.id for r in export.all()} == {r.id for r in page.items}


def test_invalid_attention_filter_does_not_silently_show_all(app):
    import pytest
    from werkzeug.exceptions import BadRequest
    from app.modules.admin_dashboard.attention import parse
    for args in ({'atencao':'unknown','referencia':'2026-10-30'}, {'atencao':'hoje','referencia':'invalid'}):
        with pytest.raises(BadRequest):
            parse(args)


def test_large_summary_keeps_response_bounded(app):
    seed(app)
    from sqlalchemy import insert
    from datetime import time
    from app.modules.admin_dashboard import attention
    from app.modules.admin_dashboard.service import build_admin_dashboard_query
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    with app.app_context():
        db.session.execute(insert(Solicitacao), [dict(usuario_id=1, prefeitura_id=1,
            status='PENDENTE', data_agendamento=today, hora_agendamento=time(10),
            foco='Teste', tipo_visita='Aedes', cep='01000000', logradouro='Teste',
            bairro='Centro', cidade='Cidade', uf='SP') for _ in range(7100)])
        db.session.commit()
    response = client(app,3).post('/api/azul/ajuda',json={'message':'O que precisa da minha atenção hoje?'})
    assert 'para hoje: 7101.' in response.json['answer']
    assert len(response.json['answer']) < 2000
    assert len(response.json['links']) <= 9
    assert any('Ver todas (7101)' in link['label'] for link in response.json['links'])
    with app.app_context():
        query = build_admin_dashboard_query(db.session.get(Usuario,3),'','','','','')
        page = attention.apply(query, attention.parse({'atencao':'hoje','referencia':today.isoformat()})).order_by(Solicitacao.id).paginate(page=2,per_page=25)
        assert page.total == 7101
        assert len(page.items) == 25
