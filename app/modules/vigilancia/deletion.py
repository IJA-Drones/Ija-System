"""Exclusões explícitas, municipais e atômicas; CSVs originais continuam preservados."""

import hashlib
import hmac
import json
import time

import sqlalchemy as sa

from app.models import AuditoriaUsuario
from .field_models import CampoInspecao, CampoImovel, CampoLevantamento, CampoLote, CampoLoteInspecao
from .field_store import FieldStore, FieldConflict
from .planning import scoped
from .planning_models import CampoPlano, CampoPlanoEstrato, CampoPlanoQuarteirao, CampoPlanoVisita, CampoQuarteirao


class DeletionStore(FieldStore):
    def _snapshot(self, conn, prefeitura, demo, kind, code, origin=''):
        if kind not in {'levantamento', 'visita', 'quarteirao'}:
            raise FieldConflict('Selecione um levantamento, uma visita ou um quarteirão.')
        target_table = {'levantamento': CampoPlano, 'visita': CampoInspecao, 'quarteirao': CampoQuarteirao}[kind].__table__
        where = [*scoped(target_table, prefeitura, demo), target_table.c.code == code]
        if kind == 'visita':
            if origin not in {'LIRAA', 'FOCAL'}:
                raise FieldConflict('Selecione a atividade da visita.')
            where.append(target_table.c.origin == origin)
        target = conn.execute(sa.select(target_table).where(*where)).mappings().first()
        if target is None:
            raise FieldConflict('Registro indisponível nesta prefeitura e origem de dados. Reabra a listagem.')
        inspections, blocks = CampoInspecao.__table__, CampoPlanoQuarteirao.__table__
        records, references = [], []
        if kind == 'levantamento':
            records = list(conn.execute(sa.select(inspections).where(*scoped(inspections, prefeitura, demo),
                inspections.c.survey_code == code)).mappings())
            references = list(conn.execute(sa.select(blocks).where(*scoped(blocks, prefeitura, demo),
                blocks.c.plano == code).order_by(blocks.c.quarteirao)).mappings())
        elif kind == 'visita':
            records = [target]
        else:
            references = list(conn.execute(sa.select(blocks).where(*scoped(blocks, prefeitura, demo),
                blocks.c.quarteirao == code).order_by(blocks.c.plano)).mappings())
        records = sorted((dict(row) for row in records), key=lambda row: (row['origin'], row['code']))
        changes = []
        if kind != 'quarteirao':
            lots = CampoLote.__table__
            for lot in conn.execute(sa.select(lots.c.id, lots.c.report).where(
                lots.c.prefeitura == prefeitura, lots.c.demo == demo).order_by(lots.c.id)).mappings():
                matches = [row for row in lot['report'].get('registros', []) if (
                    row.get('levantamento_codigo') == code if kind == 'levantamento' else
                    (row.get('origem'), row.get('inspecao_codigo')) == (origin, code))]
                if matches:
                    changes.append(dict(id=lot['id'], report=lot['report'], count=len(matches)))
        evidence = dict(target=dict(target), records=records, references=[dict(row) for row in references], lots=changes)
        revision = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        return dict(tipo=kind, codigo=code, origem=origin, titulo=target.get('titulo', code),
                    visitas=len(records), quarteiroes=len(references), lotes=len(changes), revisao=revision,
                    bloqueio='Este quarteirão está vinculado a levantamentos. Remova os vínculos nas amostras antes de excluí-lo.'
                        if kind == 'quarteirao' and references else None,
                    _records=records, _lots=changes)

    def preview(self, prefeitura, demo, kind, code, origin=''):
        with self.connection() as conn:
            return self._snapshot(conn, prefeitura, demo, kind, code, origin)

    def delete(self, prefeitura, demo, kind, code, origin, revision, audit):
        with self.connection(write_prefeitura=prefeitura) as conn:
            item = self._snapshot(conn, prefeitura, demo, kind, code, origin)
            if not hmac.compare_digest(item['revisao'], revision):
                raise FieldConflict('Os dados mudaram desde a revisão. Reabra a confirmação antes de excluir.')
            if item['bloqueio']:
                raise FieldConflict(item['bloqueio'])
            now = time.time()
            for lot in item['_lots']:
                report = dict(lot['report'])
                report['exclusoes'] = [*report.get('exclusoes', []), dict(tipo=kind, codigo=code,
                    origem=origin, registros=lot['count'], autor=audit['usuario_id'], instante=now)]
                conn.execute(CampoLote.__table__.update().where(CampoLote.id == lot['id']).values(report=report))
            if item['_records']:
                inspections = CampoInspecao.__table__
                conditions = [*scoped(inspections, prefeitura, demo)]
                conditions += [inspections.c.survey_code == code] if kind == 'levantamento' else [
                    inspections.c.origin == origin, inspections.c.code == code]
                keys = sa.select(inspections.c.origin, inspections.c.code).where(*conditions)
                for model in (CampoPlanoVisita, CampoLoteInspecao):
                    table = model.__table__
                    conn.execute(table.delete().where(*scoped(table, prefeitura, demo),
                        sa.tuple_(table.c.origin, table.c.code).in_(keys)))
                conn.execute(inspections.delete().where(*conditions))
                properties = CampoImovel.__table__
                unused = {row['property_code'] for row in item['_records']}
                conn.execute(properties.delete().where(*scoped(properties, prefeitura, demo),
                    properties.c.code.in_(unused), ~sa.exists(sa.select(1).where(
                        *scoped(inspections, prefeitura, demo), inspections.c.property_code == properties.c.code))))
            if kind == 'levantamento':
                for model, field in ((CampoPlanoVisita, 'plano'), (CampoPlanoQuarteirao, 'plano'),
                                     (CampoPlanoEstrato, 'plano'), (CampoPlano, 'code'), (CampoLevantamento, 'code')):
                    table = model.__table__
                    conn.execute(table.delete().where(*scoped(table, prefeitura, demo), table.c[field] == code))
            elif kind == 'quarteirao':
                table = CampoQuarteirao.__table__
                conn.execute(table.delete().where(*scoped(table, prefeitura, demo), table.c.code == code))
            conn.execute(AuditoriaUsuario.__table__.insert().values({**audit, 'prefeitura_id': prefeitura,
                'objeto_tipo': 'vigilancia.' + kind, 'objeto_id': code, 'status_code': 303,
                'detalhes': dict(demo=demo, origem=origin, visitas=item['visitas'],
                                quarteiroes=item['quarteiroes'], lotes_afetados=item['lotes'])}))
            return item
