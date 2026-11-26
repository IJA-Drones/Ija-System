"""Excel upload, review and atomic import: all databases here are disposable SQLite."""
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import g
from openpyxl import Workbook, load_workbook
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import EstoqueImportacao, EstoquePeca, ManutencaoPecaUso, Usuario
from app.modules.estoque.importacao import read_excel, create_preview, confirm_preview, preview_state, now, INVENTORY_HEADERS, preview_revision
from app.modules.estoque.service import list_pecas
from app.modules.equipamentos.service import send_drone_to_manutencao, registrar_pecas_usadas_manutencao
from tests import test_estoque_compatibilidade as fixture

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ['Peça *', 'Número de série', 'Quantidade *', 'Prateleira/Local', 'Modelos compatíveis',
           'Equipamentos compatíveis (nº de série)', 'Status', 'Observações']


def excel(rows, headers=HEADERS, sheet='Peças'):
    workbook = Workbook()
    workbook.active.title = sheet
    workbook.active.append(headers)
    for row in rows:
        workbook.active.append(row)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def upload(rows):
    return FileStorage(stream=excel(rows), filename='pecas.xlsx')


def inventory_upload(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        sheet.append(['Título do inventário'])
        sheet.append(INVENTORY_HEADERS)
        for row in rows:
            sheet.append(row)
    summary = workbook.create_sheet('RESUMO GERAL')
    summary.append(['TOTAL', '=SUM(1,2)'])  # Derived summary must never be imported.
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return FileStorage(stream=stream, filename='inventario.xlsm')


class EstoqueImportacaoTests(unittest.TestCase):
    setUp = fixture.EstoqueCompatibilidadeTests.setUp
    tearDown = fixture.EstoqueCompatibilidadeTests.tearDown
    login = fixture.EstoqueCompatibilidadeTests.login

    def post_excel(self, rows, **extra):
        return self.client.post('/estoque/importar', data={'prefeitura_id': '1', 'arquivo': (excel(rows), 'pecas.xlsx'), **extra})

    def test_fernando_inventory_maps_locations_codes_and_models_without_serial_invention(self):
        file = inventory_upload({'T10': [
            [1, ' T10 ', 'SKU-1', 'A2', 'Hélice', 4, '01 usada'],
            [2, 'T10', 'SKU-2', 'A3', 'Cabo', 2],
            [3, 'T10'],  # Pre-numbered blank template row.
        ]})
        batch = create_preview(file, self.user, 1)
        self.assertEqual(len(batch.linhas), 2)
        page = self.client.get(f'/estoque/importar/{batch.id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Código interno: SKU-1', page.text)
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.assertTrue(confirm_preview(batch, self.user)[0])
        part = EstoquePeca.query.order_by(EstoquePeca.id).first()
        self.assertEqual(part.modelos_compativeis, 'AGRAS T10')
        self.assertEqual(part.prateleira_local, 'A2')
        self.assertEqual(part.observacoes, 'Código interno: SKU-1\n01 usada')
        self.assertIsNone(part.numero_serie)
        self.assertEqual(part.equipamentos_compativeis, [])

    def test_repeated_internal_codes_preserve_separate_parts_and_balances(self):
        file = inventory_upload({'T10': [[1, 'T10', 'SAME', 'A2', 'Peça', 16],
                                        [2, 'T10', 'SAME', 'A2', 'Peça', 16]],
                                 'T30': [[1, 'T30', 'SAME', None, 'Outra peça', 7, 'JUNTO COM T10']]})
        rows = read_excel(file)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['dados']['quantidade'] for r in rows], ['16', '16', '7'])
        self.assertTrue(all(not r['erros_arquivo'] for r in rows))
        self.drones[2].modelo = 'AGRAS T30'
        db.session.commit()
        file.stream.seek(0)
        batch = create_preview(file, self.user, 1)
        self.assertTrue(confirm_preview(batch, self.user)[0])
        parts = EstoquePeca.query.order_by(EstoquePeca.id).all()
        self.assertEqual([p.quantidade for p in parts], [16, 16, 7])
        self.assertEqual(parts[2].observacoes, 'Código interno: SAME\nJUNTO COM T10')
        self.assertTrue(all(p.numero_serie is None for p in parts))
        # Keeping separate lines must not allow the entire file to be imported twice.
        file.stream.seek(0)
        second = create_preview(file, self.user, 1)
        self.assertFalse(confirm_preview(second, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 3)

    def test_inventory_never_evaluates_arithmetic_or_assumes_missing_stock(self):
        file = inventory_upload({'T10': [[1, 'T10', 'A', 'A1', 'Peça A', '13+5'],
                                        [2, 'T10', 'B', 'A2', 'Peça B', None],
                                        [3, 'T10', 'C', 'A3', 'Peça C', '=1+1']]})
        batch = create_preview(file, self.user, 1)
        rows, _ = preview_state(batch, self.user)
        self.assertTrue(all(row['erros'] for row in rows))
        self.assertEqual(rows[0]['quantidade'], '13+5')
        self.assertFalse(confirm_preview(batch, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 0)

    def test_edit_pending_quantities_in_preview_then_confirm_preserves_originals(self):
        batch = create_preview(inventory_upload({'T10': [
            [1, 'T10', 'A', 'A1', 'Peça A', '13+5'],
            [2, 'T10', 'B', 'A2', 'Peça B', None],
            [3, 'T10', 'C', 'A3', 'Peça C', '=1+1'],
        ]}), self.user, 1)
        endpoint = f'/estoque/importar/{batch.id}'
        page = self.client.get(endpoint)
        self.assertIn('value="13+5"', page.text)
        self.assertIn('Validar quantidades', page.text)
        response = self.client.post(endpoint, data={'preview_revision': preview_revision(batch),
            'quantidade_0': '18', 'quantidade_1': '0', 'quantidade_2': '2', 'prefeitura_id': '2', 'modelo_peca': 'Tampering'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EstoquePeca.query.count(), 0)
        rows, problems = preview_state(batch, self.user)
        self.assertEqual(problems, [])
        self.assertTrue(all(not row['erros'] for row in rows))
        self.assertEqual([row['quantidade_arquivo'] for row in rows], ['13+5', '', '=1+1'])
        page = self.client.get(endpoint)
        self.assertIn('No arquivo: 13+5', page.text)
        self.assertIn('No arquivo: não informada', page.text)
        self.client.post(endpoint + '/confirmar', data={'preview_revision': preview_revision(batch)})
        parts = EstoquePeca.query.order_by(EstoquePeca.id).all()
        self.assertEqual([part.quantidade for part in parts], [18, 0, 2])
        self.assertEqual([part.modelo_peca for part in parts], ['Peça A', 'Peça B', 'Peça C'])
        self.assertTrue(all(part.prefeitura_id == 1 for part in parts))

    def test_invalid_manual_quantities_still_block_stock_and_other_errors_survive(self):
        batch = create_preview(upload([['=BAD()', None, '=1+1'], ['Peça B', None, 1]]), self.user, 1)
        endpoint = f'/estoque/importar/{batch.id}'
        self.client.post(endpoint, data={'preview_revision': preview_revision(batch), 'quantidade_0': '2', 'quantidade_1': ''})
        rows, _ = preview_state(batch, self.user)
        self.assertTrue(any('fórmula' in error for error in rows[0]['erros']))
        self.assertTrue(rows[1]['erros'])
        self.assertEqual(rows[1]['dados']['quantidade'], '')
        self.client.post(endpoint + '/confirmar')
        self.assertEqual(EstoquePeca.query.count(), 0)
        for quantity in ('13+5', '-1', '1.5', '2147483648'):
            with self.subTest(quantity=quantity):
                self.client.post(endpoint, data={'preview_revision': preview_revision(batch), 'quantidade_1': quantity})
                self.assertTrue(preview_state(batch, self.user)[0][1]['erros'])
                self.assertFalse(confirm_preview(batch, self.user)[0])

    def test_stale_preview_cannot_overwrite_or_confirm_new_quantities(self):
        batch = create_preview(upload([['Peça', None, 1]]), self.user, 1)
        endpoint = f'/estoque/importar/{batch.id}'
        old = preview_revision(batch)
        self.client.post(endpoint, data={'preview_revision': old, 'quantidade_0': '2'})
        current = preview_revision(batch)
        self.assertNotEqual(old, current)
        self.client.post(endpoint, data={'preview_revision': old, 'quantidade_0': '3'})
        self.assertEqual(batch.linhas[0]['dados']['quantidade'], '2')
        self.client.post(endpoint + '/confirmar', data={'preview_revision': old})
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.client.post(endpoint + '/confirmar', data={'preview_revision': current})
        self.assertEqual(EstoquePeca.query.one().quantidade, 2)

    def test_confirmation_with_unsaved_edits_only_revalidates_and_needs_second_confirmation(self):
        batch = create_preview(upload([['Peça', None, 1]]), self.user, 1)
        endpoint = f'/estoque/importar/{batch.id}'
        self.client.post(endpoint + '/confirmar', data={'preview_revision': preview_revision(batch), 'quantidade_0': '5'})
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.assertEqual(batch.linhas[0]['dados']['quantidade'], '5')
        self.client.post(endpoint + '/confirmar', data={'preview_revision': preview_revision(batch), 'quantidade_0': '5'})
        self.assertEqual(EstoquePeca.query.one().quantidade, 5)

    def test_expired_completed_foreign_or_changed_catalog_previews_cannot_be_edited(self):
        batch = create_preview(upload([['Peça', None, 1]]), self.user, 1)
        endpoint = f'/estoque/importar/{batch.id}'
        data = {'preview_revision': preview_revision(batch), 'quantidade_0': '2'}
        self.login('dev')
        self.assertEqual(self.client.post(endpoint, data=data).status_code, 404)
        self.login('manutencao')
        batch.expira_em = now() - timedelta(seconds=1)
        db.session.commit()
        self.client.post(endpoint, data=data)
        self.assertEqual(batch.linhas[0]['dados']['quantidade'], '1')
        batch.expira_em = now() + timedelta(minutes=30)
        db.session.commit()
        self.assertTrue(confirm_preview(batch, self.user)[0])
        self.client.post(endpoint, data=data)
        self.assertEqual(EstoquePeca.query.one().quantidade, 1)
        catalog = create_preview(upload([['Modelo', None, 1, None, None, 'DRONE-0']]), self.user, 1)
        before = preview_revision(catalog)
        self.drones[0].numero_serie = 'CHANGED'
        db.session.commit()
        self.client.post(f'/estoque/importar/{catalog.id}', data={'preview_revision': before, 'quantidade_0': '2'})
        self.assertEqual(catalog.linhas[0]['dados']['quantidade'], '1')

    def test_csrf_is_required_to_edit_preview_quantities(self):
        batch = create_preview(upload([['Peça', None, 1]]), self.user, 1)
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        response = self.client.post(f'/estoque/importar/{batch.id}', data={'preview_revision': preview_revision(batch), 'quantidade_0': '2'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(batch.linhas[0]['dados']['quantidade'], '1')

    def test_download_blank_model_instructions_examples_and_validation(self):
        self.app.root_path = str(ROOT / 'app')
        response = self.client.get('/estoque/importar/modelo')
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.data))
        self.assertEqual(book.sheetnames, ['Peças', 'Instruções', 'Exemplos'])
        self.assertEqual([c.value for c in book['Peças'][5]], HEADERS)
        self.assertEqual(book['Peças']['B6'].number_format, '@')
        self.assertTrue(book['Peças'].data_validations.count)
        with self.assertRaisesRegex(ValueError, 'vazia'):
            read_excel(FileStorage(stream=BytesIO(response.data), filename='modelo.xlsx'))
        book['Peças']['A6'], book['Peças']['C6'] = 'Minha peça', 2
        edited = BytesIO()
        book.save(edited)
        edited.seek(0)
        rows = read_excel(FileStorage(stream=edited, filename='modelo.xlsx'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['numero'], 6)
        self.assertEqual(rows[0]['dados']['modelo_peca'], 'Minha peça')

    def test_preview_then_confirm_shared_stock_and_double_submit(self):
        response = self.post_excel([
            ['Hélice', '00001', 4, 'Armário A', 'AGRAS T10; MATRICE 4E', 'DRONE-0; DRONE-1'],
            ['Conector', None, 6, 'Prateleira B', None, 'BAT-TESTE', 'Reservada', 'Lote piloto'],
        ])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EstoquePeca.query.count(), 0)
        batch = EstoqueImportacao.query.one()
        page = self.client.get(response.location)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Drone 0', page.text)
        self.assertIn('00001', page.text)
        self.assertIn('Todos os dados estão válidos', page.text)
        endpoint = f'/estoque/importar/{batch.id}/confirmar'
        self.assertEqual(self.client.post(endpoint).status_code, 302)
        parts = EstoquePeca.query.order_by(EstoquePeca.id).all()
        self.assertEqual([p.quantidade for p in parts], [4, 6])
        self.assertEqual(parts[0].numero_serie, '00001')
        self.assertEqual({e.id for e in parts[0].equipamentos_compativeis}, {d.id for d in self.drones[:2]})
        self.assertEqual(parts[1].status, 'reservada')
        self.assertIsNotNone(batch.concluida_em)
        self.assertEqual(self.client.post(endpoint).status_code, 302)
        self.assertEqual(EstoquePeca.query.count(), 2)
        self.assertEqual(self.client.get(f'/estoque/importar/{batch.id}').status_code, 302)

    def test_invalid_rows_block_entire_batch_even_posting_directly(self):
        response = self.post_excel([
            ['Válida', None, 3],
            [None, None, -1, None, 'Modelo inexistente', 'DRONE-3'],
            ['Fórmula', None, '=1+1'],
            ['Serial numérico', 123, 1],
            ['Inválida', None, 1.5, None, None, None, 'Status inventado'],
        ])
        self.assertEqual(response.status_code, 302)
        batch = EstoqueImportacao.query.one()
        page = self.client.get(response.location)
        self.assertIn('disabled aria-describedby="import-bloqueada"', page.text)
        for message in ['fórmula', 'texto para preservar', 'modelo da peça', 'inteiro', 'nesta prefeitura', 'Status inválido']:
            self.assertIn(message, page.text)
        self.client.post(f'/estoque/importar/{batch.id}/confirmar')
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.assertIsNone(batch.concluida_em)

    def test_missing_quantity_zero_and_integer_limits(self):
        for quantity in (None, -1, 'NaN', 'Infinity', 2147483648, '3.2'):
            with self.subTest(quantity=quantity):
                batch = create_preview(upload([['Peça', None, quantity]]), self.user, 1)
                self.assertFalse(confirm_preview(batch, self.user)[0])
                self.assertEqual(EstoquePeca.query.count(), 0)
        for quantity in (0, 2147483647):
            batch = create_preview(upload([[f'Peça {quantity}', None, quantity]]), self.user, 1)
            self.assertTrue(confirm_preview(batch, self.user)[0])
        self.assertEqual(sorted(p.quantidade for p in EstoquePeca.query.all()), [0, 2147483647])

    def test_duplicate_rows_serials_and_existing_active_stock(self):
        db.session.add(EstoquePeca(modelo_peca='Existente', numero_serie='EXISTE', quantidade=7, prefeitura_id=1))
        db.session.commit()
        batch = create_preview(upload([
            ['Peça A', 'existe', 1], ['Peça B', 'REP', 1], ['Peça C', 'rep', 2],
            ['Repetida', None, 2], ['Repetida', None, 2],
        ]), self.user, 1)
        rows, _ = preview_state(batch, self.user)
        self.assertTrue(rows[0]['erros'])
        self.assertIn('repetido no arquivo', ' '.join(rows[2]['erros']))
        self.assertIn('Linha repetida', ' '.join(rows[4]['erros']))
        self.assertFalse(confirm_preview(batch, self.user)[0])
        self.assertEqual(EstoquePeca.query.one().quantidade, 7)

    def test_reordered_duplicate_content_without_serials_cannot_import_twice(self):
        rows = [['Hélice', None, 2], ['Cabo', None, 3]]
        first = create_preview(upload(rows), self.user, 1)
        second = create_preview(upload(rows[::-1]), self.user, 1)
        self.assertEqual(first.digest, second.digest)
        self.assertTrue(confirm_preview(first, self.user)[0])
        self.assertFalse(confirm_preview(second, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 2)

    def test_database_receipt_prevents_racing_confirmations_without_serials(self):
        rows = [['Hélice', None, 2], ['Cabo', None, 3]]
        first = create_preview(upload(rows), self.user, 1)
        second = create_preview(upload(rows), self.user, 1)
        stale_state = preview_state(second, self.user)
        self.assertTrue(confirm_preview(first, self.user)[0])
        # Both requests validated before the other committed. The DB receipt must arbitrate.
        with patch('app.modules.estoque.importacao.preview_state', return_value=stale_state):
            self.assertFalse(confirm_preview(second, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 2)
        self.assertIsNone(db.session.get(EstoqueImportacao, second.id).concluida_em)

    def test_expiry_catalog_changes_and_new_serial_conflict_revalidated(self):
        batch = create_preview(upload([['Hélice', None, 2, None, None, 'DRONE-0']]), self.user, 1)
        batch.expira_em = now() - timedelta(seconds=1)
        db.session.commit()
        self.assertIn('expirou', ' '.join(confirm_preview(batch, self.user)[1]))
        fresh = create_preview(upload([['Cabo', 'NOVO', 2], ['Hélice', None, 2]]), self.user, 1)
        db.session.add(EstoquePeca(modelo_peca='Outro cadastro', numero_serie='NOVO', quantidade=8, prefeitura_id=1))
        db.session.commit()
        self.assertFalse(confirm_preview(fresh, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 1)
        catalog = create_preview(upload([['Peça com modelo', None, 2, None, 'MATRICE 4E']]), self.user, 1)
        for drone in (self.drones[0], self.drones[2]):
            drone.modelo = 'Novo modelo'
        db.session.commit()
        self.assertFalse(confirm_preview(catalog, self.user)[0])

    def test_ambiguous_or_foreign_equipment_and_unknown_columns(self):
        self.drones[1].numero_serie = 'drone-0'
        db.session.commit()
        batch = create_preview(upload([['Hélice', None, 1, None, None, 'DRONE-0; DRONE-3']]), self.user, 1)
        rows, _ = preview_state(batch, self.user)
        self.assertEqual(sum('ambígua' in error for error in rows[0]['erros']), 2)
        self.assertFalse(confirm_preview(batch, self.user)[0])
        response = self.client.post('/estoque/importar', data={'prefeitura_id': 1, 'arquivo': (excel([['A', 1, 'ignored']], ['Peça', 'Quantidade', 'Outra coluna']), 'a.xlsx')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('colunas desconhecidas', response.text)
        unmapped = read_excel(FileStorage(stream=excel([['A', 1, 'ignored']], ['Peça', 'Quantidade']), filename='a.xlsx'))
        self.assertTrue(unmapped[0]['erros_arquivo'])

    def test_wrong_owner_tenant_and_revoked_permission(self):
        batch = create_preview(upload([['Hélice', None, 2]]), self.user, 1)
        self.login('dev')
        self.assertEqual(self.client.get(f'/estoque/importar/{batch.id}').status_code, 404)
        self.assertEqual(self.client.post(f'/estoque/importar/{batch.id}/confirmar').status_code, 404)
        self.login('manutencao')
        self.assertEqual(self.post_excel([['Hélice', None, 2]], prefeitura_id='2').status_code, 403)
        self.user.prefeitura_id = 2
        db.session.commit()
        self.assertEqual(self.client.post(f'/estoque/importar/{batch.id}/confirmar').status_code, 404)
        self.user.prefeitura_id = 1
        self.user.tipo_usuario = 'piloto'
        db.session.commit()
        g.pop('_central_ti_permissions', None)
        self.assertEqual(self.client.post(f'/estoque/importar/{batch.id}/confirmar').status_code, 403)
        self.assertEqual(EstoquePeca.query.count(), 0)

    def test_csrf_protects_upload_and_confirmation(self):
        self.app.config['CSRF_PROTECTION_ENABLED'] = True
        page = self.client.get('/estoque/importar')
        self.assertIn('name="_csrf_token"', page.text)
        self.assertEqual(self.post_excel([['Hélice', None, 2]]).status_code, 403)
        with self.client.session_transaction() as session:
            token = session['_ija_csrf']
        self.assertEqual(self.post_excel([['Hélice', None, 2]], _csrf_token=token).status_code, 302)
        batch = EstoqueImportacao.query.one()
        self.assertEqual(self.client.post(f'/estoque/importar/{batch.id}/confirmar').status_code, 403)
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.assertEqual(self.client.post(f'/estoque/importar/{batch.id}/confirmar', data={'_csrf_token': token}).status_code, 302)
        self.assertEqual(EstoquePeca.query.count(), 1)

    def test_database_failure_rolls_back_all_items_and_receipt(self):
        batch = create_preview(upload([['Cabo', None, 2], ['Hélice', None, 3]]), self.user, 1)
        from app.modules.estoque.service import _apply_peca
        calls = 0
        def fail_on_second(item, cleaned, tenant):
            nonlocal calls
            calls += 1
            if calls == 2:
                db.session.flush()  # First piece has reached the DB, but must still roll back.
                raise IntegrityError('simulated concurrent conflict', {}, Exception('conflict'))
            _apply_peca(item, cleaned, tenant)
        with patch('app.modules.estoque.importacao._apply_peca', side_effect=fail_on_second):
            self.assertFalse(confirm_preview(batch, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 0)
        self.assertIsNone(db.session.get(EstoqueImportacao, batch.id).concluida_em)

    def test_invalid_formats_limits_and_empty_file_create_no_preview(self):
        for content, filename in [(b'invalid', 'a.xlsx'), (b'data', 'a.csv'), (b'x' * (5 * 1024 * 1024 + 1), 'a.xlsx')]:
            with self.subTest(filename=filename, size=len(content)):
                response = self.client.post('/estoque/importar', data={'prefeitura_id': 1, 'arquivo': (BytesIO(content), filename)})
                self.assertEqual(response.status_code, 400)
        for stream in (excel([]), excel([['A', 1]], ['Peça', 'Quantidade'], 'Errada'), excel([['A', 1]] * 1001, ['Peça', 'Quantidade'])):
            response = self.client.post('/estoque/importar', data={'prefeitura_id': 1, 'arquivo': (stream, 'a.xlsx')})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(EstoqueImportacao.query.count(), 0)
        self.assertEqual(EstoquePeca.query.count(), 0)

    def test_archiving_preserves_os_history_and_allows_reuse_of_serial(self):
        batch = create_preview(upload([['Hélice', 'SERIAL', 4, None, None, 'DRONE-0']]), self.user, 1)
        self.assertTrue(confirm_preview(batch, self.user)[0])
        item = EstoquePeca.query.one()
        send_drone_to_manutencao(self.drones[0], user=self.user)
        from werkzeug.datastructures import MultiDict
        _, errors = registrar_pecas_usadas_manutencao(self.drones[0], MultiDict([('peca_id', str(item.id))]), user=self.user)
        self.assertFalse(errors)
        item.arquivada_em = now()
        db.session.commit()
        self.assertEqual(list_pecas(user=self.user), [])
        self.assertEqual(ManutencaoPecaUso.query.one().peca_id, item.id)
        self.assertEqual(self.client.get(f'/estoque/{item.id}/editar').status_code, 404)
        new = create_preview(upload([['Hélice nova', 'SERIAL', 2]]), self.user, 1)
        self.assertTrue(confirm_preview(new, self.user)[0])
        self.assertEqual(EstoquePeca.query.count(), 2)
        self.assertEqual(len(list_pecas(user=self.user)), 1)


class ImportacaoMigrationTests(unittest.TestCase):
    def test_migration_preserves_existing_stock_in_disposable_database(self):
        path = ROOT / 'migrations/versions/e64b1d9f203a_estoque_importacoes_e_arquivo.py'
        spec = importlib.util.spec_from_file_location('import_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine('sqlite:///:memory:')
        try:
            with engine.begin() as conn:
                conn.execute(sa.text('CREATE TABLE prefeituras (id INTEGER PRIMARY KEY)'))
                conn.execute(sa.text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
                conn.execute(sa.text('CREATE TABLE estoque_pecas (id INTEGER PRIMARY KEY, numero_serie VARCHAR(100), quantidade INTEGER)'))
                conn.execute(sa.text('CREATE UNIQUE INDEX ix_estoque_pecas_numero_serie ON estoque_pecas(numero_serie)'))
                conn.execute(sa.text("INSERT INTO estoque_pecas VALUES (1,'SERIE',8)"))
                with Operations.context(MigrationContext.configure(conn)):
                    migration.upgrade()
                self.assertEqual(conn.execute(sa.text('SELECT id,numero_serie,quantidade,arquivada_em FROM estoque_pecas')).one(), (1, 'SERIE', 8, None))
                conn.execute(sa.text("UPDATE estoque_pecas SET arquivada_em = '2026-11-26' WHERE id=1"))
                conn.execute(sa.text("INSERT INTO estoque_pecas VALUES (2,'SERIE',4,NULL)"))
                with Operations.context(MigrationContext.configure(conn)):
                    with self.assertRaises(RuntimeError):
                        migration.downgrade()
                self.assertIn('estoque_importacoes', sa.inspect(conn).get_table_names())
                conn.execute(sa.text('DELETE FROM estoque_pecas WHERE id=2'))
                with Operations.context(MigrationContext.configure(conn)):
                    migration.downgrade()
                self.assertNotIn('estoque_importacoes', sa.inspect(conn).get_table_names())
                self.assertEqual(conn.execute(sa.text('SELECT quantidade FROM estoque_pecas')).scalar(), 8)
        finally:
            engine.dispose()
