"""Individual capability isolation, using disposable SQLite only."""
import importlib.util
import re
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import g
from sqlalchemy import create_engine, inspect, text

from app.extensions import db
from app.models import (CentralTiUsuarioAuditoria, CentralTiUsuarioConfiguracao, Usuario,
                        Prefeitura, Veiculos)
from app.modules.gestao_ti.permissions import active_configuration, has_permission
from app.modules.gestao_ti.service import ConfigurationConflict, save_configurations
from app.modules.gestao_ti.user_permissions import save_user_configuration, user_configuration, search_users
from tests import test_central_ti as central_fixture
from scripts.prepare_central_ti_users_neon import target_url


class CentralTiUserTests(unittest.TestCase):
    tearDown = central_fixture.CentralTiTests.tearDown
    login = central_fixture.CentralTiTests.login

    def setUp(self):
        central_fixture.CentralTiTests.setUp(self)
        self.app.config.update(CENTRAL_TI_ENFORCE_PERMISSIONS=True, CENTRAL_TI_USER_PERMISSIONS_ENABLED=True)
        second = Usuario(nome_uvis='Outra UVIS', login='other-uvis', senha_hash='test-only', tipo_usuario='uvis')
        db.session.add(second); db.session.commit()
        self.users['second'] = second
        self.actor = self.users['dev']

    def payload(self, permissions=(), version=0, areas=None, name='Acesso teste'):
        return {'version': version, 'nome_acesso': name, 'permissions': list(permissions),
                'areas': list(areas if areas is not None else sorted({p.split('.')[0] for p in permissions}))}

    def save(self, user='uvis', permissions=(), version=0, **kwargs):
        return save_user_configuration(self.actor, self.users[user].id, self.payload(permissions, version, **kwargs))

    def test_users_with_same_role_have_independent_capabilities_in_one_request(self):
        self.save(permissions=['prefeitura.veiculos.consultar'])
        self.save('second', ['prefeitura.checklists.consultar'])
        with self.app.test_request_context('/'):
            self.assertTrue(has_permission(self.users['uvis'], 'prefeitura.veiculos.consultar'))
            self.assertFalse(has_permission(self.users['second'], 'prefeitura.veiculos.consultar'))
            self.assertTrue(has_permission(self.users['second'], 'prefeitura.checklists.consultar'))
            self.assertFalse(has_permission(self.users['uvis'], 'prefeitura.checklists.consultar'))

    def test_unconfigured_user_inherits_and_empty_personal_selection_denies(self):
        self.assertIsNone(active_configuration(self.users['uvis']))
        save_configurations(self.actor, {'profiles': [{'id': 'uvis', 'version': 0, 'areas': ['prefeitura'],
            'permissions': ['prefeitura.veiculos.consultar']}]})
        g.pop('_central_ti_permissions', None)
        self.assertTrue(has_permission(self.users['uvis'], 'prefeitura.veiculos.consultar'))
        self.save()
        self.assertEqual(active_configuration(self.users['uvis']), frozenset())
        self.assertTrue(has_permission(self.users['second'], 'prefeitura.veiculos.consultar'))

    def test_later_profile_change_does_not_rewrite_personal_selection(self):
        self.save(permissions=['prefeitura.veiculos.consultar'])
        save_configurations(self.actor, {'profiles': [{'id': 'uvis', 'version': 0, 'areas': ['prefeitura'],
            'permissions': ['prefeitura.checklists.consultar']}]})
        g.pop('_central_ti_permissions', None)
        self.assertTrue(has_permission(self.users['uvis'], 'prefeitura.veiculos.consultar'))
        self.assertTrue(has_permission(self.users['second'], 'prefeitura.checklists.consultar'))

    def test_save_keeps_account_role_scope_and_other_accounts_unchanged(self):
        user = self.users['uvis']; user.regiao = 'SUL'; user.codigo_setor = '23'; db.session.commit()
        original = (user.tipo_usuario, user.prefeitura_id, user.regiao, user.codigo_setor, user.senha_hash)
        saved = self.save(permissions=['prefeitura.veiculos.consultar'])
        self.assertEqual(saved['version'], 1)
        self.assertEqual((user.tipo_usuario, user.prefeitura_id, user.regiao, user.codigo_setor, user.senha_hash), original)
        self.assertIsNone(db.session.get(CentralTiUsuarioConfiguracao, self.users['second'].id))
        audit = CentralTiUsuarioAuditoria.query.one()
        self.assertEqual((audit.usuario_id, audit.usuario_alvo_id, audit.versao_anterior, audit.versao_nova), (self.actor.id, user.id, 0, 1))
        from app.modules.gestao_ti.permission_versions import VEHICLE_DETAILS
        self.assertEqual(audit.depois['permissions'], sorted({'prefeitura.veiculos.consultar', *VEHICLE_DETAILS}))

    def test_stale_save_conflicts_and_noop_does_not_increment_version(self):
        self.save(permissions=['prefeitura.veiculos.consultar'])
        same = self.save(permissions=['prefeitura.veiculos.consultar'], version=1)
        self.assertEqual(same['version'], 1)
        with self.assertRaises(ConfigurationConflict): self.save(permissions=[], version=0)
        self.assertEqual(CentralTiUsuarioAuditoria.query.count(), 1)

    def test_invalid_actions_dependencies_and_reserved_central_are_rejected(self):
        for permissions, areas in [(['inventada'], ['prefeitura']), (['prefeitura.veiculos.editar'], ['prefeitura']),
                                    (['prefeitura.veiculos.consultar'], []),
                                    (['sistema.perfis.consultar'], ['sistema'])]:
            with self.subTest(permissions=permissions), self.assertRaises(ValueError):
                self.save(permissions=permissions, areas=areas)
        self.assertEqual(CentralTiUsuarioConfiguracao.query.count(), 0)

    def test_page_lists_users_and_protects_csrf_and_version(self):
        self.login('dev')
        response = self.client.get('/central-ti/usuarios')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Por usuário', response.text)
        with self.client.session_transaction() as session:
            csrf = session['_ija_central_ti_csrf']['token']
        path = f'/central-ti/usuarios/{self.users["uvis"].id}/permissoes'
        self.assertEqual(self.client.post(path, json=self.payload()).status_code, 403)
        response = self.client.post(path, json=self.payload(['prefeitura.veiculos.consultar']), headers={'X-Central-TI-CSRF': csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json['configuration']['version'], 1)
        self.assertEqual(self.client.post(path, json=self.payload(), headers={'X-Central-TI-CSRF': csrf}).status_code, 409)

    def test_global_csrf_and_central_csrf_are_both_required(self):
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        self.login('dev')
        response = self.client.get('/central-ti/usuarios')
        with self.client.session_transaction() as session:
            central = session['_ija_central_ti_csrf']['token']; global_token = session['_ija_csrf']
        path = f'/central-ti/usuarios/{self.users["uvis"].id}/permissoes'
        self.assertEqual(self.client.post(path, json=self.payload(), headers={'X-Central-TI-CSRF': central}).status_code, 403)
        self.assertEqual(self.client.post(path, json=self.payload(), headers={'X-Central-TI-CSRF': central, 'X-CSRFToken': global_token}).status_code, 200)

    def test_non_managers_cannot_list_read_or_write_other_accounts(self):
        self.login('admin')
        for path in ('/central-ti/usuarios', '/central-ti/usuarios/busca', f'/central-ti/usuarios/{self.users["uvis"].id}'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post(f'/central-ti/usuarios/{self.users["uvis"].id}/permissoes', json=self.payload()).status_code, 403)

    def test_feature_disabled_preserves_legacy_engine_without_querying_personal_tables(self):
        self.save(permissions=['prefeitura.veiculos.consultar'])
        self.app.config['CENTRAL_TI_USER_PERMISSIONS_ENABLED'] = False
        g.pop('_central_ti_permissions', None)
        self.assertIsNone(active_configuration(self.users['uvis']))
        self.login('dev')
        self.assertEqual(self.client.get('/central-ti/usuarios').status_code, 404)

    def test_custom_vehicle_permission_updates_route_and_menu_only_for_selected_user(self):
        self.save(permissions=['prefeitura.veiculos.consultar', 'prefeitura.checklists.consultar'])
        self.login('uvis')
        response = self.client.get('/veiculos/menu')
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/admin/checklists/semanais"', response.text)
        self.assertEqual(self.client.get('/admin/checklists/semanais').status_code, 200)
        self.assertEqual(self.client.get('/central-ti/usuarios').status_code, 403)
        self.assertEqual(self.client.post('/veiculos/equipes', data={}).status_code, 403)
        self.login('second')
        self.assertEqual(self.client.get('/admin/checklists/semanais').status_code, 403)

    def test_personal_vehicle_consultation_preserves_municipal_scope(self):
        db.session.add_all([Prefeitura(id=1, nome='Primeiro município', slug='primeiro-municipio'),
                            Prefeitura(id=2, nome='Segundo município', slug='segundo-municipio')])
        for tenant in (1, 2):
            db.session.add(Veiculos(modelo='Veículo teste', renomacao=f'Teste {tenant}', placa=f'ABC{tenant}D23',
                                   frota='PROPRIA', operacao='PMSP', prefeitura_id=tenant, status='Ativo'))
        self.users['second'].tipo_usuario = 'manutencao'; self.users['second'].prefeitura_id = 1
        db.session.commit()
        self.save('second', ['prefeitura.veiculos.consultar'])
        self.login('second')
        response = self.client.get('/veiculos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('ABC1D23', response.text); self.assertNotIn('ABC2D23', response.text)

    def test_training_materials_follow_personal_vehicle_access(self):
        self.save(permissions=['prefeitura.veiculos.consultar'])
        self.login('uvis')
        page = self.client.get('/treinamentos')
        self.assertEqual(page.status_code, 200)
        self.assertIn('guia-rastreamento-veiculos', page.text)
        self.assertNotIn('video-quadra', page.text)

    def test_search_is_paginated_and_never_exposes_passwords_or_dev(self):
        result = search_users(self.actor, 'other-uvis')
        self.assertEqual([user['id'] for user in result['users']], [self.users['second'].id])
        self.assertNotIn('senha_hash', str(result)); self.assertNotIn('test-only', str(result))
        self.assertEqual(search_users(self.actor, self.actor.login)['users'], [])

    def test_ti_manager_can_configure_users_but_dev_recovery_account_is_protected(self):
        saved = save_user_configuration(self.users['gestor_ti'], self.users['uvis'].id,
                                         self.payload(['prefeitura.veiculos.consultar']))
        self.assertEqual(saved['version'], 1)
        self.login('gestor_ti')
        self.assertEqual(self.client.get('/central-ti/usuarios').status_code, 200)
        self.assertEqual(self.client.get(f'/central-ti/usuarios/{self.actor.id}').status_code, 403)

    def test_personal_grant_never_allows_delegated_account_manager_to_edit_a_more_privileged_user(self):
        from app.modules.usuarios.service import can_manage_admin_user
        city = Prefeitura(nome='Município teste', slug='municipio-teste')
        db.session.add(city); db.session.flush()
        actor = self.users['operario']; target = self.users['uvis']
        actor.prefeitura_id = target.prefeitura_id = city.id; db.session.commit()
        self.save('operario', ['sistema.usuarios.consultar', 'sistema.usuarios.editar', 'prefeitura.veiculos.consultar'])
        self.save('uvis', ['prefeitura.veiculos.consultar', 'prefeitura.checklists.consultar'])
        self.assertFalse(can_manage_admin_user(actor, target))

    def test_overlarge_payload_is_rejected_before_parsing(self):
        self.login('dev'); self.client.get('/central-ti/usuarios')
        with self.client.session_transaction() as stored:
            token = stored['_ija_central_ti_csrf']['token']
        response = self.client.post(f'/central-ti/usuarios/{self.users["uvis"].id}/permissoes',
            data=' ' * 262145, content_type='application/json', headers={'X-Central-TI-CSRF': token})
        self.assertEqual(response.status_code, 413)


class CentralTiUserNeonTargetTests(unittest.TestCase):
    def test_uses_commented_neon_and_ignores_active_render(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('DATABASE_URL=postgresql://test:fake@render.example/app\n# DATABASE_URL=postgresql://test:fake@ep-test.neon.tech/test?sslmode=require\n')
            url, fingerprint = target_url(root)
            self.assertEqual(url.host, 'ep-test.neon.tech'); self.assertEqual(len(fingerprint), 16)

    def test_rejects_non_neon_missing_ssl_and_host_overrides(self):
        for value in ('postgresql://test:fake@render.example/app?sslmode=require',
                      'postgresql://test:fake@ep-test.neon.tech/test',
                      'postgresql://test:fake@ep-test.neon.tech/test?sslmode=require&host=render.example'):
            with self.subTest(value=value), TemporaryDirectory() as temp:
                root = Path(temp); (root / '.env.neon.local').write_text('DATABASE_URL=' + value)
                with self.assertRaises(ValueError): target_url(root)


class CentralTiUserMigrationTests(unittest.TestCase):
    def test_migration_is_additive_and_reversible_without_touching_accounts(self):
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/d92e7a4b6c81_add_central_ti_user_permissions.py'
        spec = importlib.util.spec_from_file_location('individual_permissions_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        engine = create_engine('sqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT)'))
            connection.execute(text("INSERT INTO usuarios VALUES (1, 'preservado')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.validate_existing_schema(connection)
                migration.upgrade()
                self.assertNotEqual(migration._check_expression('versao >= 0'), migration._check_expression('versao >= 1'))
                self.assertEqual(migration._check_expression('((versao_anterior >= 0) AND (versao_nova > versao_anterior))'),
                                 migration._check_expression('versao_anterior >= 0 AND versao_nova > versao_anterior'))
                self.assertIn('central_ti_usuarios_configuracoes', inspect(connection).get_table_names())
                self.assertEqual(connection.execute(text('SELECT nome FROM usuarios')).scalar_one(), 'preservado')
                migration.downgrade()
            self.assertEqual(inspect(connection).get_table_names(), ['usuarios'])
        engine.dispose()
