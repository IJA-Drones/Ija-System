"""Real grants/revocations, disposable SQLite only; never the project's DB."""
import re
import unittest
from io import BytesIO
from unittest.mock import patch

from flask import g, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import CentralTiPerfilConfiguracao, CentralTiSelecao, EquipePiloto, EstoquePeca, Pilotos, Solicitacao
from app.modules.gestao_ti.catalog import AREA_CODES, CATALOG, PERMISSION_CODES
from app.modules.gestao_ti.permissions import EXCLUSIONS, FIXED_ENDPOINTS, POLICY, active_configuration, can_access_endpoint, has_permission
from app.modules.gestao_ti.service import save_configurations
from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.relatorios.service import build_relatorios_solicitacoes_context, build_relatorios_os_context, build_relatorios_coleta_imagens_context
from app.modules.dji_flight_logs import service as dji_service
from app.models import DjiFlightKmlRoute, Denuncia, OrdemServico
from scripts.prepare_central_ti_neon import seed_profiles
from tests import test_central_ti as central_base
from tests.test_relatorios_region_team_filters import _seed_relatorio_rows


class CentralTiPermissionsTests(unittest.TestCase):
    tearDown = central_base.CentralTiTests.tearDown
    login = central_base.CentralTiTests.login
    editor_data = central_base.CentralTiTests.editor_data
    token = central_base.CentralTiTests.token
    save = central_base.CentralTiTests.save

    def setUp(self):
        central_base.CentralTiTests.setUp(self)
        self.app.config['CENTRAL_TI_ENFORCE_PERMISSIONS'] = True

    def configure(self, role, permissions=(), areas=None):
        row = db.session.get(CentralTiPerfilConfiguracao, role)
        version = row.versao if row else 0
        if areas is None: areas = sorted({code.split('.')[0] for code in permissions})
        save_configurations(self.users['dev'], {'profiles': [{
            'id': role, 'version': version, 'areas': list(areas), 'permissions': list(permissions),
        }]})
        g.pop('_central_ti_permissions', None)

    def test_every_business_endpoint_and_method_has_an_explicit_policy(self):
        for rule in self.app.url_map.iter_rules():
            if not rule.endpoint.startswith('main.'): continue
            if rule.endpoint in EXCLUSIONS or rule.endpoint in FIXED_ENDPOINTS: continue
            self.assertIn(rule.endpoint, POLICY, rule.endpoint)
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                self.assertIn(method, POLICY[rule.endpoint], (rule.endpoint, method))
        for methods in POLICY.values():
            for value in methods.values():
                for code in value if isinstance(value, list) else [value]:
                    self.assertIn(code[5:], AREA_CODES) if code.startswith('area:') else self.assertIn(code, PERMISSION_CODES)

    def test_a_new_unmapped_route_is_detected_before_activation(self):
        from app.modules.gestao_ti.permissions import validate_route_policy
        from werkzeug.routing import Rule
        validate_route_policy(self.app)
        self.app.url_map.add(Rule('/demo-unmapped',endpoint='main.demo_unmapped',methods=['GET']))
        with self.assertRaisesRegex(ValueError,'rota sem permissão'):
            validate_route_policy(self.app)

    def test_area_access_alone_does_not_expose_unselected_agro_dashboard_data(self):
        self.configure('piloto',areas=['agro'])
        self.login('piloto')
        response=self.client.get('/agro/admin')
        self.assertEqual(response.status_code,200)
        self.assertIn('Seu perfil ainda não possui funções liberadas',response.get_data(as_text=True))

    def test_clearing_a_profile_denies_all_business_routes_before_handlers(self):
        self.configure('admin')
        self.login('admin')
        with self.app.test_request_context():
            urls={}
            for rule in self.app.url_map.iter_rules():
                if rule.endpoint not in POLICY: continue
                values={key: 'test' if rule._converters[key].__class__.__name__ in {'UnicodeConverter','PathConverter'} else 1 for key in rule.arguments}
                urls[rule.endpoint]=url_for(rule.endpoint,**values)
        for endpoint,methods in POLICY.items():
            for method in methods:
                with self.subTest(endpoint=endpoint,method=method):
                    response=self.client.open(urls[endpoint],method=method)
                    self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.get('/acessos').status_code,200)
        self.assertEqual(EstoquePeca.query.count(),0)

    def test_a_newly_granted_report_appears_in_the_pilot_sidebar_and_opens(self):
        self.configure('piloto',['prefeitura.relatorios.consultar'])
        self.login('piloto')
        response=self.client.get('/relatorios')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertRegex(html,r'class="nav-link[^"\n]*" href="/relatorios"')
        self.assertEqual(self.client.get('/relatorios/solicitacoes?mes=7&ano=2026').status_code,200)
        self.assertEqual(self.client.get('/admin').status_code,403)
        self.assertEqual(self.client.get('/agro/admin').status_code,403)

    def test_consulting_inventory_does_not_grant_creation_editing_or_deletion(self):
        item=EstoquePeca(modelo_peca='Peça isolada',quantidade=3)
        db.session.add(item);db.session.commit()
        self.configure('piloto',['sistema.estoque.consultar'])
        self.login('piloto')
        response=self.client.get('/estoque')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertRegex(html,r'href="/estoque/novo"[^>]*data-ti-allowed="false"')
        self.assertRegex(html,rf'href="/estoque/{item.id}/editar"[^>]*data-ti-allowed="false"')
        self.assertRegex(html,rf'action="/estoque/{item.id}/deletar"[^>]*data-ti-allowed="false"')
        for path in ('/estoque/novo',f'/estoque/{item.id}/editar'):
            self.assertEqual(self.client.get(path).status_code,403)
        for path in ('/estoque/novo',f'/estoque/{item.id}/editar',f'/estoque/{item.id}/deletar'):
            self.assertEqual(self.client.post(path,data={'modelo_peca':'Alterada','quantidade':'0'}).status_code,403)
        self.assertEqual(db.session.get(EstoquePeca,item.id).quantidade,3)

    def test_each_inventory_mutation_can_be_granted_and_removed_independently(self):
        self.configure('piloto',['sistema.estoque.consultar','sistema.estoque.criar'])
        self.login('piloto')
        response=self.client.post('/estoque/novo',data={'modelo_peca':'Peça nova','quantidade':'2'})
        self.assertEqual(response.status_code,302)
        item=EstoquePeca.query.one()
        self.assertEqual(self.client.post(f'/estoque/{item.id}/deletar').status_code,403)
        self.configure('piloto',['sistema.estoque.consultar','sistema.estoque.editar'])
        self.assertEqual(self.client.get('/estoque/novo').status_code,403)
        response=self.client.post(f'/estoque/{item.id}/editar',data={'modelo_peca':'Peça editada','quantidade':'7'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(db.session.get(EstoquePeca,item.id).quantidade,7)
        self.configure('piloto',['sistema.estoque.consultar','sistema.estoque.excluir'])
        self.assertEqual(self.client.get(f'/estoque/{item.id}/editar').status_code,403)
        self.assertEqual(self.client.post(f'/estoque/{item.id}/deletar').status_code,302)
        self.assertEqual(EstoquePeca.query.count(),0)

    def test_revocation_applies_to_the_same_logged_in_session(self):
        self.configure('piloto',['prefeitura.relatorios.consultar'])
        self.login('piloto')
        self.assertEqual(self.client.get('/relatorios').status_code,200)
        self.configure('piloto')
        self.assertEqual(self.client.get('/relatorios').status_code,403)
        response=self.client.get('/acessos')
        self.assertNotIn('href="/relatorios"',response.get_data(as_text=True))
        with self.client.session_transaction() as stored:
            self.assertEqual(stored['_user_id'],str(self.users['piloto'].id))

    def test_export_requires_its_own_permission(self):
        self.configure('admin',['prefeitura.relatorios.consultar'])
        self.login('admin')
        self.assertEqual(self.client.get('/relatorios').status_code,200)
        for url in ('/admin/exportar_relatorio_excel','/relatorios-os/export/pdf','/relatorios-coleta-imagens/export/pdf-zip'):
            self.assertEqual(self.client.get(url).status_code,403)
        with self.app.test_request_context():
            self.assertFalse(can_access_endpoint(self.users['admin'],'main.relatorios_os_export_excel'))

    def test_area_and_consultar_dependencies_cannot_be_bypassed_by_db_codes(self):
        db.session.add(CentralTiPerfilConfiguracao(perfil_codigo='piloto',versao=1,atualizado_por_id=self.users['dev'].id))
        db.session.add(CentralTiSelecao(perfil_codigo='piloto',codigo='sistema.estoque.excluir'))
        db.session.commit()
        with self.app.test_request_context():
            self.assertFalse(has_permission(self.users['piloto'],'sistema.estoque.excluir'))

    def test_neutral_seeds_keep_legacy_rules_until_a_profile_is_saved(self):
        seed_profiles(db.session.connection(), CATALOG["profiles"]);db.session.commit()
        self.login('admin')
        self.assertEqual(self.client.get('/admin/usuarios').status_code,200)
        self.login('piloto')
        self.assertEqual(self.client.get('/relatorios').status_code,302)  # legacy guard redirects
        self.configure('piloto',['prefeitura.relatorios.consultar'])
        self.assertEqual(self.client.get('/relatorios').status_code,200)

    def test_dev_and_ti_manager_cannot_lock_their_central_out(self):
        for role in ('dev','gestor_ti'):
            self.configure(role)
            self.login(role)
            self.assertEqual(self.client.get('/central-ti').status_code,200)
            self.assertEqual(self.client.get('/admin/usuarios').status_code,403)

    def test_a_business_profile_cannot_grant_itself_the_ti_central(self):
        with self.assertRaisesRegex(ValueError,'exclusiva'):
            self.configure('admin',['sistema.perfis.consultar','sistema.perfis.configurar'])
        self.configure('admin',['sistema.usuarios.consultar'])
        self.login('admin')
        self.assertEqual(self.client.get('/central-ti').status_code,403)

    def test_the_editor_reports_active_rules_and_updates_current_checkmarks(self):
        self.login('dev');self.editor_data()
        response=self.save([{'id':'piloto','version':0,'areas':['prefeitura'],'permissions':['prefeitura.relatorios.consultar']}])
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['active_rules_changed'])
        state=next(state for state in self.editor_data()['states'] if state['id']=='piloto')
        self.assertEqual(state['current_rules']['permissions'],['prefeitura.relatorios.consultar'])

    def test_a_database_failure_does_not_restore_broad_legacy_access(self):
        self.login('admin')
        with self.assertLogs(self.app.logger,level='ERROR'), patch.object(db.session,'get',side_effect=SQLAlchemyError('isolated failure')):
            # Patch after login-user loading to exercise the permission lookup only.
            with self.app.test_request_context():
                with self.assertRaises(Exception) as raised:active_configuration(self.users['admin'])
                self.assertEqual(raised.exception.code,503)

    def seed_pilot_reports(self):
        _,north,south=_seed_relatorio_rows()
        pilot=Pilotos(nome_piloto='Piloto isolado',prefeitura_id=north.prefeitura_id)
        db.session.add(pilot);db.session.flush()
        self.users['piloto'].piloto=pilot
        db.session.add(EquipePiloto(equipe_id=north.id,piloto_id=pilot.id,papel='piloto'))
        db.session.commit()
        return north,south

    def test_new_report_grants_preserve_the_pilots_team_scope_in_all_reports(self):
        north,south=self.seed_pilot_reports()
        self.configure('piloto',['prefeitura.relatorios.consultar'])
        user=self.users['piloto']
        with self.app.test_request_context('/relatorios/solicitacoes'):
            args=MultiDict({'mes':'7','ano':'2026'})
            context=build_relatorios_solicitacoes_context(user,args)
            self.assertEqual(context['total_solicitacoes'],1)
            self.assertEqual([team.id for team in context['equipes_disponiveis']],[north.id])
            context=build_relatorios_solicitacoes_context(user,MultiDict({'mes':'7','ano':'2026','equipe_id':str(south.id)}))
            self.assertEqual(context['total_solicitacoes'],0)
            os_context=build_relatorios_os_context(user,args)
            self.assertEqual(os_context['total_os'],1)
            media_context=build_relatorios_coleta_imagens_context(user,args)
            self.assertEqual(media_context['paginacao'].total,1)

    def test_missing_municipal_binding_does_not_expose_other_tenants(self):
        _seed_relatorio_rows()
        self.configure('financeiro',['prefeitura.relatorios.consultar'])
        user=self.users['financeiro']
        with self.app.test_request_context('/relatorios/solicitacoes'):
            context=build_relatorios_solicitacoes_context(user,MultiDict({'mes':'7','ano':'2026'}))
            self.assertEqual(context['total_solicitacoes'],0)
            self.assertEqual(context['equipes_disponiveis'],[])
            self.assertEqual(context['uvis_disponiveis'],[])

    def test_editing_a_request_does_not_grant_approval_or_team_assignment(self):
        north,south=self.seed_pilot_reports()
        self.configure('admin',['prefeitura.solicitacoes.consultar','prefeitura.solicitacoes.editar'])
        self.login('admin')
        request_row=Solicitacao.query.filter_by(equipe_id=north.id).one()
        old=request_row.status
        response=self.client.post(f'/admin/atualizar/{request_row.id}',data={'status':'APROVADO'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(db.session.get(Solicitacao,request_row.id).status,old)
        self.assertEqual(self.client.post(f'/admin/atualizar/{request_row.id}',data={'equipe_id':str(south.id)}).status_code,403)

    def test_files_cannot_be_uploaded_through_an_edit_form_without_media_permission(self):
        self.configure('admin',['prefeitura.os.consultar','prefeitura.os.editar'])
        self.login('admin')
        response=self.client.post('/admin/os/1/formulario',data={'imagem_principal':(BytesIO(b'isolated'),'test.jpg')})
        self.assertEqual(response.status_code,403)

    def test_os_media_and_exports_preserve_the_newly_authorized_pilots_scope(self):
        north,south=self.seed_pilot_reports()
        self.configure('piloto',['prefeitura.os.consultar','prefeitura.os.exportar'])
        self.login('piloto')
        from app.shared.retorno_ciclo import get_accessible_solicitacao_for_retorno_ciclo
        mine=Solicitacao.query.filter_by(equipe_id=north.id).one()
        other=Solicitacao.query.filter_by(equipe_id=south.id).one()
        self.assertIsNotNone(get_accessible_solicitacao_for_retorno_ciclo(self.users['piloto'],mine.id))
        self.assertIsNone(get_accessible_solicitacao_for_retorno_ciclo(self.users['piloto'],other.id))
        from app.modules.piloto_os.routes import _ensure_os_region_access
        with self.app.test_request_context():
            from flask_login import login_user
            login_user(self.users['piloto'])
            with self.assertRaises(Exception) as raised:_ensure_os_region_access(other.id)
            self.assertEqual(raised.exception.code,404)

    def test_dji_routes_granted_to_a_pilot_do_not_leak_other_teams(self):
        north,south=self.seed_pilot_reports()
        routes=[]
        for index,team in enumerate((north,south),start=1):
            route=DjiFlightKmlRoute(route_code=f'demo-{index}',original_filename='demo.kml',
                stored_filename='demo.kml',stored_path='demo.kml',file_sha256=str(index)*64,points_json='[]')
            db.session.add(route);db.session.flush()
            solicitation=Solicitacao.query.filter_by(equipe_id=team.id).one()
            solicitation.ordem_servico.dji_kml_route_id=route.id
            routes.append(route)
        db.session.commit()
        self.configure('piloto',['prefeitura.voos.consultar','prefeitura.voos.importar'])
        self.login('piloto')
        self.assertEqual(self.client.get(f'/api/dji-kml-route/{routes[0].id}').status_code,200)
        self.assertEqual(self.client.get(f'/api/dji-kml-route/{routes[1].id}').status_code,403)
        self.assertEqual(self.client.post(f'/relatorios/dji-logs/rota/{routes[0].id}/excluir').status_code,403)
        self.assertEqual(self.client.post(f'/relatorios/dji-logs/rota/{routes[0].id}/vincular-os').status_code,403)
        with self.app.test_request_context():
            from flask_login import login_user
            login_user(self.users['piloto'])
            self.assertEqual([r.id for r in dji_service._build_filtered_kml_query().all()],[routes[0].id])
            self.assertEqual(dji_service._scope_dji_query(dji_service.DjiFlightLogImport.query,dji_service.DjiFlightLogImport).count(),0)

    def test_account_management_cannot_delegate_privileges_above_its_profile(self):
        from app.modules.gestao_ti.permissions import can_delegate_profile
        from app.modules.usuarios.service import can_manage_admin_user
        self.configure('piloto',['sistema.usuarios.consultar','sistema.usuarios.criar','sistema.usuarios.editar'])
        actor=self.users['piloto']
        self.assertFalse(can_delegate_profile(actor,'admin'))
        self.assertFalse(can_delegate_profile(actor,'dev'))
        self.assertFalse(can_delegate_profile(actor,'gestor_ti'))
        self.assertFalse(can_manage_admin_user(actor,self.users['admin']))
        self.assertFalse(can_manage_admin_user(actor,self.users['gestor_ti']))

    def test_denuncias_new_grants_preserve_tenant_and_linked_team(self):
        north,south=self.seed_pilot_reports()
        from app.modules.denuncias.service import _scope_denuncias, can_access_denuncia
        rows=[]
        for index,team in enumerate((north,south),start=1):
            solicitation=Solicitacao.query.filter_by(equipe_id=team.id).one()
            row=Denuncia(protocolo=f'DEMO-{index}',tipo_visita='Denuncia',foco='Teste',
                logradouro='Fictício',numero='1',bairro='Demo',cidade='Demo',uf='SP',
                cidadao_nome='Pessoa fictícia',cidadao_cpf='00000000000',cidadao_rg='000',
                cidadao_telefone='000',prefeitura_id=team.prefeitura_id,solicitacao_id=solicitation.id)
            db.session.add(row);rows.append(row)
        db.session.commit()
        self.configure('piloto',['prefeitura.denuncias.consultar'])
        self.assertEqual([r.id for r in _scope_denuncias(Denuncia.query,self.users['piloto']).all()],[rows[0].id])
        self.assertTrue(can_access_denuncia(self.users['piloto'],rows[0]))
        self.assertFalse(can_access_denuncia(self.users['piloto'],rows[1]))
        self.configure('financeiro',['prefeitura.denuncias.consultar'])
        self.assertEqual(_scope_denuncias(Denuncia.query,self.users['financeiro']).count(),0)

    def test_agro_pilot_flight_grants_do_not_expose_unlinked_foreign_imports(self):
        from app.models import AgroFlightKmlRoute, Usuario
        from app.modules.agro.flight_logs_service import _scope_agro_flights
        user=Usuario(nome_uvis='Piloto Agro fictício',login='test_agro_pilot',senha_hash='test-only',tipo_usuario='piloto_agro')
        db.session.add(user);db.session.flush()
        rows=[]
        for index,owner in enumerate((user,self.users['admin']),start=1):
            route=AgroFlightKmlRoute(route_code=f'agro-demo-{index}',original_filename='demo.kml',
                stored_filename='demo.kml',stored_path='demo.kml',file_sha256=str(index)*64,
                points_json='[]',uploaded_by_id=owner.id)
            db.session.add(route);rows.append(route)
        db.session.commit()
        self.configure('piloto_agro',['agro.voos.consultar'])
        self.assertEqual([r.id for r in _scope_agro_flights(AgroFlightKmlRoute.query,AgroFlightKmlRoute,user).all()],[rows[0].id])

    def test_configured_profiles_keep_csrf_protection(self):
        self.configure('piloto',['sistema.estoque.consultar','sistema.estoque.criar'])
        self.app.config['CSRF_PROTECTION_ENABLED']=True
        self.login('piloto')
        self.assertEqual(self.client.get('/estoque/novo').status_code,200)
        with self.assertLogs(self.app.logger,level='WARNING'):
            self.assertEqual(self.client.post('/estoque/novo',data={'modelo_peca':'Sem token'}).status_code,403)
        self.assertEqual(EstoquePeca.query.count(),0)

    def test_configured_finance_user_stays_in_finance_when_only_that_area_is_selected(self):
        self.configure('financeiro',['financeiro.contas.consultar'])
        self.login('financeiro')
        response=self.client.get('/financeiro')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/agro/admin').status_code,403)
        self.assertEqual(self.client.get('/admin').status_code,403)
        self.assertNotIn('href="/relatorios"',response.get_data(as_text=True))

    def test_login_falls_back_to_allowed_screens_after_home_access_is_removed(self):
        self.configure('piloto',['prefeitura.relatorios.consultar'])
        with self.app.test_request_context():
            self.assertEqual(get_authenticated_redirect_endpoint(self.users['piloto']),'main.acessos_dashboard')
