import io
from unittest.mock import patch

import pytest
from flask import g
from openpyxl import load_workbook

from app.extensions import db
from app.models import ParceiroAgro, ParceiroAgroHistorico, Prefeitura, CentralTiPerfilConfiguracao
from app.modules.agro import partners
from app.modules.chatbot import prospecting
from app.modules.gestao_ti.permissions import validate_route_policy
from tests.test_treinamentos import training


def candidate():
    return dict(name='Cooperativa DEMO',city='Itajubá/MG',phone='(35) 99999-1234',whatsapp='não confirmado',
                cultures='Café',services='Mapeamento de lavouras',approach='Conversar com a gerência',
                source_ids=[1])


def get_preview(training):
    training.app.config['OPENAI_API_KEY']='test-key'
    def answer(*args):
        g.fly_partner_candidates=([candidate()], [{'url':'https://cooperrita.com.br/lojas','title':'Fonte'}])
        return 'Parceiro encontrado.', []
    with patch.object(prospecting,'answer',side_effect=answer), patch('app.modules.chatbot.azul.consume_help_quota',return_value=True):
        response=training.client.post('/api/azul/ajuda',json={'message':'Busque cooperativas','page':'/agro/admin'})
    assert response.status_code==200, response.text
    return response.json['partner_preview']


def edit_values(row, **changes):
    return dict(nome=row.nome,cidade=row.cidade,telefone=row.telefone,whatsapp=row.whatsapp,
                oportunidade=row.oportunidade,versao=row.versao,status='CONTATADO',
                observacao='Conversei com a gerência.',responsavel='João',**changes)


def test_preview_selection_save_deduplicate_and_export(training):
    training.login('dev')
    preview=get_preview(training)
    assert ParceiroAgro.query.count()==0
    payload={'token':preview['token'],'selected':[0]}
    first=training.client.post(preview['save_url'],json=payload)
    assert first.status_code==200
    assert first.json['created']==1
    row=ParceiroAgro.query.one()
    assert row.status=='A_ABORDAR'
    assert row.prefeitura_id==14
    assert row.fontes[0]['url']=='https://cooperrita.com.br/lojas'
    result=training.client.post(f'/agro/parceiros/{row.id}/atualizar',data=edit_values(row))
    assert result.status_code==302
    db.session.expire_all()
    row=ParceiroAgro.query.one()
    assert row.status=='CONTATADO' and row.ultimo_contato
    assert len(row.historico)==2
    assert row.historico[0].usuario_id==training.users['dev'].id
    assert 'gerência' in row.historico[0].observacao
    again=training.client.post(preview['save_url'],json=payload)
    assert again.json['existing']==1 and again.json['created']==0
    assert ParceiroAgro.query.one().status=='CONTATADO'
    assert ParceiroAgroHistorico.query.count()==2
    export=training.client.get('/agro/parceiros/excel?status=CONTATADO')
    assert export.status_code==200
    book=load_workbook(io.BytesIO(export.data))
    sheet=book['Parceiros']
    assert sheet['A2'].value==row.nome
    assert sheet['C2'].value==row.telefone
    assert sheet['H2'].value=='Contatado'
    assert sheet.freeze_panes=='A2'
    assert training.client.get('/agro/parceiros?status=CONTATADO').status_code==200
    detail=training.client.get(f'/agro/parceiros/{row.id}')
    assert detail.status_code==200 and 'Conversei com a gerência.' in detail.text


def test_signed_selection_cannot_be_modified_or_replayed_by_another_user(training):
    training.login('dev');preview=get_preview(training)
    for payload in [{'token':preview['token']+'x','selected':[0]},
                    {'token':preview['token'],'selected':[999]},
                    {'token':preview['token'],'selected':[]},
                    {'token':preview['token'],'selected':[True]}]:
        assert training.client.post(preview['save_url'],json=payload).status_code==400
    training.users['operario'].trabalha_agro=True
    db.session.commit();training.login('operario')
    assert training.client.post(preview['save_url'],json={'token':preview['token'],'selected':[0]}).status_code==403
    assert ParceiroAgro.query.count()==0


def test_tenant_scope_covers_details_updates_and_excel(training):
    training.login('dev');p=get_preview(training)
    training.client.post(p['save_url'],json={'token':p['token'],'selected':[0]})
    row=ParceiroAgro.query.one()
    db.session.add(Prefeitura(id=15,nome='Outra unidade',slug='outra-parceiros'))
    user=training.users['operario'];user.trabalha_agro=True;user.prefeitura_id=15
    db.session.commit();training.login('operario')
    assert training.client.get(f'/agro/parceiros/{row.id}').status_code==404
    assert training.client.post(f'/agro/parceiros/{row.id}/atualizar',data=edit_values(row)).status_code==404
    excel=training.client.get('/agro/parceiros/excel')
    assert load_workbook(io.BytesIO(excel.data)).active.max_row==1


def test_stale_updates_do_not_overwrite_history(training):
    training.login('dev');p=get_preview(training)
    training.client.post(p['save_url'],json={'token':p['token'],'selected':[0]})
    row=ParceiroAgro.query.one();values=edit_values(row)
    assert training.client.post(f'/agro/parceiros/{row.id}/atualizar',data=values).status_code==302
    assert training.client.post(f'/agro/parceiros/{row.id}/atualizar',data=values).status_code==409
    assert ParceiroAgroHistorico.query.count()==2


def test_permission_revocation_blocks_list_save_and_export(training):
    training.login('dev');p=get_preview(training)
    db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='dev',versao=1));db.session.commit()
    assert training.client.get('/agro/parceiros').status_code==403
    assert training.client.post(p['save_url'],json={'token':p['token'],'selected':[0]}).status_code==403
    assert training.client.get('/agro/parceiros/excel').status_code==403


def test_excel_treats_formulas_and_phone_numbers_as_literal_text():
    book=load_workbook(partners.workbook([{'nome':'=HYPERLINK("https://evil.example")','cidade':'+123',
                                          'telefone':'0012345','oportunidade':'@SUM(A1:A3)','fontes':[]}]))
    sheet=book.active
    assert sheet['A2'].data_type=='s'
    assert sheet['B2'].data_type=='s'
    assert sheet['C2'].value=='0012345'
    assert sheet['E2'].data_type=='s'


def test_csrf_required_for_saving_with_authenticated_cookie(training):
    training.login('dev');p=get_preview(training)
    training.app.config['CSRF_PROTECTION_ENABLED']=True
    response=training.client.post(p['save_url'],json={'token':p['token'],'selected':[0]})
    assert response.status_code==403
    assert ParceiroAgro.query.count()==0


def test_research_excel_does_not_create_records(training):
    training.login('dev');p=get_preview(training)
    response=training.client.post(p['export_url'],json={'token':p['token'],'selected':[0]})
    assert response.status_code==200
    assert load_workbook(io.BytesIO(response.data)).active['A2'].value=='Cooperativa DEMO'
    assert ParceiroAgro.query.count()==0


def test_partner_routes_have_permission_policies(training):
    validate_route_policy(training.app)
