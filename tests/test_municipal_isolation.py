"""Cross-municipality regressions. All records live in disposable SQLite."""
from datetime import date, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask, g
from flask_login import LoginManager
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import NotFound

from app.extensions import db
from app.models import (Prefeitura, Usuario, Solicitacao, Denuncia, DenunciaAnexo, Equipe,
                        EstoquePeca, Notificacao, FeedbackTopico, CentralTiPerfilConfiguracao,
                        CentralTiSelecao, Drones, Clientes)
from app.modules.gestao_ti.catalog import PERMISSION_CODES, AREA_CODES
from app.modules.denuncias.service import (can_access_denuncia, count_denuncias_alerta,
    build_uvis_options_for_denuncia, designar_denuncia_para_uvis, _scope_denuncias)
from app.shared.access import apply_prefeitura_scope, apply_solicitacao_prefeitura_scope

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('covisa', 'visualizar', 'regional', 'prefeitura_admin', 'uvis', 'operario')


@pytest.fixture(params=[False, True], ids=['legacy', 'central-ti'])
def municipal(request, tmp_path):
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'), static_folder=str(ROOT / 'app/static'))
    app.config.update(TESTING=True, SECRET_KEY='isolated-municipal-tests',
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', CENTRAL_TI_ENABLED=request.param,
        CENTRAL_TI_ENFORCE_PERMISSIONS=request.param, CSRF_PROTECTION_ENABLED=False,
        SKYBOX_ENABLED=False, UPLOAD_FOLDER=str(tmp_path))
    db.init_app(app)
    manager = LoginManager(app)
    manager.user_loader(lambda uid: db.session.get(Usuario, int(uid)))

    @app.before_request
    def clear_user():
        g.pop('_login_user', None)
        g.pop('_central_ti_permissions', None)
        g.pop('_central_ti_team_ids', None)

    from app.routes import bp
    from app.modules.auth.routes import bp as auth_bp
    with patch('app.modules.backup.routes.start_daily_backup_scheduler'):
        app.register_blueprint(bp)
    app.register_blueprint(auth_bp)
    with app.app_context():
        db.create_all()
        users, reports, requests, teams, notices = {}, {}, {}, {}, {}
        for tenant in (1, 2):
            db.session.add(Prefeitura(id=tenant, nome=f'Prefeitura {tenant}', slug=f'prefeitura-{tenant}'))
            for role in ROLES:
                user = Usuario(nome_uvis=f'{role}-{tenant}', login=f'{role}-{tenant}', senha_hash='fixture',
                    tipo_usuario=role, prefeitura_id=tenant, regiao='COVISA' if role in ('covisa','visualizar') else 'NORTE')
                users[role, tenant] = user
                db.session.add(user)
            teams[tenant] = Equipe(nome_equipe=f'Equipe {tenant}', prefeitura_id=tenant, regiao='NORTE', ativa=True)
            db.session.add(teams[tenant])
        dev = Usuario(nome_uvis='Dev', login='dev', senha_hash='fixture', tipo_usuario='dev')
        db.session.add(dev)
        db.session.flush()
        for tenant in (1, 2):
            report = Denuncia(prefeitura_id=tenant, protocolo=f'DEN-{tenant}', status=Denuncia.STATUS_ENCAMINHADA_COORDENADORIA,
                coordenadoria='NORTE', tipo_visita='Culex', foco='Corrego', logradouro=f'Rua exclusiva {tenant}',
                numero='1', bairro='Centro', cidade='Teste', uf='SP', cidadao_nome=f'Pessoa {tenant}',
                cidadao_cpf='00000000000', cidadao_rg='', cidadao_telefone='000', consentimento=True)
            report.anexos.append(DenunciaAnexo(arquivo_path=f'{tenant}.txt', arquivo_nome=f'{tenant}.txt'))
            (tmp_path / f'{tenant}.txt').write_text(f'midia-{tenant}')
            reports[tenant] = report
            db.session.add(report)
            row = Solicitacao(prefeitura_id=tenant, usuario_id=users['uvis',tenant].id, equipe_id=teams[tenant].id,
                data_agendamento=date.today(), hora_agendamento=time(9), foco='Corrego', tipo_visita='Culex',
                cep='', logradouro=f'Rua exclusiva {tenant}', numero='1', bairro='Centro', cidade='Teste', uf='SP',
                status='APROVADO', latitude='-23.5', longitude='-46.6', anexo_path=f'{tenant}.txt')
            requests[tenant] = row
            db.session.add(row)
            db.session.add(EstoquePeca(modelo_peca=f'Peca {tenant}', quantidade=1, prefeitura_id=tenant))
            db.session.add(Clientes(nome_cliente=f'Cliente {tenant}', documento=str(tenant), prefeitura_id=tenant))
            db.session.add(Drones(modelo='Drone', renomacao=f'Drone {tenant}', registro_anatel=str(tenant),
                registro_anac=str(tenant), pmd_kg=10, prefeitura_id=tenant, equipe_id=teams[tenant].id))
            notice = Notificacao(usuario_id=users['covisa',tenant].id, titulo=f'Notificação {tenant}')
            notices[tenant] = notice
            db.session.add(notice)
            db.session.add(FeedbackTopico(prefeitura_id=tenant, uvis_usuario_id=users['uvis',tenant].id,
                uvis_nome=f'UVIS {tenant}', regiao='NORTE', criado_por_id=users['regional',tenant].id,
                criado_por_nome='Regional', titulo=f'Bug {tenant}', descricao='Teste', categoria='bug', setor_suporte='tecnico'))
        if request.param:
            for role in (*ROLES, 'dev'):
                code = 'covisa' if role == 'visualizar' else role
                if role == 'visualizar': continue
                db.session.add(CentralTiPerfilConfiguracao(perfil_codigo=code, versao=2))
                for permission in (*PERMISSION_CODES, *(f'area:{area}' for area in AREA_CODES)):
                    db.session.add(CentralTiSelecao(perfil_codigo=code, codigo=permission))
        db.session.commit()
        client = app.test_client()

        def login(role='covisa', tenant=1):
            user = dev if role == 'dev' else users[role,tenant]
            with client.session_transaction() as session:
                session['_user_id'] = str(user.id)
                session['_fresh'] = True
            return user

        yield SimpleNamespace(app=app, client=client, users=users, reports=reports, requests=requests,
                              teams=teams, notices=notices, login=login, dev=dev)
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.mark.parametrize('role', ['covisa','visualizar','regional','prefeitura_admin'])
def test_denuncia_same_region_does_not_cross_municipalities(municipal, role):
    m=municipal; user=m.login(role)
    assert can_access_denuncia(user,m.reports[1])
    assert not can_access_denuncia(user,m.reports[2])
    assert [row.id for row in _scope_denuncias(Denuncia.query,user)] == [m.reports[1].id]
    assert m.client.get(f'/denuncias/{m.reports[2].id}').status_code == 403
    assert m.client.get(f'/denuncias/anexos/{m.reports[2].anexos[0].id}').status_code == 403
    for action, data in [('encaminhar-coordenadoria',{'coordenadoria':'SUL'}),('arquivar',{'motivo':'Relato duplicado de teste'})]:
        assert m.client.post(f'/denuncias/{m.reports[2].id}/{action}',data=data).status_code == 403
    db.session.refresh(m.reports[2]); assert m.reports[2].status == Denuncia.STATUS_ENCAMINHADA_COORDENADORIA


def test_forward_options_and_forged_uvis_are_restricted_even_for_global_admin(municipal):
    m=municipal
    assert [u.id for u in build_uvis_options_for_denuncia(m.reports[1])] == [m.users['uvis',1].id]
    for actor in (m.users['regional',1],m.dev):
        with pytest.raises(ValueError,match='prefeitura'):
            designar_denuncia_para_uvis(m.reports[1],m.users['uvis',2].id,actor)
        assert m.reports[1].uvis_usuario_id is None
    designar_denuncia_para_uvis(m.reports[1],m.users['uvis',1].id,m.users['regional',1])
    assert m.reports[1].uvis_usuario_id == m.users['uvis',1].id


def test_alert_counts_and_missing_tenant_fail_closed(municipal):
    m=municipal
    assert count_denuncias_alerta(m.users['regional',1]) == 1
    for tenant in (1,2): m.reports[tenant].status=Denuncia.STATUS_RECEBIDA
    db.session.commit()
    assert count_denuncias_alerta(m.users['covisa',1]) == 1
    for role in ROLES:
        user=m.users[role,1]; user.prefeitura_id=None
        assert apply_prefeitura_scope(Solicitacao.query,user,Solicitacao.prefeitura_id).count()==0
        assert not can_access_denuncia(user,m.reports[2])
    assert apply_prefeitura_scope(Solicitacao.query,None,Solicitacao.prefeitura_id).count()==0
    assert apply_prefeitura_scope(Solicitacao.query,m.dev,Solicitacao.prefeitura_id).count()==2


def test_assets_lists_details_mutations_and_downloads(municipal):
    m=municipal; m.login('prefeitura_admin')
    user=m.users['prefeitura_admin',1]
    for model in (Equipe,Usuario,EstoquePeca,Clientes,Drones,Solicitacao):
        assert {row.prefeitura_id for row in apply_prefeitura_scope(model.query,user,model.prefeitura_id)} == {1}
    assert m.client.get('/clientes/2/editar').status_code in (403,404)
    assert m.client.get('/drones/2/editar').status_code==404
    assert m.client.post('/equipes/2/deletar').status_code==404
    assert m.client.get('/admin/uvis/'+str(m.users['uvis',2].id)+'/editar').status_code==404
    assert m.client.get('/admin/solicitacao/2/anexo').status_code==403
    assert m.client.post('/admin/atualizar/2',data={'status':'NEGADO'}).status_code==404
    db.session.refresh(m.requests[2]); assert m.requests[2].status=='APROVADO'


def test_maps_agenda_exports_and_bug_queries_share_tenant_scope(municipal):
    from app.modules.mapas.service import build_heatmap_query
    from app.modules.agenda_notificacoes.service import apply_agenda_user_scope
    from app.modules.feedback.routes import _build_coordination_bug_query
    m=municipal; user=m.users['regional',1]
    m.requests[1].status=m.requests[2].status='CONCLUÍDO'; db.session.commit()
    assert {r.prefeitura_id for r in apply_agenda_user_scope(Solicitacao.query,user)}=={1}
    assert {r.prefeitura_id for r in build_heatmap_query(user)}=={1}
    assert {r.prefeitura_id for r in _build_coordination_bug_query(user)}=={1}
    with m.app.test_request_context():
        from flask_login import login_user
        login_user(user)
        from app.modules.piloto_os.routes import _ensure_os_region_access
        _ensure_os_region_access(1)
        with pytest.raises(NotFound): _ensure_os_region_access(2)


def test_notifications_are_personal_for_municipal_accounts(municipal):
    from app.modules.agenda_notificacoes.service import get_notificacao_or_404,clear_notificacoes
    m=municipal; user=m.login('covisa')
    assert get_notificacao_or_404(user,m.notices[1].id).id==m.notices[1].id
    with pytest.raises(NotFound): get_notificacao_or_404(user,m.notices[2].id)
    clear_notificacoes(user)
    assert m.notices[1].apagada_em is not None
    assert m.notices[2].apagada_em is None


def test_account_management_cannot_change_another_tenant_or_move_own_uvis(municipal):
    m=municipal; m.login('prefeitura_admin')
    target=m.users['uvis',1]
    response=m.client.post(f'/admin/uvis/{target.id}/editar',data={
        'nome_uvis':target.nome_uvis,'login':target.login,'regiao':'NORTE','prefeitura_id':'2'})
    assert response.status_code in (200,302)
    db.session.refresh(target); assert target.prefeitura_id==1
    if m.app.config['CENTRAL_TI_ENABLED']:
        assert m.client.get(f'/admin/usuarios/{m.users["regional",2].id}/editar').status_code==403
        for endpoint in ('/backup/status','/dev/data','/admin/logs-usuarios'):
            assert m.client.get(endpoint).status_code==403


def test_public_report_requires_active_municipality(municipal):
    m=municipal
    data=dict(prefeitura_id='2',tipo_visita='Culex',foco='Corrego',logradouro='Rua Teste',numero='1',
        bairro='Centro',cidade='Teste',uf='SP',nome='Pessoa Teste',cpf='52998224725',telefone='11987654321',consentimento='1')
    with patch('app.modules.portal_cidadao.service._try_geocode_address'):
        response=m.client.post('/portal-cidadao/denuncias',data=data)
        assert response.status_code==201
        row=db.session.get(Denuncia,response.json['denuncia_id']); assert row.prefeitura_id==2
        for value in ('','999','invalid'):
            assert m.client.post('/portal-cidadao/denuncias',data={**data,'prefeitura_id':value}).status_code==400
        db.session.get(Prefeitura,2).ativa=False; db.session.commit()
        assert m.client.post('/portal-cidadao/denuncias',data=data).status_code==400


def test_creation_rejects_foreign_uvis_before_geocoding(municipal):
    from app.modules.solicitacoes.service import create_nova_solicitacao,NovoCadastroValidationError
    m=municipal
    form=MultiDict(dict(data=date.today().isoformat(),hora='09:00',logradouro='Rua Teste',numero='1',
        distrito_administrativo='Centro',uvis_responsavel_id=str(m.users['uvis',2].id)))
    with patch('app.modules.solicitacoes.service.resolve_google_place_id_for_address') as geocode:
        with pytest.raises(NovoCadastroValidationError,match='prefeitura'):
            create_nova_solicitacao(m.users['visualizar',1],form)
        geocode.assert_not_called()
    assert Solicitacao.query.count()==2


def test_own_download_works_and_foreign_export_does_not_call_renderer(municipal):
    from app.models import OrdemServico
    from app.modules.relatorios.service import build_relatorio_os_export_data
    m=municipal; m.login('prefeitura_admin')
    for tenant in (1,2):
        db.session.add(OrdemServico(solicitacao_id=m.requests[tenant].id, equipe_id=m.teams[tenant].id, data_aplicacao=date.today()))
    db.session.commit()
    with patch('app.modules.anexos.routes.resolve_attachment_file',return_value=('/tmp','fixture.txt','fixture.txt')), \
         patch('app.modules.anexos.routes.send_from_directory',return_value='own attachment') as send:
        assert m.client.get('/admin/solicitacao/1/anexo').data==b'own attachment'
        assert m.client.get('/admin/solicitacao/2/anexo').status_code==403
        send.assert_called_once()
    data=build_relatorio_os_export_data(m.users['prefeitura_admin',1],MultiDict(),include_ordens=True)
    assert data['total_os']==1
    for extension in ('pdf','excel'):
        assert m.client.get(f'/admin/os/2/export/{extension}/v2').status_code==404


def test_conflicting_team_rejected_without_partial_update(municipal):
    m=municipal; m.login('prefeitura_admin')
    response=m.client.post('/admin/atualizar/1',data={'status':'NEGADO','equipe_id':m.teams[2].id},
                           headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==400
    db.session.refresh(m.requests[1])
    assert m.requests[1].status=='APROVADO'
    assert m.requests[1].equipe_id==m.teams[1].id
    m.login('dev')
    response=m.client.post('/admin/atualizar/1',data={'status':'NEGADO','equipe_id':m.teams[2].id},
                           headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==400
    db.session.refresh(m.requests[1]); assert m.requests[1].status=='APROVADO'


def test_changed_account_binding_does_not_expose_previous_municipality(municipal):
    from app.modules.dashboard.service import build_dashboard_context
    from app.modules.agenda_notificacoes.service import apply_agenda_user_scope
    m=municipal; user=m.users['uvis',1]
    user.prefeitura_id=2; db.session.commit()
    assert apply_solicitacao_prefeitura_scope(Solicitacao.query,user).count()==0
    assert apply_agenda_user_scope(Solicitacao.query,user).count()==0
    with m.app.test_request_context():
        assert build_dashboard_context(user,MultiDict(),'')['solicitacoes']==[]


def test_supervisor_without_municipality_cannot_read_fleet(municipal):
    from app.shared.vehicle_supervisor import supervisor_equipment_query
    user=SimpleNamespace(id=999,tipo_usuario='sup_veiculos',prefeitura_id=None)
    assert supervisor_equipment_query(Drones,user).count()==0


def test_asset_links_cannot_move_records_between_municipalities(municipal):
    from app.modules.estoque.service import validate_peca_form
    from app.shared.access import resolve_linked_prefeitura
    m=municipal
    with pytest.raises(ValueError,match='prefeitura'):
        resolve_linked_prefeitura(1,m.teams[2])
    assert resolve_linked_prefeitura(None,m.teams[1])==1
    _,_,errors=validate_peca_form(MultiDict({'modelo_peca':'Peça','quantidade':'1','drone_id':'2'}),
                                existing_peca=db.session.get(EstoquePeca,1),user=m.dev)
    assert 'drone_id' in errors


def test_private_uploads_cannot_bypass_authorization_through_static_files(tmp_path):
    from whitenoise import WhiteNoise
    from app.shared.private_uploads import PrivateUploadsMiddleware
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    (tmp_path/'uploads/os/1').mkdir(parents=True)
    (tmp_path/'uploads/os/1/private.jpg').write_bytes(b'private')
    (tmp_path/'public.css').write_bytes(b'body{}')
    app=Flask(__name__,static_folder=str(tmp_path),static_url_path='/static')
    app.wsgi_app=PrivateUploadsMiddleware(WhiteNoise(app.wsgi_app,root=str(tmp_path)))
    client=Client(app,Response)
    for path in ('/uploads/os/1/private.jpg','/static/uploads/os/1/private.jpg',
                 '/static/%75ploads/os/1/private.jpg','/static/x/../uploads/os/1/private.jpg'):
        response=client.get(path)
        assert response.status_code==404
        assert response.headers['Cache-Control']=='private, no-store'
        assert b'private' not in response.data
    assert client.get('/public.css').status_code==200
    assert client.get('/static/public.css').status_code==200


def test_unlinked_account_cannot_create_municipal_records(municipal):
    m=municipal; user=m.login('prefeitura_admin')
    user.prefeitura_id=None; db.session.commit()
    response=m.client.post('/clientes/cadastrar',data={},headers={'Accept':'application/json'})
    assert response.status_code==403
    assert 'vinculada a uma prefeitura' in response.json['error']
    assert Clientes.query.count()==2


def test_public_form_lists_only_active_municipalities(municipal):
    m=municipal
    db.session.get(Prefeitura,2).ativa=False; db.session.commit()
    module='app.modules.portal_cidadao.routes.'
    with patch(module+'get_portal_health_news',return_value=[]), patch(module+'get_infodengue_alert',return_value={}):
        html=m.client.get('/portal-cidadao').get_data(as_text=True)
    assert 'name="prefeitura_id" required' in html
    assert '<option value="1">Prefeitura 1</option>' in html
    assert '<option value="2">Prefeitura 2</option>' not in html


def test_operational_uvis_credentials_are_scoped_before_any_change(municipal):
    from app.modules.uvis_equipes.service import build_admin_uvis_teams_listing
    m = municipal
    actor = m.login('operario')
    assert [row['uvis_id'] for row in build_admin_uvis_teams_listing(user=actor)] == [m.users['uvis', 1].id]
    assert len(build_admin_uvis_teams_listing(user=m.dev)) == 2
    with patch('app.modules.uvis_equipes.routes.upsert_operational_uvis_account') as save:
        response = m.client.post(f'/admin/uvis/{m.users["uvis", 2].id}/acesso-operacional', data={
            'login_operacional': 'foreign-reset', 'senha': 'Secret123!', 'senha2': 'Secret123!'})
        assert response.status_code == 404
        save.assert_not_called()


@pytest.mark.parametrize('tenant', [1, 2])
def test_new_uvis_team_inherits_owner_scope_and_cannot_read_foreign_media(municipal, tenant):
    from app.models import OrdemServico
    from app.modules.piloto_os.service import get_os_principal_image_path_for_user
    m = municipal
    owner = m.login('uvis', tenant)
    foreign = 3 - tenant
    response = m.client.post('/uvis/equipes/nova', data={
        'login_equipe': f'new-team-{tenant}', 'senha': 'Strong-Test-Password123!',
        'senha2': 'Strong-Test-Password123!', 'prefeitura_id': foreign,
        'equipe_uvis_uvis_usuario_id': m.users['uvis', foreign].id,
    })
    assert response.status_code == 302
    account = Usuario.query.filter_by(login=f'new-team-{tenant}').one()
    assert account.prefeitura_id == tenant
    assert account.equipe_uvis_uvis_usuario_id == owner.id
    assert account.regiao == owner.regiao
    assert {r.id for r in apply_solicitacao_prefeitura_scope(Solicitacao.query, account)} == {m.requests[tenant].id}
    for number in (1, 2):
        db.session.add(OrdemServico(solicitacao_id=m.requests[number].id,
            equipe_id=m.teams[number].id, imagem_principal=f'webdav://os/{number}/principal.jpg'))
    db.session.commit()
    assert get_os_principal_image_path_for_user(account, m.requests[tenant].id) == f'webdav://os/{tenant}/principal.jpg'
    with pytest.raises(NotFound):
        get_os_principal_image_path_for_user(account, m.requests[foreign].id)


@pytest.mark.parametrize('operation', ['team', 'operational'])
@pytest.mark.parametrize('invalid_owner', ['missing', 'inactive', 'wrong_role'])
def test_uvis_account_services_reject_invalid_owner_before_writing(municipal, operation, invalid_owner):
    from app.modules.uvis_equipes.service import create_team_account, upsert_operational_uvis_account
    m = municipal
    owner = m.users['uvis', 1]
    if invalid_owner == 'missing':
        owner.prefeitura_id = None
    elif invalid_owner == 'inactive':
        db.session.get(Prefeitura, 1).ativa = False
    else:
        owner = m.users['regional', 1]
    db.session.commit()
    before = Usuario.query.count()
    with pytest.raises(ValueError, match='UVIS|prefeitura'):
        if operation == 'team':
            create_team_account(owner, 'Equipe teste', 'invalid-team', 'Strong-Test-Password123!')
        else:
            upsert_operational_uvis_account(owner, 'invalid-operational', 'Strong-Test-Password123!')
    db.session.commit()
    assert Usuario.query.count() == before


def test_admin_gets_actionable_error_for_uvis_without_municipality(municipal):
    m = municipal
    m.login('dev')
    owner = m.users['uvis', 1]
    owner.prefeitura_id = None
    db.session.commit()
    response = m.client.post(f'/admin/uvis/{owner.id}/acesso-operacional', data={
        'login_operacional': 'invalid-operational', 'senha': 'Strong-Test-Password123!',
        'senha2': 'Strong-Test-Password123!'})
    assert response.status_code == 302
    assert Usuario.query.filter_by(login='invalid-operational').first() is None
    with m.client.session_transaction() as session:
        assert any('prefeitura' in message.lower() for _, message in session.get('_flashes', []))


def test_operational_update_preserves_existing_credentials_when_owner_unlinked(municipal):
    from app.modules.uvis_equipes.service import upsert_operational_uvis_account
    m = municipal
    owner = m.users['uvis', 1]
    account = upsert_operational_uvis_account(owner, 'original-operational', 'Strong-Test-Password123!')
    db.session.commit()
    old_hash = account.senha_hash
    owner.prefeitura_id = None
    db.session.commit()
    with pytest.raises(ValueError, match='prefeitura'):
        upsert_operational_uvis_account(owner, 'changed-operational', 'Other-Password123!')
    db.session.commit()
    db.session.refresh(account)
    assert account.prefeitura_id == 1
    assert account.login == 'original-operational'
    assert account.senha_hash == old_hash


@pytest.mark.parametrize('endpoint,login_field', [
    ('/uvis/equipes/nova', 'login_equipe'),
    ('/uvis/acesso-operacional', 'login_operacional'),
])
def test_inactive_municipality_returns_warning_without_creating_account(municipal, endpoint, login_field):
    m = municipal
    m.login('uvis')
    db.session.get(Prefeitura, 1).ativa = False
    db.session.commit()
    with patch('app.modules.uvis_equipes.routes.render_template', return_value='form preserved'):
        response = m.client.post(endpoint, data={login_field: 'inactive-team',
            'senha': 'Strong-Test-Password123!', 'senha2': 'Strong-Test-Password123!'})
    assert response.status_code == 200
    assert Usuario.query.filter_by(login='inactive-team').first() is None
    with m.client.session_transaction() as session:
        assert any('prefeitura ativa' in message for _, message in session.get('_flashes', []))


@pytest.mark.parametrize('tenant', [1, 2])
def test_operational_login_inherits_uvis_municipality_on_create_and_update(municipal, tenant):
    m = municipal
    owner = m.login('uvis', tenant)
    for login in ('operational-new', 'operational-updated'):
        response = m.client.post('/uvis/acesso-operacional', data={
            'login_operacional': login, 'prefeitura_id': 3 - tenant,
            'senha': 'Strong-Test-Password123!', 'senha2': 'Strong-Test-Password123!'})
        assert response.status_code == 302
        account = Usuario.query.filter_by(equipe_uvis_uvis_usuario_id=owner.id).one()
        assert account.login == login
        assert account.prefeitura_id == tenant


def test_support_permissions_do_not_grant_foreign_uvis_selection(municipal):
    from app.modules.feedback.service import user_can_use_uvis
    m = municipal
    with patch('app.modules.feedback.service.can_moderate_feedback', return_value=True):
        assert user_can_use_uvis(m.users['regional', 1], m.users['uvis', 1])
        assert not user_can_use_uvis(m.users['regional', 1], m.users['uvis', 2])
        assert user_can_use_uvis(m.dev, m.users['uvis', 2])


def test_reassigned_uvis_cannot_acknowledge_or_assign_old_municipality_os(municipal):
    from app.models import OrdemServico
    from app.modules.relatorios.service import registrar_visualizacao_coleta_imagens
    m = municipal
    actor = m.login('uvis')
    order = OrdemServico(solicitacao_id=m.requests[1].id, equipe_id=m.teams[1].id)
    db.session.add(order)
    db.session.commit()
    assert registrar_visualizacao_coleta_imagens(actor, m.requests[1].id).uvis_visualizado
    order.uvis_visualizado = False
    actor.prefeitura_id = 2
    db.session.commit()
    with pytest.raises(ValueError, match='OS nao encontrada'):
        registrar_visualizacao_coleta_imagens(actor, m.requests[1].id)
    assert not order.uvis_visualizado
    assert m.client.post(f'/solicitacao/{m.requests[1].id}/atribuir-equipe-uvis',
                         data={'nome_equipe': 'Equipe antiga'}).status_code == 404


def test_address_check_cannot_select_foreign_or_missing_municipality(municipal):
    m = municipal
    actor = m.login('prefeitura_admin')
    with patch('app.modules.solicitacoes.routes.find_solicitacao_bloqueada_por_place_id', return_value=None) as lookup:
        response = m.client.get('/api/solicitacao/checar-bloqueio', query_string={
            'place_id': 'same-place', 'uvis_responsavel_id': m.users['uvis', 2].id})
        assert response.status_code == 200
        assert lookup.call_args.kwargs['prefeitura_id'] == 1
        lookup.reset_mock()
        actor.prefeitura_id = None
        db.session.commit()
        assert m.client.get('/api/solicitacao/checar-bloqueio?place_id=same-place').status_code == 403
        lookup.assert_not_called()


def test_drone_details_and_form_validation_reject_conflicting_tenant(municipal):
    from app.modules.piloto_os.service import get_piloto_drone_payload, _get_valid_os_drone, PilotoOsError
    m = municipal
    actor = SimpleNamespace(id=999, tipo_usuario='piloto', prefeitura_id=1, piloto_id=999)
    # Even a stale team association must not override the explicit municipality.
    foreign_drone = db.session.get(Drones, 2)
    foreign_drone.equipe_id = m.teams[1].id
    db.session.commit()
    with pytest.raises(NotFound):
        get_piloto_drone_payload(actor, foreign_drone.id)
    with pytest.raises(PilotoOsError, match='pertencente a equipe'):
        _get_valid_os_drone(m.users['prefeitura_admin', 1], m.requests[1],
                           foreign_drone.id, 'pulverizacao', 'drone')


def test_selected_kml_route_must_be_in_authorized_options():
    from app.modules.piloto_os.service import _get_selected_dji_route
    allowed = SimpleNamespace(id=1)
    order = SimpleNamespace(dji_kml_route_id=2, dji_kml_route=SimpleNamespace(id=2))
    assert _get_selected_dji_route(order, [allowed]) is None
    order.dji_kml_route_id = 1
    assert _get_selected_dji_route(order, [allowed]) is allowed
