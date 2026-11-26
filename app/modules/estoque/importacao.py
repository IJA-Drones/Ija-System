"""Deterministic Excel preview and atomic inventory import. No stock writes on upload."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
import re
import unicodedata
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from flask import abort
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import EstoqueImportacao, EstoquePeca, Prefeitura
from app.modules.estoque.service import _apply_peca, list_equipamentos_for_estoque, validate_peca_form
from app.shared.access import can_access_prefeitura

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
FIELDS = {
    'modelo_peca': ('Peça', 'Modelo da peça', 'Modelo peça'),
    'numero_serie': ('Número de série', 'Nº de série'),
    'quantidade': ('Quantidade',),
    'prateleira_local': ('Prateleira/Local', 'Localização física', 'Local'),
    'modelos_compativeis': ('Modelos compatíveis',),
    'equipamentos': ('Equipamentos compatíveis (nº de série)', 'Equipamentos compatíveis'),
    'status': ('Status',),
    'observacoes': ('Observações',),
}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower())


HEADERS = {normalized(label): field for field, labels in FIELDS.items() for label in labels}
STATUS = {normalized(label): code for code, labels in {
    'disponivel_manutencao': ['Disponível', 'Disponível para manutenção', 'disponivel_manutencao'],
    'reservada': ['Reservada'], 'baixada': ['Baixada'], 'indisponivel': ['Indisponível'],
}.items() for label in labels}

INVENTORY_SHEETS = {'T10', 'T20', 'T30', 'T40'}
INVENTORY_HEADERS = ['ITEM', 'MODELO', 'CÓDIGO INTERNO', 'LOCALIZAÇÃO FÍSICA',
                     'DESCRIÇÃO DA PEÇA', 'QUANTIDADE', 'OBSERVAÇÕES']


def _read_inventory(workbook):
    """Read Fernando's inventory without guessing balances or merging repeated SKUs."""
    unknown = set(workbook.sheetnames) - INVENTORY_SHEETS - {'RESUMO GERAL'}
    if unknown:
        raise ValueError('Abas não reconhecidas no inventário: ' + ', '.join(sorted(unknown)) + '. Use o modelo padrão ou as abas T10, T20, T30 e T40.')
    rows = []
    for sheet in workbook:
        if sheet.title == 'RESUMO GERAL':
            continue  # This is a derived summary, never another source of stock.
        if (sheet.max_row or 0) > 10020 or (sheet.max_column or 0) > 64:
            raise ValueError('A planilha tem linhas ou colunas em excesso. Envie até 1.000 peças.')
        header = None
        for number, cells in enumerate(sheet.iter_rows(max_row=20, max_col=64), 1):
            if [normalized(c.value) for c in cells[:7]] == [normalized(h) for h in INVENTORY_HEADERS]:
                if any(c.value not in (None, '') for c in cells[7:]):
                    raise ValueError(f'Aba {sheet.title}: existem colunas desconhecidas no cabeçalho.')
                header = number
                break
        if header is None:
            raise ValueError(f'Aba {sheet.title}: cabeçalho do inventário não reconhecido.')
        for number, cells in enumerate(sheet.iter_rows(min_row=header + 1, max_row=10020, max_col=64), header + 1):
            # Numbered template lines with only ITEM/MODELO are placeholders, not parts.
            if all(c.value is None or (isinstance(c.value, str) and not c.value.strip()) for c in cells[2:]):
                continue
            if len(rows) >= MAX_ROWS:
                raise ValueError('Importe no máximo 1.000 peças por arquivo, somando todas as abas.')
            errors, values = [], []
            for cell, label in zip(cells[:7], INVENTORY_HEADERS):
                value = cell.value
                if cell.data_type == 'f' or (isinstance(value, str) and value.lstrip().startswith('=')):
                    errors.append(f'{label}: substitua a fórmula pelo valor da célula.')
                if isinstance(value, (datetime, bool)):
                    errors.append(f'{label}: formato inválido.')
                text = '' if value is None else str(value).strip()
                if len(text) > 5000:
                    errors.append(f'{label}: o texto ultrapassa 5.000 caracteres.')
                values.append(text[:5000])
            if any(c.value not in (None, '') for c in cells[7:]):
                errors.append('Existem dados fora das sete colunas do inventário.')
            _, model, code, location, name, quantity, notes = values
            if not model:
                errors.append('MODELO: informe o modelo compatível; o nome da aba não substitui esse campo.')
            if not code:
                errors.append('CÓDIGO INTERNO: informe o código da peça.')
            if len(code) > 100:
                errors.append('CÓDIGO INTERNO: use até 100 caracteres.')
            # The current stock form has no SKU column. Preserve the source code explicitly
            # in observations instead of misrepresenting it as a unique equipment serial.
            observations = '\n'.join(v for v in (f'Código interno: {code}' if code else '', notes) if v)
            row = {'numero': number, 'aba': sheet.title, 'codigo_interno': code,
                   'dados': {'modelo_peca': name, 'numero_serie': '', 'quantidade': quantity,
                             'prateleira_local': location, 'modelos_compativeis': model,
                             'equipamentos': '', 'status': '', 'observacoes': observations},
                   'erros_arquivo': errors}
            rows.append(row)
    return rows


def read_excel(upload):
    if upload is None or not (upload.filename or '').lower().endswith(('.xlsx', '.xlsm')):
        raise ValueError('Selecione um arquivo Excel .xlsx ou .xlsm. Macros não são executadas.')
    content = upload.stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('O arquivo deve ter no máximo 5 MB.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            if len(archive.infolist()) > 1500 or sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                raise ValueError('A estrutura do arquivo é muito grande. Envie uma planilha menor.')
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False, keep_vba=False)
    except (BadZipFile, OSError, KeyError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(('A estrutura', 'Envie um')):
            raise
        raise ValueError('Não foi possível ler o Excel. Salve novamente como .xlsx e tente outra vez.') from exc
    try:
        if 'Peças' not in workbook.sheetnames and INVENTORY_SHEETS.intersection(workbook.sheetnames):
            rows = _read_inventory(workbook)
            if not rows:
                raise ValueError('As abas do inventário estão vazias. Preencha pelo menos uma peça.')
            if len(json.dumps(rows, ensure_ascii=False).encode()) > 2 * 1024 * 1024:
                raise ValueError('Os dados são muito extensos para uma prévia. Divida o arquivo.')
            return rows
        if 'Peças' not in workbook.sheetnames:
            raise ValueError('A aba Peças não foi encontrada. Use o modelo padrão e mantenha o nome dessa aba.')
        sheet = workbook['Peças']
        if (sheet.max_row or 0) > 10020 or (sheet.max_column or 0) > 64:
            raise ValueError('A planilha tem linhas ou colunas em excesso. Use o modelo e envie até 1.000 peças.')
        header_row = None
        columns = {}
        for row_number, row in enumerate(sheet.iter_rows(min_row=1, max_row=min(sheet.max_row or 0, 20)), 1):
            candidate = {i: HEADERS.get(normalized(cell.value)) for i, cell in enumerate(row) if cell.value is not None}
            if {'modelo_peca', 'quantidade'} <= set(candidate.values()):
                if len([v for v in candidate.values() if v]) != len(set(v for v in candidate.values() if v)):
                    raise ValueError('Existem colunas repetidas no cabeçalho. Use uma coluna para cada campo.')
                if any(value is None for value in candidate.values()):
                    raise ValueError('O cabeçalho contém colunas desconhecidas. Use as colunas do modelo padrão.')
                columns = candidate
                header_row = row_number
                break
        if header_row is None:
            raise ValueError('Não encontrei as colunas obrigatórias Peça e Quantidade na aba Peças.')
        rows = []
        for row_number, cells in enumerate(sheet.iter_rows(min_row=header_row + 1), header_row + 1):
            if all(cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()) for cell in cells):
                continue
            if len(rows) >= MAX_ROWS:
                raise ValueError('Importe no máximo 1.000 peças por arquivo.')
            data = {}
            errors = []
            if any(cell.value not in (None, '') for i, cell in enumerate(cells) if i not in columns):
                errors.append('Existem dados em uma coluna sem cabeçalho. Use apenas as colunas do modelo.')
            for index, field in columns.items():
                cell = cells[index]
                value = cell.value
                if cell.data_type == 'f' or (isinstance(value, str) and value.lstrip().startswith('=')):
                    errors.append(f'{FIELDS[field][0]}: substitua a fórmula pelo valor da célula.')
                if field == 'numero_serie' and value is not None and not isinstance(value, str):
                    errors.append('Número de série: formate a célula como texto para preservar o identificador.')
                if isinstance(value, (datetime, bool)):
                    errors.append(f'{FIELDS[field][0]}: formato inválido. Use texto ou um número inteiro na quantidade.')
                value = '' if value is None else str(value).strip()
                if len(value) > 5000:
                    errors.append(f'{FIELDS[field][0]}: o texto ultrapassa 5.000 caracteres.')
                    value = value[:5000]
                data[field] = value
            rows.append({'numero': row_number, 'dados': data, 'erros_arquivo': errors})
        if not rows:
            raise ValueError('A aba Peças está vazia. Preencha pelo menos uma linha antes de enviar.')
        if len(json.dumps(rows, ensure_ascii=False).encode()) > 2 * 1024 * 1024:
            raise ValueError('Os dados são muito extensos para uma prévia. Divida a importação em arquivos menores.')
        return rows
    finally:
        workbook.close()


def validate_rows(rows, user, prefeitura_id):
    if not can_access_prefeitura(user, prefeitura_id) or db.session.get(Prefeitura, prefeitura_id) is None:
        abort(403)
    equipment = [e for e in list_equipamentos_for_estoque(user) if e.prefeitura_id == prefeitura_id]
    model_names = {(e.modelo or '').strip().casefold(): (e.modelo or '').strip() for e in equipment if e.modelo}
    by_serial = {}
    for item in equipment:
        if item.numero_serie:
            by_serial.setdefault(item.numero_serie.strip().casefold(), []).append(item)
    used_serials = {str(s).casefold() for s in db.session.scalars(select(EstoquePeca.numero_serie).where(
        EstoquePeca.numero_serie.isnot(None), EstoquePeca.arquivada_em.is_(None)))}
    seen_serials, seen_rows = {}, {}
    results, canonical = [], []
    for source in rows:
        raw = source['dados']
        errors = list(source.get('erros_arquivo', []))
        models = list(dict.fromkeys(m.strip() for m in raw.get('modelos_compativeis', '').split(';') if m.strip()))
        if source.get('aba') in INVENTORY_SHEETS:
            # Explicit Agras shorthand only, and only when the tenant catalog has one match.
            def canonical_model(model):
                if model.casefold() in model_names:
                    return model_names[model.casefold()]
                matches = [name for key, name in model_names.items()
                           if re.sub(r'^(?:dji\s+)?agras\s+', '', key) == model.casefold()]
                return matches[0] if len(matches) == 1 else model
            models = [canonical_model(model) for model in models]
        serials = list(dict.fromkeys(s.strip() for s in raw.get('equipamentos', '').split(';') if s.strip()))
        resolved = []
        for serial in serials:
            matches = by_serial.get(serial.casefold(), [])
            if len(matches) != 1:
                errors.append(f'Equipamento {serial}: série não encontrada ou ambígua nesta prefeitura.')
            else:
                resolved.append(matches[0])
        quantity = raw.get('quantidade', '')
        try:
            number = Decimal(quantity)
            if not number.is_finite() or number != number.to_integral_value() or not 0 <= number <= 2147483647:
                raise InvalidOperation
            quantity = str(int(number))
        except (InvalidOperation, ValueError):
            errors.append('Quantidade: informe um número inteiro entre 0 e 2.147.483.647.')
            quantity = 'inválida'
        status = STATUS.get(normalized(raw.get('status', '')), 'disponivel_manutencao' if not raw.get('status') else 'inválido')
        form = MultiDict({key: raw.get(key, '') for key in ('modelo_peca', 'numero_serie', 'prateleira_local', 'observacoes')})
        form.update({'quantidade': quantity, 'status': status, 'prefeitura_id': str(prefeitura_id), 'compatibilidade_multipla': '1'})
        form.setlist('modelos_compativeis', models)
        form.setlist('equipamento_ids', [str(e.id) for e in resolved])
        presented, cleaned, validation = validate_peca_form(form, user=user, equipamentos_disponiveis=equipment, series_em_uso=used_serials)
        if quantity == 'inválida':
            validation.pop('quantidade', None)  # The Excel-specific message above already explains the accepted range.
        errors.extend(f'{FIELDS[field][0] if field in FIELDS else "Compatibilidade"}: {message}'
                      for field, message in validation.items())
        if len(raw.get('observacoes', '')) > 5000:
            errors.append('Observações: use até 5.000 caracteres.')
        own_serial = raw.get('numero_serie', '').casefold()
        if own_serial:
            if own_serial in seen_serials:
                errors.append(f'Número de série repetido no arquivo (linha {seen_serials[own_serial]}).')
            seen_serials.setdefault(own_serial, source['numero'])
        fingerprint = dict(modelo_peca=presented['modelo_peca'], numero_serie=own_serial,
                           quantidade=quantity, prateleira_local=presented['prateleira_local'],
                           modelos=sorted(m.casefold() for m in presented['modelos_compativeis']),
                           equipamentos=sorted(e.id for e in resolved), status=status, observacoes=presented['observacoes'])
        key = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False)
        # The owner confirmed that each inventory line represents a separate part,
        # including repeated codes and matching descriptions. Preserve every line.
        if key in seen_rows and source.get('aba') not in INVENTORY_SHEETS:
            errors.append(f'Linha repetida no arquivo (igual à linha {seen_rows[key]}).')
        seen_rows.setdefault(key, source['numero'])
        canonical.append(key)
        results.append(dict(numero=source['numero'], aba=source.get('aba', ''), codigo_interno=source.get('codigo_interno', ''),
                            quantidade_arquivo=source.get('quantidade_arquivo', raw.get('quantidade', '')),
                            dados=raw, modelos=presented['modelos_compativeis'],
                            equipamentos=resolved, status=status, quantidade=raw.get('quantidade', '') if quantity == 'inválida' else int(quantity),
                            erros=list(dict.fromkeys(errors)), cleaned=cleaned))
    digest = sha256('\n'.join(sorted(canonical)).encode()).hexdigest()
    return results, digest


def create_preview(upload, user, prefeitura_id):
    rows = read_excel(upload)
    _, digest = validate_rows(rows, user, prefeitura_id)
    batch = EstoqueImportacao(id=str(uuid4()), prefeitura_id=prefeitura_id, usuario_id=user.id,
                             arquivo_nome=(upload.filename or 'pecas.xlsx').replace('\\', '/').rsplit('/', 1)[-1][:255],
                             digest=digest, linhas=rows, criado_em=now(), expira_em=now() + timedelta(minutes=30))
    db.session.add(batch)
    db.session.commit()
    return batch


def get_preview(batch_id, user, lock=False):
    query = select(EstoqueImportacao).where(EstoqueImportacao.id == batch_id, EstoqueImportacao.usuario_id == user.id)
    if lock:
        query = query.with_for_update()
    batch = db.session.scalar(query.execution_options(populate_existing=True))
    if batch is None or not can_access_prefeitura(user, batch.prefeitura_id):
        abort(404)
    return batch


def preview_state(batch, user):
    rows, digest = validate_rows(batch.linhas, user, batch.prefeitura_id)
    problems = []
    if not batch.concluida_em:
        if now() >= batch.expira_em:
            problems.append('Esta prévia expirou. Envie a planilha novamente para revisar os dados atuais.')
        if digest != batch.digest:
            problems.append('Os cadastros de compatibilidade mudaram. Envie a planilha novamente antes de confirmar.')
        if db.session.scalar(select(EstoqueImportacao.id).where(
            EstoqueImportacao.prefeitura_id == batch.prefeitura_id, EstoqueImportacao.digest == batch.digest,
            EstoqueImportacao.concluida_em.isnot(None), EstoqueImportacao.id != batch.id)):
            problems.append('Este mesmo conteúdo já foi importado para esta prefeitura.')
    return rows, problems


def confirm_preview(batch, user):
    if batch.concluida_em:
        return False, ['Esta importação já foi concluída. Nenhuma peça foi cadastrada novamente.']
    rows, problems = preview_state(batch, user)
    if problems or any(row['erros'] for row in rows):
        return False, problems or ['Corrija os erros e envie a planilha novamente. Nenhuma peça foi cadastrada.']
    try:
        for row in rows:
            item = EstoquePeca()
            _apply_peca(item, row['cleaned'], batch.prefeitura_id)
            db.session.add(item)
        batch.concluida_em = now()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False, ['O estoque mudou ou este lote já foi importado. Atualize a prévia antes de continuar. Nenhuma peça deste envio foi salva.']
    return True, []


def preview_revision(batch):
    return sha256(json.dumps(batch.linhas, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def update_preview_quantities(batch, user, form):
    """Save explicit edits to staging only, preserving original quantities for review."""
    if batch.concluida_em:
        return ['Esta importação já foi concluída. Nenhuma quantidade foi alterada.']
    _, problems = preview_state(batch, user)
    if problems:
        return problems
    if form.get('preview_revision') != preview_revision(batch):
        return ['A prévia mudou em outra aba. Recarregue a página e confira as quantidades antes de editar.']
    sources = deepcopy(batch.linhas)
    for index, source in enumerate(sources):
        key = f'quantidade_{index}'
        if key not in form:
            continue
        value = form.get(key, '').strip()
        if value == source['dados'].get('quantidade', ''):
            continue
        source.setdefault('quantidade_arquivo', source['dados'].get('quantidade', ''))
        source['dados']['quantidade'] = value[:100]
        # Replace errors from the quantity cell only. Errors in other columns remain.
        source['erros_arquivo'] = [error for error in source.get('erros_arquivo', [])
                                  if normalized(error.split(':', 1)[0]) != 'quantidade']
    _, digest = validate_rows(sources, user, batch.prefeitura_id)
    batch.linhas = sources
    batch.digest = digest
    db.session.commit()
    return []
