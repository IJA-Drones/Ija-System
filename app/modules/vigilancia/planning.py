"""Planejamento informado pela coordenação; não executa sorteio amostral."""

import csv
import io
import time
from datetime import date

import sqlalchemy as sa

from .field_models import CampoLevantamento, CampoInspecao
from .field_store import FieldStore, FieldConflict
from .planning_models import CampoQuarteirao, CampoPlano, CampoPlanoEstrato, CampoPlanoQuarteirao, CampoPlanoVisita
from .geometry import validate_polygon

RG_COLUMNS = ("quarteirao", "bairro", "area", "imoveis", "referencia")
PLAN_COLUMNS = ("estrato", "imoveis_estrato", "meta_estrato", "criterio", "quarteirao", "meta_quarteirao", "agente_id")


def text(values, name, maximum=80, optional=False):
    if hasattr(values, "getlist") and len(values.getlist(name)) > 1:
        raise FieldConflict("Informe um único valor por campo.")
    value = str(values.get(name, "") or "").strip()
    if (not value and not optional) or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise FieldConflict(f"Confira o campo {name}: limite de {maximum} caracteres.")
    return value


def number(values, name, optional=False):
    value = text(values, name, 10, optional)
    if not value and optional:
        return None
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 2147483647:
        raise FieldConflict(f"Informe um inteiro positivo em {name}.")
    return int(value)


def read_csv(content, columns, optional_columns=()):
    if not isinstance(content, bytes) or len(content) > 1024 * 1024:
        raise FieldConflict("Envie um CSV de até 1 MiB.")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";", strict=True)
        if tuple(reader.fieldnames or ()) not in {columns, (*columns, *optional_columns)}:
            raise FieldConflict("Cabeçalho diferente do modelo de planejamento.")
        rows = []
        for row in reader:
            if len(rows) >= 5000 or None in row or None in row.values():
                raise FieldConflict("CSV incompleto ou com mais de 5.000 linhas.")
            rows.append(row)
        if not rows:
            raise FieldConflict("O arquivo não contém registros.")
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise FieldConflict("Use CSV UTF-8 separado por ponto e vírgula.") from exc


def scoped(table, prefeitura, demo):
    return (table.c.prefeitura == prefeitura, table.c.demo == bool(demo))


def rows(conn, table, prefeitura, demo, *where):
    return [dict(row) for row in conn.execute(sa.select(table).where(*scoped(table, prefeitura, demo), *where)).mappings()]


def available_agents(conn, prefeitura):
    from app.models import Usuario
    return [dict(row) for row in conn.execute(sa.select(Usuario.id, Usuario.nome_uvis)
        .where(Usuario.prefeitura_id == prefeitura,
               Usuario.tipo_usuario.in_(["uvis", "equipe_uvis", "prefeitura_admin", "agente_endemias"]))
        .order_by(Usuario.nome_uvis)).mappings()]


class PlanningStore(FieldStore):
    def released_plans(self, prefeitura, demo):
        table = CampoPlano.__table__
        with self.connection() as conn:
            if not sa.inspect(conn).has_table(table.name):
                return []
            return [dict(row) for row in conn.execute(sa.select(
                table.c.code, table.c.titulo, table.c.inicio, table.c.fim
            ).where(*scoped(table, prefeitura, demo), table.c.status == "LIBERADO")
             .order_by(table.c.inicio.desc(), table.c.code)).mappings()]

    def agent_blocks(self, prefeitura, agent_id, demo):
        plans, blocks = CampoPlano.__table__, CampoPlanoQuarteirao.__table__
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sa.select(blocks, plans.c.titulo, plans.c.inicio, plans.c.fim)
                .join(plans, sa.and_(plans.c.prefeitura == blocks.c.prefeitura, plans.c.demo == blocks.c.demo,
                                    plans.c.code == blocks.c.plano))
                .where(*scoped(blocks, prefeitura, demo), blocks.c.agente_id == agent_id, plans.c.status == "LIBERADO")
                .order_by(plans.c.inicio, blocks.c.plano, blocks.c.quarteirao)).mappings()]

    def overview(self, prefeitura, demo, code=""):
        with self.connection() as conn:
            rg = rows(conn, CampoQuarteirao.__table__, prefeitura, demo)
            plans = rows(conn, CampoPlano.__table__, prefeitura, demo)
            plans.sort(key=lambda row: (row["inicio"], row["code"]), reverse=True)
            selected = next((row for row in plans if row["code"] == code), None)
            strata = rows(conn, CampoPlanoEstrato.__table__, prefeitura, demo, CampoPlanoEstrato.plano == code) if selected else []
            blocks = rows(conn, CampoPlanoQuarteirao.__table__, prefeitura, demo, CampoPlanoQuarteirao.plano == code) if selected else []
            visits = rows(conn, CampoPlanoVisita.__table__, prefeitura, demo, CampoPlanoVisita.plano == code) if selected else []
            inspected = {row["code"]: row["payload"] for row in conn.execute(sa.select(CampoInspecao.code, CampoInspecao.payload)
                .where(*scoped(CampoInspecao.__table__, prefeitura, demo), CampoInspecao.survey_code == code)).mappings()} if selected else {}
            for block in blocks:
                data = [inspected[v["code"]] for v in visits if v["quarteirao"] == block["quarteirao"] and v["code"] in inspected]
                block["inspecionados"] = len({v["imovel_codigo"] for v in data if v["situacao"] == "INSPECIONADO"})
                block["pendentes"] = len({v["imovel_codigo"] for v in data if v["situacao"] != "INSPECIONADO"})
            return dict(territorio=sorted(rg, key=lambda r: r["code"]), planos=plans, plano=selected,
                        estratos=sorted(strata, key=lambda r: r["code"]), quarteiroes=sorted(blocks, key=lambda r: r["quarteirao"]),
                        agentes=available_agents(conn, prefeitura))

    def mutate(self, prefeitura, demo, actor, action, values, content=None):
        with self.connection(write_prefeitura=prefeitura) as conn:
            if action in {"territorio", "importar_territorio"}:
                source = read_csv(content, RG_COLUMNS, ("geometria",)) if content is not None else [values]
                has_geometry = content is not None and any(row.get("geometria") for row in source)
                if has_geometry and values.get("geometrias_confirmadas") != "sim":
                    raise FieldConflict("Confira os polígonos do CSV e marque a confirmação dos contornos antes de importar.")
                self._territory(conn, prefeitura, demo, actor, source, imported_geometry=has_geometry)
                return ""
            code = text(values, "plano")
            table = CampoPlano.__table__
            where = (*scoped(table, prefeitura, demo), table.c.code == code)
            previous = conn.execute(sa.select(table).where(*where)).mappings().first()
            if action == "criar":
                if previous:
                    raise FieldConflict("Já existe um planejamento com este código.")
                if conn.scalar(sa.select(sa.func.count()).select_from(CampoInspecao).where(
                    *scoped(CampoInspecao.__table__, prefeitura, demo), CampoInspecao.survey_code == code)):
                    raise FieldConflict("Esse código já possui inspeções legadas. Use um novo código para o planejamento.")
                metadata = self._metadata(values)
                parent = CampoLevantamento.__table__
                if not rows(conn, parent, prefeitura, demo, parent.c.code == code):
                    conn.execute(parent.insert().values(prefeitura=prefeitura, demo=demo, code=code))
                conn.execute(table.insert().values(prefeitura=prefeitura, demo=demo, code=code,
                    **metadata, status="RASCUNHO", versao=1,
                    historico=[dict(acao="criar", autor=actor, instante=time.time())]))
                return code
            if previous is None:
                raise FieldConflict("Planejamento indisponível nesta prefeitura e origem de dados.")
            if number(values, "versao") != previous["versao"]:
                raise FieldConflict("O planejamento foi alterado por outra pessoa. Reabra a página antes de salvar.")
            changes = {}
            if action == "encerrar":
                if previous["status"] != "LIBERADO":
                    raise FieldConflict("Somente um planejamento liberado pode ser encerrado.")
                changes["status"] = "ENCERRADO"
            else:
                if previous["status"] != "RASCUNHO":
                    raise FieldConflict("O planejamento liberado ou encerrado está protegido contra alterações.")
                if action == "metadados":
                    changes = self._metadata(values)
                elif action == "estrato":
                    item = self._stratum(values)
                    self._upsert(conn, CampoPlanoEstrato.__table__, prefeitura, demo, code, item, "code")
                elif action == "quarteirao":
                    item = self._block(conn, prefeitura, demo, values)
                    if not rows(conn, CampoPlanoEstrato.__table__, prefeitura, demo,
                                CampoPlanoEstrato.plano == code, CampoPlanoEstrato.code == item["estrato"]):
                        raise FieldConflict("Cadastre o estrato deste planejamento antes do quarteirão.")
                    self._upsert(conn, CampoPlanoQuarteirao.__table__, prefeitura, demo, code, item, "quarteirao")
                elif action == "remover_quarteirao":
                    b = CampoPlanoQuarteirao.__table__
                    conn.execute(b.delete().where(*scoped(b, prefeitura, demo), b.c.plano == code, b.c.quarteirao == text(values, "quarteirao")))
                elif action == "remover_estrato":
                    b, s = CampoPlanoQuarteirao.__table__, CampoPlanoEstrato.__table__
                    key = text(values, "estrato")
                    if rows(conn, b, prefeitura, demo, b.c.plano == code, b.c.estrato == key):
                        raise FieldConflict("Remova os quarteirões deste estrato antes de removê-lo.")
                    conn.execute(s.delete().where(*scoped(s, prefeitura, demo), s.c.plano == code, s.c.code == key))
                elif action == "importar_plano":
                    self._import_plan(conn, prefeitura, demo, code, read_csv(content, PLAN_COLUMNS))
                elif action == "liberar":
                    if values.get("amostra_validada") != "sim":
                        raise FieldConflict("Confirme que o plano amostral foi revisado pela coordenação.")
                    self._check_release(conn, prefeitura, demo, code)
                    changes["status"] = "LIBERADO"
                else:
                    raise FieldConflict("Ação de planejamento inválida.")
            changes.update(versao=previous["versao"] + 1,
                historico=[*previous["historico"], dict(acao=action, autor=actor, instante=time.time())])
            conn.execute(table.update().where(*where).values(**changes))
            return code

    def visit_context(self, prefeitura, demo, reference):
        with self.connection() as conn:
            plans = rows(conn, CampoPlano.__table__, prefeitura, demo, CampoPlano.code == reference["plano"])
            blocks = rows(conn, CampoPlanoQuarteirao.__table__, prefeitura, demo,
                         CampoPlanoQuarteirao.plano == reference["plano"],
                         CampoPlanoQuarteirao.quarteirao == reference["quarteirao"])
            if not plans or not blocks or plans[0]["status"] != "LIBERADO":
                raise FieldConflict("O quarteirão não está disponível em um levantamento liberado.")
            block = blocks[0]
            return dict(levantamento_codigo=plans[0]["code"], estrato_codigo=block["estrato"],
                        area_codigo=block["territorio"]["area"], bairro=block["territorio"]["bairro"], origem="LIRAA")

    @staticmethod
    def _metadata(values):
        try:
            start, end = date.fromisoformat(text(values, "inicio", 10)), date.fromisoformat(text(values, "fim", 10))
        except ValueError as exc:
            raise FieldConflict("Informe datas válidas para o levantamento.") from exc
        if end < start:
            raise FieldConflict("O fim do levantamento deve ser posterior ou igual ao início.")
        return dict(titulo=text(values, "titulo", 120), inicio=start, fim=end,
                    responsavel=text(values, "responsavel", 120), fonte=text(values, "fonte", 200))

    @staticmethod
    def _territory(conn, prefeitura, demo, actor, source, imported_geometry=False):
        table, seen = CampoQuarteirao.__table__, set()
        for values in source:
            code = text(values, "quarteirao")
            if code in seen:
                raise FieldConflict("Quarteirão repetido no arquivo territorial.")
            seen.add(code)
            item = dict(bairro=text(values, "bairro", 120), area=text(values, "area"),
                imoveis=number(values, "imoveis"), referencia=text(values, "referencia", 200),
                atualizado_por=actor, atualizado_em=time.time())
            where = (*scoped(table, prefeitura, demo), table.c.code == code)
            previous = rows(conn, table, prefeitura, demo, table.c.code == code)
            if imported_geometry and values.get("geometria"):
                geometry = validate_polygon(text(values, "geometria", 32768))
                if previous and previous[0].get("geometria") and previous[0]["geometria"] != geometry:
                    raise FieldConflict(f"O quarteirão {code} já possui outro contorno. Confira e altere esse limite pelo mapa.")
                item["geometria"] = geometry
            action = text(values, "geometria_acao", 20, optional=True) or "manter"
            if action not in {"manter", "substituir", "remover"}:
                raise FieldConflict("Ação de desenho inválida.")
            if action != "manter":
                if text(values, "geometria_confirmada", 3, optional=True) != "sim":
                    raise FieldConflict("Confira e confirme a alteração da área antes de salvar.")
                if previous and text(values, "territorio_versao", 40, optional=True) != str(previous[0]["atualizado_em"]):
                    raise FieldConflict("O território foi atualizado. Carregue novamente o cadastro no mapa antes de alterar a área.")
                item["geometria"] = validate_polygon(text(values, "geometria", 32768)) if action == "substituir" else None
            if previous:
                conn.execute(table.update().where(*where).values(**item))
            else:
                conn.execute(table.insert().values(prefeitura=prefeitura, demo=demo, code=code, **item))

    @staticmethod
    def _stratum(values):
        total, target = number(values, "imoveis_estrato"), number(values, "meta_estrato")
        if target > total:
            raise FieldConflict("A meta do estrato não pode ultrapassar sua população de imóveis.")
        return dict(code=text(values, "estrato"), imoveis=total, meta=target, criterio=text(values, "criterio", 200))

    @staticmethod
    def _block(conn, prefeitura, demo, values):
        code = text(values, "quarteirao")
        territory = rows(conn, CampoQuarteirao.__table__, prefeitura, demo, CampoQuarteirao.code == code)
        if not territory:
            raise FieldConflict(f"Cadastre o quarteirão {code} no território desta prefeitura e origem.")
        target = number(values, "meta_quarteirao")
        if target > territory[0]["imoveis"]:
            raise FieldConflict("A meta do quarteirão ultrapassa sua quantidade de imóveis.")
        agent = number(values, "agente_id", optional=True)
        if agent and agent not in {row["id"] for row in available_agents(conn, prefeitura)}:
            raise FieldConflict("A conta atribuída deve ser uma conta de campo da mesma prefeitura.")
        snapshot = {name: territory[0][name] for name in ("bairro", "area", "imoveis", "referencia")}
        if territory[0].get("geometria"):
            snapshot["geometria"] = territory[0]["geometria"]
        return dict(quarteirao=code, estrato=text(values, "estrato"), meta=target, agente_id=agent, territorio=snapshot)

    @staticmethod
    def _upsert(conn, table, prefeitura, demo, code, item, key):
        where = (*scoped(table, prefeitura, demo), table.c.plano == code, table.c[key] == item[key])
        if conn.execute(sa.select(table).where(*where)).first():
            conn.execute(table.update().where(*where).values(**item))
        else:
            conn.execute(table.insert().values(prefeitura=prefeitura, demo=demo, plano=code, **item))

    def _import_plan(self, conn, prefeitura, demo, code, source):
        strata, seen, blocks = {}, set(), []
        for row in source:
            item = self._stratum(row)
            if item["code"] in strata and strata[item["code"]] != item:
                raise FieldConflict("O mesmo estrato possui metas ou características divergentes no CSV.")
            strata[item["code"]] = item
            block = self._block(conn, prefeitura, demo, row)
            if block["quarteirao"] in seen:
                raise FieldConflict("Um quarteirão só pode aparecer uma vez no planejamento.")
            seen.add(block["quarteirao"])
            blocks.append(block)
        for table in (CampoPlanoQuarteirao.__table__, CampoPlanoEstrato.__table__):
            conn.execute(table.delete().where(*scoped(table, prefeitura, demo), table.c.plano == code))
        for item in strata.values():
            self._upsert(conn, CampoPlanoEstrato.__table__, prefeitura, demo, code, item, "code")
        for item in blocks:
            self._upsert(conn, CampoPlanoQuarteirao.__table__, prefeitura, demo, code, item, "quarteirao")

    @staticmethod
    def _check_release(conn, prefeitura, demo, code):
        strata = rows(conn, CampoPlanoEstrato.__table__, prefeitura, demo, CampoPlanoEstrato.plano == code)
        blocks = rows(conn, CampoPlanoQuarteirao.__table__, prefeitura, demo, CampoPlanoQuarteirao.plano == code)
        if not strata or not blocks:
            raise FieldConflict("Cadastre estratos e quarteirões antes de liberar o levantamento.")
        for stratum in strata:
            selected = [b for b in blocks if b["estrato"] == stratum["code"]]
            if sum(b["meta"] for b in selected) != stratum["meta"]:
                raise FieldConflict(f"As metas dos quarteirões não fecham a meta do estrato {stratum['code']}.")
            if sum(b["territorio"]["imoveis"] for b in selected) > stratum["imoveis"]:
                raise FieldConflict("A população dos quarteirões selecionados ultrapassa a do estrato.")


def csv_plan_reference(records, reference=None):
    """A coluna opcional vincula cada visita ao quarteirão, sem mudar o payload operacional."""
    if not any("quarteirao_codigo" in record for record in records):
        return reference
    if any(record["origem"] != "LIRAA" or not record.get("quarteirao_codigo") for record in records):
        raise FieldConflict("O CSV planejado deve conter somente visitas LIRAa com quarteirao_codigo preenchido.")
    codes = {record["levantamento_codigo"] for record in records}
    if len(codes) != 1:
        raise FieldConflict("Importe um único levantamento planejado por CSV de visitas.")
    inferred = {"plano": codes.pop(), "quarteiroes": {
        record["inspecao_codigo"]: record["quarteirao_codigo"] for record in records}}
    if reference:
        if reference["plano"] != inferred["plano"] or any(
            planned_block(reference, record) != record["quarteirao_codigo"] for record in records
        ):
            raise FieldConflict("Os quarteirões do CSV divergem do vínculo de planejamento informado.")
        return reference
    return inferred


def planned_block(reference, record):
    return reference.get("quarteirao") or reference.get("quarteiroes", {}).get(record["inspecao_codigo"])


def validate_visits(conn, records, prefeitura, demo, reference, actor=None):
    """Executado novamente na confirmação, sob o mesmo lock municipal do plano."""
    if not sa.inspect(conn).has_table(CampoPlano.__tablename__):
        if reference:
            raise FieldConflict("Instale a migração do planejamento antes de vincular visitas.")
        return
    # Consulte cada contexto uma vez por lote, inclusive planos inexistentes.
    # O cache é local à chamada: a confirmação consulta novamente sob o lock.
    codes = {record["levantamento_codigo"] for record in records if record["origem"] == "LIRAA"}
    plans = {plan["code"]: plan for plan in rows(
        conn, CampoPlano.__table__, prefeitura, demo, CampoPlano.code.in_(codes)
    )} if codes else {}
    blocks = {item["quarteirao"]: item for item in rows(
        conn, CampoPlanoQuarteirao.__table__, prefeitura, demo,
        CampoPlanoQuarteirao.plano == reference["plano"]
    )} if reference else {}
    agents_checked = set()
    for record in records:
        if record["origem"] != "LIRAA":
            if reference:
                raise FieldConflict("A visita de um planejamento deve ser LIRAa.")
            continue
        code = record["levantamento_codigo"]
        plan = plans.get(code)
        if not plan and not reference:
            continue  # Registros legados continuam disponíveis.
        if not plan:
            raise FieldConflict(f'O levantamento "{code}" não foi encontrado nesta prefeitura e origem de dados. Selecione o levantamento de destino na importação.')
        if plan["status"] != "LIBERADO":
            raise FieldConflict("O levantamento precisa estar liberado para receber visitas planejadas.")
        if not reference or reference.get("plano") != code:
            raise FieldConflict("Abra a visita pelo quarteirão no planejamento deste levantamento.")
        block_code = planned_block(reference, record)
        block = blocks.get(block_code)
        if block is None or block["estrato"] != record["estrato_codigo"]:
            raise FieldConflict("O quarteirão ou estrato não pertence à amostra planejada.")
        if reference.get("agente_id") is not None and block_code not in agents_checked:
            from app.models import Usuario
            agent_id = reference["agente_id"]
            if str(agent_id) != str(actor) or block["agente_id"] != agent_id or conn.scalar(sa.select(Usuario.id)
                .where(Usuario.id == agent_id, Usuario.prefeitura_id == prefeitura,
                       Usuario.tipo_usuario == "agente_endemias")) is None:
                raise FieldConflict("O quarteirão não está atribuído a este agente nesta prefeitura.")
            agents_checked.add(block_code)
        if any(record[key] != block["territorio"][column] for key, column in (("bairro", "bairro"), ("area_codigo", "area"))):
            raise FieldConflict("A área e o bairro devem corresponder ao quarteirão planejado.")
        inspected = date.fromisoformat(record["data_inspecao"])
        if not plan["inicio"] <= inspected <= plan["fim"]:
            raise FieldConflict("A data da visita está fora do período do levantamento.")


def link_visits(conn, records, prefeitura, demo, reference, actor):
    if not reference:
        return
    table = CampoPlanoVisita.__table__
    for record in records:
        block_code = planned_block(reference, record)
        where = (*scoped(table, prefeitura, demo), table.c.origin == record["origem"], table.c.code == record["inspecao_codigo"])
        existing = conn.execute(sa.select(table).where(*where)).mappings().first()
        if existing and (existing["plano"], existing["quarteirao"]) != (reference["plano"], block_code):
            raise FieldConflict("Esta visita já pertence a outro quarteirão planejado.")
        if not existing:
            conn.execute(table.insert().values(prefeitura=prefeitura, demo=demo, origin=record["origem"],
                code=record["inspecao_codigo"], plano=reference["plano"], quarteirao=block_code, autor=actor))
