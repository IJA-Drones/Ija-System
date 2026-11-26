"""Draft, stock, scope and concurrency regressions in disposable SQLite only."""
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import g
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import set_committed_value
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Drones, EstoquePeca, ManutencaoEquipamento, ManutencaoPecaUso
from app.modules.equipamentos.manutencao import salvar_atendimento_manutencao
from app.modules.equipamentos.service import list_pecas_disponiveis_manutencao, get_manutencao_aberta, send_drone_to_manutencao
from app.shared.skybox import build_skybox_marker
from tests import test_manutencao_os as fixture
from tests.maintenance_helpers import worksheet_data


class UnifiedMaintenanceTests(unittest.TestCase):
    setUp = fixture.ManutencaoOsTests.setUp
    tearDown = fixture.ManutencaoOsTests.tearDown
    login = fixture.ManutencaoOsTests.login
    configure = fixture.ManutencaoOsTests.configure
    open_os = fixture.ManutencaoOsTests.open_os

    def start(self):
        self.open_os()
        return get_manutencao_aberta(self.drones[0], user=self.user)

    @property
    def path(self):
        return f'/equipamentos/{self.drones[0].id}/manutencao/pecas'

    def test_new_order_and_consumption_timestamps_are_naive_utc(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        order = self.start()
        self.client.post(self.path, data=worksheet_data(order, [(self.peca, 1)], complete=True))
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        use = ManutencaoPecaUso.query.one()
        for value in (order.aberta_em, order.encerrada_em, order.atualizada_em, use.criado_em):
            self.assertLessEqual(before, value)
            self.assertLessEqual(value, after)

    def test_legacy_maintenance_without_order_creates_only_on_valid_post(self):
        self.drones[0].status = 'Em Manutenção'; db.session.commit()
        page = self.client.get(self.path)
        self.assertIn('name="manutencao_id" value="0"', page.text)
        self.assertEqual(ManutencaoEquipamento.query.count(), 0)
        data = MultiDict(dict(manutencao_id='0', versao='0', acao='rascunho', avarias_identificadas='Relato legado'))
        response = self.client.post(self.path, data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ManutencaoEquipamento.query.one().versao, 1)
        self.assertEqual(self.peca.quantidade, 3)

    def test_draft_is_partial_preserves_rows_and_does_not_reserve_or_consume(self):
        order = self.start()
        data = worksheet_data(order, [(self.peca, 2, 'Troca do conjunto')], diagnostico_tecnico='', tipo_manutencao='', servicos_realizados='', observacoes_teste='', condicao_final='', drone_testado='0')
        data.add('avariada_id', str(self.peca.id)); data.add('avariada_nome', ''); data.add('avariada_descricao', 'Hélice trincada')
        response = self.client.post(self.path, data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.versao, 1)
        self.assertEqual(order.status, 'aberta')
        self.assertEqual(order.pecas_avariadas[0]['descricao'], 'Hélice trincada')
        self.assertEqual(order.pecas_reparo[0]['quantidade'], 2)
        self.assertEqual(self.peca.quantidade, 3)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)
        self.assertEqual(order.recebido_em, datetime(2026, 11, 26, 13, 30))
        self.assertEqual(self.drones[0].ultima_manutencao, date(2026, 1, 1))
        page = self.client.get(self.path).text
        for value in ('Hélice trincada', 'Troca do conjunto', '2026-11-26T10:30', 'Salvar rascunho', 'Concluir Ordem de Serviço'):
            self.assertIn(value, page)

    def test_full_completion_separates_damaged_components_and_new_parts_with_snapshot(self):
        order = self.start()
        damaged = EstoquePeca(prefeitura_id=1, modelo_peca='Bomba com defeito', modelos_compativeis='Matrice teste', codigo_dji='DJI-OLD', quantidade=0, status='baixada')
        self.peca.codigo_dji = 'DJI-NEW'
        db.session.add(damaged); db.session.commit()
        data = worksheet_data(order, [(self.peca, 2, 'Substituição do kit')], complete=True)
        data.add('avariada_id', str(damaged.id)); data.add('avariada_nome', 'Nome forjado'); data.add('avariada_descricao', 'Sem pressão')
        response = self.client.post(self.path, data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, 'encerrada')
        self.assertEqual(order.pecas_reparo, [])
        self.assertEqual(order.pecas_avariadas[0]['nome'], 'Bomba com defeito')
        self.assertEqual(damaged.quantidade, 0)
        use = ManutencaoPecaUso.query.one()
        self.assertEqual((use.peca_id, use.quantidade_usada, use.observacoes, use.codigo_dji_historico), (self.peca.id, 2, 'Substituição do kit', 'DJI-NEW'))
        self.assertEqual((self.peca.quantidade, self.drones[0].status), (1, 'Ativo'))
        self.peca.modelo_peca = 'Nome atualizado no estoque'; self.peca.codigo_dji = 'DJI-CHANGED'; db.session.commit()
        history = self.client.get(response.location).text
        self.assertIn('Hélice', history); self.assertIn('DJI-NEW', history); self.assertIn('Sem pressão', history)
        self.assertNotIn('DJI-CHANGED', history)
        self.assertIn('Diagnóstico técnico', history)

    def test_completion_without_replacement_is_valid_for_preventive_maintenance(self):
        order = self.start()
        response = self.client.post(self.path, data=worksheet_data(order, complete=True, tipo_manutencao='preventiva', servicos_realizados='Limpeza e ajuste preventivo'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, 'encerrada')
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)
        self.assertEqual(self.peca.quantidade, 3)

    def test_ineligible_for_operation_stays_inactive_even_when_os_is_complete(self):
        order = self.start()
        self.client.post(self.path, data=worksheet_data(order, complete=True, condicao_final='inapto', drone_testado='0', observacoes_teste='Sem condições de realizar voo de teste'))
        self.assertEqual(order.status, 'encerrada')
        self.assertEqual(self.drones[0].status, 'Inativo')

    def test_final_fields_and_tests_are_required_only_for_completion(self):
        order = self.start()
        response = self.client.post(self.path, data=worksheet_data(order, complete=True, diagnostico_tecnico='', drone_testado='0', recebido_em='inválida'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('A OS ainda não foi salva.', response.text)
        self.assertIn('Confirme os testes', response.text)
        self.assertIn('Informe uma data e hora', response.text)
        self.assertIn('value="Técnica de teste"', response.text)
        self.assertEqual((order.versao, order.status, self.peca.quantidade), (0, 'aberta', 3))

    def test_insufficient_draft_can_be_saved_but_completion_never_spends_partial_balance(self):
        order = self.start()
        self.client.post(self.path, data=worksheet_data(order, [(self.peca, 5)]))
        self.assertEqual(order.pecas_reparo[0]['quantidade'], 5)
        response = self.client.post(self.path, data=worksheet_data(order, [(self.peca, 5)], complete=True))
        self.assertIn('Saldo insuficiente', response.text)
        self.assertEqual((order.versao, self.peca.quantidade), (1, 3))
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)
        self.assertEqual(order.pecas_reparo[0]['quantidade'], 5)

    def test_stale_tab_never_overwrites_draft_or_finalizes(self):
        order = self.start()
        stale = worksheet_data(order, [(self.peca, 1)], complete=True)
        self.client.post(self.path, data=worksheet_data(order, diagnostico_tecnico='Diagnóstico da primeira aba'))
        response = self.client.post(self.path, data=stale)
        self.assertIn('mudou em outra aba', response.text)
        self.assertIn('Recarregar OS atualizada', response.text)
        self.assertEqual(order.diagnostico_tecnico, 'Diagnóstico da primeira aba')
        self.assertEqual((order.versao, order.status, self.peca.quantidade), (1, 'aberta', 3))

    def test_duplicate_completion_and_old_form_cannot_spend_on_new_os(self):
        order = self.start()
        payload = worksheet_data(order, [(self.peca, 1)], complete=True)
        self.client.post(self.path, data=payload)
        self.assertEqual(self.client.post(self.path, data=payload).status_code, 302)
        self.assertEqual(self.peca.quantidade, 2)
        send_drone_to_manutencao(self.drones[0], user=self.user)
        next_order = get_manutencao_aberta(self.drones[0], user=self.user)
        self.assertNotEqual(next_order.id, order.id)
        self.client.post(self.path, data=payload)
        self.assertEqual(next_order.versao, 0)
        self.assertEqual(next_order.status, 'aberta')
        self.assertEqual(ManutencaoPecaUso.query.count(), 1)
        self.assertEqual(self.peca.quantidade, 2)

    def test_previously_consumed_legacy_parts_are_not_debited_twice(self):
        order = self.start()
        self.peca.quantidade = 2
        db.session.add(ManutencaoPecaUso(prefeitura_id=1, manutencao=order, drone_id=self.drones[0].id, peca_id=self.peca.id, usuario_id=self.user.id, quantidade_usada=1))
        db.session.commit()
        page = self.client.get(self.path).text
        self.assertIn('Consumos já registrados', page)
        self.client.post(self.path, data=worksheet_data(order, [(self.peca, 1)], complete=True))
        self.assertEqual(self.peca.quantidade, 1)
        self.assertEqual(sum(row.quantidade_usada for row in order.pecas_usadas), 2)

    def test_cross_tenant_incompatible_archived_and_reserved_pieces_cannot_be_consumed(self):
        order = self.start()
        variants = [dict(prefeitura_id=2), dict(modelos_compativeis='Outro modelo'), dict(arquivada_em=datetime.now()), dict(status='reservada')]
        for extra in variants:
            fields = dict(prefeitura_id=1, modelo_peca='Restrita', modelos_compativeis='Matrice teste', quantidade=5); fields.update(extra)
            part = EstoquePeca(**fields); db.session.add(part); db.session.commit()
            response = self.client.post(self.path, data=worksheet_data(order, [(part, 1)], complete=True))
            self.assertIn('A OS ainda não foi salva.', response.text)
            self.assertEqual(part.quantidade, 5)
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)

    def test_invalid_rows_and_missing_version_do_not_mutate_saved_draft(self):
        order = self.start()
        for quantity in ('0', '-1', '1.5', 'abc', '100001'):
            response = self.client.post(self.path, data=worksheet_data(order, [(self.peca, quantity)]))
            self.assertIn('quantidade inteira positiva', response.text)
        duplicate = worksheet_data(order, [(self.peca, 1), (self.peca, 1)], complete=True)
        self.assertIn('cada peça uma única vez', self.client.post(self.path, data=duplicate).text)
        self.assertIn('Recarregue a OS', self.client.post(self.path, data={'acao': 'concluir'}).text)
        self.assertEqual(order.versao, 0)
        self.assertEqual(self.peca.quantidade, 3)

    def test_manual_damaged_part_is_allowed_when_not_in_stock(self):
        order = self.start()
        data = worksheet_data(order)
        for key, value in [('avariada_id', 'manual'), ('avariada_nome', 'Carcaça'), ('avariada_descricao', 'Trinca lateral')]: data.add(key, value)
        self.client.post(self.path, data=data)
        self.assertEqual(order.pecas_avariadas[0]['nome'], 'Carcaça')
        self.assertEqual(self.peca.quantidade, 3)

    def test_legacy_close_endpoint_redirects_to_versioned_worksheet_without_mutation(self):
        order = self.start()
        response = self.client.post(f'/equipamentos/{self.drones[0].id}/manutencao/encerrar')
        self.assertIn('/manutencao/pecas', response.location)
        self.assertEqual(order.status, 'aberta')
        self.client.post(self.path, data=worksheet_data(order, [(self.peca, 2)]))
        self.client.post(f'/equipamentos/{self.drones[0].id}/manutencao/encerrar')
        self.assertEqual(order.status, 'aberta')
        self.assertEqual(self.peca.quantidade, 3)
        self.client.post(self.path, data=worksheet_data(order, [(self.peca, 2)], complete=True))
        self.assertEqual(order.status, 'encerrada')
        self.assertEqual(self.peca.quantidade, 1)

    def test_csrf_is_present_and_post_protected(self):
        order = self.start()
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        self.assertIn('name="_csrf_token"', self.client.get(self.path).text)
        self.assertEqual(self.client.post(self.path, data=worksheet_data(order)).status_code, 403)
        self.assertEqual(order.versao, 0)

    def test_photos_compensate_uploaded_file_if_second_file_fails(self):
        order = self.start()
        marker = build_skybox_marker('manutencoes/teste/primeira.png')
        data = worksheet_data(order, [(self.peca, 1)], complete=True)
        data.setlist('imagens_ocorrido', [(BytesIO(b'png'), 'a.png'), (BytesIO(b'pdf'), 'b.pdf')])
        with patch('app.modules.equipamentos.service.upload_file_to_skybox', return_value=marker), patch('app.modules.equipamentos.service.delete_skybox_file') as remove:
            response = self.client.post(self.path, data=data)
        remove.assert_called_once_with(marker)
        self.assertIn('JPG, JPEG ou PNG', response.text)
        self.assertIn('Selecione os arquivos novamente', response.text)
        self.assertEqual((order.versao, order.status, self.peca.quantidade), (0, 'aberta', 3))
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)

    def test_commit_failure_removes_new_photo_and_rolls_back_stock(self):
        order = self.start()
        marker = build_skybox_marker('manutencoes/teste/nova.png')
        with patch('app.modules.equipamentos.manutencao._upload_maintenance_images', return_value=[marker]), patch('app.modules.equipamentos.manutencao.delete_skybox_file') as remove, patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated failure')):
            response = self.client.post(self.path, data=worksheet_data(order, [(self.peca, 1)], complete=True))
        remove.assert_called_once_with(marker)
        self.assertIn('Não foi possível salvar a OS', response.text)
        self.assertEqual((order.versao, order.status, self.peca.quantidade), (0, 'aberta', 3))
        self.assertEqual(ManutencaoPecaUso.query.count(), 0)

    def test_model_aliases_deduplicated_and_placeholder_hidden_without_renaming_equipment(self):
        first = self.drones[0]; first.modelo = 'T10'
        extra = Drones(prefeitura_id=1, modelo='DJI Agras T10', renomacao='Outro T10', numero_serie='T10-2', registro_anatel='teste', registro_anac='T10-2', pmd_kg=1)
        placeholder = Drones(prefeitura_id=1, modelo='TESTE', renomacao='Placeholder', numero_serie='TESTE', registro_anatel='teste', registro_anac='TESTE', pmd_kg=1)
        self.peca.modelos_compativeis = 'AGRAS T10'; db.session.add_all([extra, placeholder]); db.session.commit()
        self.login('dev')
        page = self.client.get(f'/estoque/{self.peca.id}/editar').text
        self.assertEqual(page.count('value="AGRAS T10"'), 1)
        self.assertNotIn('value="T10"', page); self.assertNotIn('value="TESTE"', page)
        self.assertNotIn('Equipamentos compatíveis', page)
        for drone in (first, extra): self.assertIn(self.peca, list_pecas_disponiveis_manutencao(drone, user=self.users['dev']))
        self.assertEqual(first.modelo, 'T10'); self.assertEqual(placeholder.modelo, 'TESTE')


class UnifiedMaintenanceMigrationTests(unittest.TestCase):
    def test_additive_upgrade_preserves_all_balances_and_existing_history(self):
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/f2b6a9c4e830_os_manutencao_unificada.py'
        spec = importlib.util.spec_from_file_location('maintenance_unified_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as conn:
                conn.execute(sa.text('CREATE TABLE estoque_pecas (id INTEGER PRIMARY KEY, quantidade INTEGER, modelos_compativeis TEXT)'))
                conn.execute(sa.text('CREATE TABLE manutencoes_equipamentos (id INTEGER PRIMARY KEY, status VARCHAR(30), avarias_identificadas TEXT)'))
                conn.execute(sa.text('CREATE TABLE manutencao_pecas_usadas (id INTEGER PRIMARY KEY, quantidade_usada INTEGER)'))
                conn.execute(sa.text("INSERT INTO estoque_pecas VALUES (1,8,'T10')")); conn.execute(sa.text("INSERT INTO manutencoes_equipamentos VALUES (1,'encerrada','Relato antigo')")); conn.execute(sa.text('INSERT INTO manutencao_pecas_usadas VALUES (1,2)'))
                with Operations.context(MigrationContext.configure(conn)): migration.upgrade()
                self.assertEqual(conn.execute(sa.text('SELECT quantidade,modelos_compativeis,codigo_dji FROM estoque_pecas')).one(), (8, 'T10', None))
                self.assertEqual(conn.execute(sa.text('SELECT status,avarias_identificadas,versao,recebido_em,pecas_reparo FROM manutencoes_equipamentos')).one(), ('encerrada', 'Relato antigo', 0, None, None))
                self.assertEqual(conn.execute(sa.text('SELECT quantidade_usada,nome_peca_snapshot FROM manutencao_pecas_usadas')).one(), (2, None))
                with Operations.context(MigrationContext.configure(conn)): migration.downgrade()
                self.assertEqual(conn.execute(sa.text('SELECT quantidade FROM estoque_pecas')).scalar(), 8)
        finally:
            engine.dispose()
