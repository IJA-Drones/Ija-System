"""Carga de campo no banco do IJA; estrutura instalada por migração Alembic."""

import csv
import io
import logging
import time
import uuid
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from .field_models import CampoLote, CampoImovel, CampoLevantamento, CampoInspecao, CampoLoteInspecao, CampoOsReferencia
from .service import CSV_COLUMNS, MAX_ROWS, PreviewValidationError, preview_csv
from .domain import DEPOSIT_COLUMNS


logger = logging.getLogger(__name__)


class FieldStoreError(ValueError):
    pass


class FieldConflict(FieldStoreError):
    pass


def _csv(records):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    columns = (*CSV_COLUMNS, *DEPOSIT_COLUMNS) if any(name in row for row in records for name in DEPOSIT_COLUMNS) else CSV_COLUMNS
    writer.writerow(columns)
    for record in records:
        writer.writerow([record.get(key) if record.get(key) is not None else "" for key in columns])
    return stream.getvalue().encode("utf-8")


class FieldStore:
    def __init__(self, engine=None):
        self.engine = engine if engine is not None else db.engine

    @contextmanager
    def connection(self, *, write_prefeitura=None):
        started = time.perf_counter()
        connected = None
        try:
            with self.engine.connect() as conn, conn.begin():
                connected = time.perf_counter()
                if write_prefeitura is not None:
                    if self.engine.dialect.name == "postgresql":
                        # Serializa os lotes da prefeitura entre workers, sem
                        # bloquear linhas de tabelas operacionais.
                        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
                        conn.execute(sa.select(sa.func.pg_advisory_xact_lock(1229603073, write_prefeitura)))
                    elif self.engine.dialect.name == "sqlite":
                        # Somente desenvolvimento/testes descartáveis.
                        conn.exec_driver_sql("BEGIN IMMEDIATE")
                    else:
                        raise FieldStoreError("O banco configurado não suporta a carga de campo.")
                yield conn
        except SQLAlchemyError as exc:
            # Registre apenas o tipo/código: a exceção completa pode conter CSV,
            # parâmetros SQL ou informações da conexão.
            logger.warning("LIRAa: falha no banco; tipo=%s sqlstate=%s",
                           type(exc).__name__, getattr(getattr(exc, "orig", None), "pgcode", None))
            raise FieldStoreError("Não foi possível acessar as tabelas de vigilância. Confira a migração e a conexão do banco; nenhuma carga foi confirmada nesta tentativa.") from exc
        finally:
            finished = time.perf_counter()
            if finished - started >= 3:
                logger.warning("LIRAa: acesso lento ao banco; conexao_ms=%.0f operacao_ms=%.0f",
                               ((connected or finished) - started) * 1000,
                               (finished - (connected or finished)) * 1000)

    @staticmethod
    def _public_columns(table):
        return [column for column in table.c if column.name != "original"]

    @staticmethod
    def _public(row):
        if row is None:
            return None
        result = dict(row)
        result.pop("original", None)
        return result

    @staticmethod
    def _check_os(conn, os_id, prefeitura):
        from app.models import Solicitacao
        table = Solicitacao.__table__
        if conn.scalar(sa.select(table.c.id).where(table.c.id == os_id, table.c.prefeitura_id == prefeitura)) is None:
            raise FieldConflict("A OS não pertence à prefeitura do registro ou não está mais disponível.")

    def prepare(self, content, *, prefeitura, actor, source, filename, demo, os_declaration=None, plan_reference=None):
        source = source.strip()
        if not source or len(source) > 120 or any(ord(c) < 32 for c in source):
            raise FieldStoreError("Informe uma fonte de até 120 caracteres.")
        report = preview_csv(content, prefeitura_id=prefeitura)
        if os_declaration:
            if demo or len(report["registros"]) != 1:
                raise FieldConflict("O vínculo com OS exige uma visita individual com dados autorizados.")
            report["vinculo_os"] = dict(os_declaration)
        if plan_reference:
            report["planejamento"] = dict(plan_reference)
        status = "VALIDADO" if report["status"] == "VALIDADO" and report["registros"] else "REJEITADO"
        table = CampoLote.__table__
        with self.connection(write_prefeitura=prefeitura) as conn:
            from .planning import validate_visits
            if status == "VALIDADO":
                validate_visits(conn, report["registros"], prefeitura, demo, plan_reference, actor)
            if os_declaration:
                self._check_os(conn, os_declaration["id"], prefeitura)
            previous = conn.execute(sa.select(*self._public_columns(table)).where(
                table.c.prefeitura == prefeitura, table.c.demo == bool(demo), table.c.actor == actor,
                table.c.sha256 == report["arquivo_sha256"], table.c.source == source)).mappings().first()
            if previous:
                if previous["report"].get("vinculo_os") != report.get("vinculo_os"):
                    raise FieldConflict("Esta visita já foi preparada com outra referência ou responsável. Revise o registro existente.")
                if previous["report"].get("planejamento") != plan_reference:
                    raise FieldConflict("Esta visita já foi preparada com outro vínculo de planejamento.")
                return self._public(previous)
            count = conn.scalar(sa.select(sa.func.count()).select_from(table).where(
                table.c.prefeitura == prefeitura, table.c.demo == bool(demo)))
            if count >= 200:
                raise FieldStoreError("Limite inicial de 200 lotes por prefeitura e tipo de dado atingido. Solicite manutenção.")
            batch_id = uuid.uuid4().hex
            batch = conn.execute(table.insert().values(id=batch_id, prefeitura=prefeitura, demo=bool(demo), actor=actor,
                         source=source, filename=filename, sha256=report["arquivo_sha256"], layout=report["layout"],
                         original=content, created=time.time(), status=status, report=report)
                         .returning(*self._public_columns(table))).mappings().one()
            if os_declaration:
                conn.execute(CampoOsReferencia.__table__.insert().values(batch_id=batch_id, solicitacao_id=os_declaration["id"]))
            return self._public(batch)

    def confirm(self, batch_id, *, prefeitura, actor):
        lots, inspections = CampoLote.__table__, CampoInspecao.__table__
        properties, surveys, links = CampoImovel.__table__, CampoLevantamento.__table__, CampoLoteInspecao.__table__
        with self.connection(write_prefeitura=prefeitura) as conn:
            batch = conn.execute(sa.select(lots).where(lots.c.id == batch_id, lots.c.prefeitura == prefeitura,
                                                     lots.c.actor == actor)).mappings().first()
            if batch is None:
                raise FieldStoreError("Lote indisponível para confirmação nesta conta e prefeitura.")
            if batch["status"] == "CONCLUIDO":
                return self._public(batch)
            if batch["status"] != "VALIDADO":
                raise FieldConflict("O lote contém inconsistências. Corrija o arquivo e valide novamente.")
            report = preview_csv(bytes(batch["original"]), prefeitura_id=prefeitura)
            declaration = batch["report"].get("vinculo_os")
            if declaration:
                reference = conn.scalar(sa.select(CampoOsReferencia.solicitacao_id).where(CampoOsReferencia.batch_id == batch_id))
                if reference != declaration["id"]:
                    raise FieldConflict("A referência à OS mudou ou foi removida. Revise a origem antes de confirmar.")
                self._check_os(conn, reference, prefeitura)
                for record in report["registros"]:
                    previous_os = conn.scalars(sa.select(CampoOsReferencia.solicitacao_id)
                        .join(links, links.c.batch_id == CampoOsReferencia.batch_id)
                        .join(lots, lots.c.id == links.c.batch_id)
                        .where(links.c.prefeitura == prefeitura, links.c.demo == batch["demo"],
                               links.c.origin == record["origem"], links.c.code == record["inspecao_codigo"],
                               lots.c.status == "CONCLUIDO", CampoOsReferencia.solicitacao_id.is_not(None)))
                    if any(value != reference for value in previous_os):
                        raise FieldConflict("Esta inspeção já está vinculada a outra OS. Revise a referência e o código da visita.")
                report["vinculo_os"] = declaration
            if report["status"] != "VALIDADO" or not report["registros"] or report["arquivo_sha256"] != batch["sha256"] or report["layout"] != batch["layout"]:
                raise FieldConflict("O arquivo preservado não passou pela validação. Nenhum registro foi gravado.")
            demo = batch["demo"]
            from .planning import validate_visits, link_visits
            plan_reference = batch["report"].get("planejamento")
            validate_visits(conn, report["registros"], prefeitura, demo, plan_reference, actor)
            if plan_reference:
                report["planejamento"] = plan_reference
            existing = list(conn.scalars(sa.select(inspections.c.payload).where(
                inspections.c.prefeitura == prefeitura, inspections.c.demo == demo)))
            by_key = {(r["origem"], r["inspecao_codigo"]): r for r in existing}
            new = []
            for record in report["registros"]:
                data = {key: record[key] for key in (*CSV_COLUMNS, *DEPOSIT_COLUMNS) if key in record}
                previous = by_key.get((data["origem"], data["inspecao_codigo"]))
                if previous is not None and previous != data:
                    raise FieldConflict(f"A inspeção {data['inspecao_codigo']} ({data['origem']}) diverge de uma carga anterior. Revise a origem; nenhum registro foi gravado.")
                if previous is None:
                    new.append(data)
            if len(existing) + len(new) > MAX_ROWS:
                raise FieldConflict("Limite inicial de 5.000 inspeções por prefeitura e tipo de dado atingido.")
            try:
                combined = preview_csv(_csv(existing + new), prefeitura_id=prefeitura)
            except PreviewValidationError as exc:
                raise FieldConflict("A base combinada excede o limite inicial de 1 MiB/5.000 registros. Nenhum registro foi gravado.") from exc
            if combined["erros"]:
                raise FieldConflict("Conflito com dados salvos: " + combined["erros"][0]["mensagem"])
            property_codes = set(conn.scalars(sa.select(properties.c.code).where(properties.c.prefeitura == prefeitura, properties.c.demo == demo)))
            survey_codes = set(conn.scalars(sa.select(surveys.c.code).where(surveys.c.prefeitura == prefeitura, surveys.c.demo == demo)))
            new_properties, new_surveys, new_inspections = [], [], []
            for record in new:
                code = record["imovel_codigo"]
                if code not in property_codes:
                    new_properties.append(dict(prefeitura=prefeitura, demo=demo, code=code,
                                               bairro=record["bairro"], area=record["area_codigo"]))
                    property_codes.add(code)
                survey = record["levantamento_codigo"] or None
                if survey and survey not in survey_codes:
                    new_surveys.append(dict(prefeitura=prefeitura, demo=demo, code=survey))
                    survey_codes.add(survey)
                new_inspections.append(dict(prefeitura=prefeitura, demo=demo, origin=record["origem"],
                             code=record["inspecao_codigo"], property_code=code, survey_code=survey,
                             stratum=record["estrato_codigo"], payload=record))
            for table, values in ((properties, new_properties), (surveys, new_surveys), (inspections, new_inspections)):
                if values:
                    conn.execute(table.insert(), values)
            link_visits(conn, report["registros"], prefeitura, demo, plan_reference, actor)
            conn.execute(links.insert(), [dict(batch_id=batch_id, prefeitura=prefeitura, demo=demo,
                         origin=record["origem"], code=record["inspecao_codigo"], source_line=record["linha"])
                         for record in report["registros"]])
            report["persistido"] = True
            saved = conn.execute(lots.update().where(lots.c.id == batch_id).values(status="CONCLUIDO", confirmed=time.time(),
                         inserted=len(new), reused=len(report["registros"])-len(new), report=report)
                         .returning(*self._public_columns(lots))).mappings().one()
            return self._public(saved)

    def history(self, prefeitura):
        table = CampoLote.__table__
        fields = [table.c[name] for name in ("id", "source", "filename", "created", "confirmed", "status", "demo", "inserted", "reused", "actor")]
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sa.select(*fields).where(table.c.prefeitura == prefeitura)
                    .order_by(table.c.created.desc(), table.c.id.desc()).limit(20)).mappings()]

    def get(self, batch_id, prefeitura):
        table = CampoLote.__table__
        with self.connection() as conn:
            return self._public(conn.execute(sa.select(*self._public_columns(table)).where(table.c.id == batch_id,
                                table.c.prefeitura == prefeitura)).mappings().first())

    def original(self, batch_id, prefeitura):
        table = CampoLote.__table__
        with self.connection() as conn:
            content = conn.scalar(sa.select(table.c.original).where(table.c.id == batch_id, table.c.prefeitura == prefeitura))
            return bytes(content) if content is not None else None

    def records(self, prefeitura, *, demo):
        """Consulta as identidades publicadas, sem multiplicar por lotes reutilizados."""
        table = CampoInspecao.__table__
        with self.connection() as conn:
            rows = list(conn.scalars(sa.select(table.c.payload).where(
                table.c.prefeitura == prefeitura, table.c.demo == demo
            ).order_by(table.c.origin, table.c.code).limit(MAX_ROWS + 1)))
        if len(rows) > MAX_ROWS:
            raise FieldStoreError("A consulta excedeu 5.000 inspeções. Solicite revisão do limite da base de campo.")
        return rows
