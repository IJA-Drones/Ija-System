"""Limpeza revisável da POC de Pesqueira; preserva usuários, auditoria e dados reais.

Por padrão apenas prepara inventário e backup. A execução exige o fingerprint do
banco e o SHA do plano revisado. Não cria nem altera tabelas ou constraints.
"""

import argparse
import gzip
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
PID = 14
IBGE = "2610905"
REQUEST_NOTE = "DADOS FICTÍCIOS para teste de consultas personalizadas. Sem execução real."
COMMON_PARAMS = {"pid": PID, "ibge": IBGE, "poc": "Base de demonstração POC", "note": REQUEST_NOTE}
ROOT_FILTERS = {
    "solicitacoes": "prefeitura_id=:pid AND protocolo LIKE 'DEMO-CONSULTA-PESQ-202610-%' AND observacao=:note",
    "equipes": "prefeitura_id=:pid AND nome_equipe LIKE 'DEMO-CONSULTA-PESQ-202610%'",
    "denuncias": "prefeitura_id=:pid AND ((protocolo LIKE 'DEMO-20261022-PES-%' AND user_agent='carga-demo-pesqueira-20261022') OR (user_agent='poc-seed' AND cidadao_nome='Cidadão Demonstração'))",
    "relatos_saude": "prefeitura_id=:pid AND ((cidadao_nome='Maria das Dores' AND regexp_replace(cidadao_telefone,'[^0-9]','','g')='87999110001' AND descricao='Febre alta, dor atrás dos olhos e manchas vermelhas há 3 dias.') OR (cidadao_nome='José Carlos' AND regexp_replace(cidadao_telefone,'[^0-9]','','g')='87999110002' AND descricao='Febre, dor no corpo e enjoo desde ontem.'))",
    "acoes_publicas": "prefeitura_id=:pid AND (demo IS TRUE OR (id='b3f2cb0b73b24ba5a11869dab0f9e745' AND titulo='teste de ação' AND origem_os_id IS NULL))",
    "alertas_regras": "prefeitura_id=:pid AND criado_por_id=170 AND intervalo_horas=0 AND limiar=2 AND nome IN ('Focos no Centro','Casos suspeitos no município')",
    "vigilancia_agente_posicoes": "prefeitura_id=:pid AND usuario_id=167 AND registrado_em >= '2026-10-22' AND registrado_em < '2026-10-24'",
    "vigilancia_campo_lotes": "prefeitura=:pid AND (demo IS TRUE OR (source=:poc AND filename='amostra-poc.csv') OR (actor='167' AND source='Registro pelo aplicativo do agente' AND filename='visita-app.csv'))",
    "vigilancia_campo_imoveis": "prefeitura=:pid AND (demo IS TRUE OR code LIKE 'DEMO-MAPA-2610905-%')",
    "vigilancia_campo_levantamentos": "prefeitura=:pid AND (demo IS TRUE OR code LIKE 'DEMO-MAPA-2610905-%' OR code='LIRAA-2026-10')",
    "vigilancia_campo_planos": "prefeitura=:pid AND (demo IS TRUE OR fonte=:poc)",
    "vigilancia_campo_quarteiroes": "prefeitura=:pid AND (demo IS TRUE OR atualizado_por='poc-seed')",
    "vigilancia_risco_analises": "prefeitura=:pid AND demo IS TRUE",
    "vigilancia_migracoes": "prefeitura=:pid AND demo IS TRUE",
    "vigilancia_sinan_lotes": "ibge=:ibge AND demo IS TRUE",
    "integracao_esus_config": "prefeitura_id=:pid AND modo='simulado'",
    "integracao_esus_execucoes": "prefeitura_id=:pid AND modo='simulado' AND status<>'executando'",
    "integracao_esus_domicilios": "prefeitura_id=:pid AND origem='simulado'",
    "integracao_esus_visitas": "prefeitura_id=:pid AND origem='simulado'",
}
CHILD_TABLES = {
    "ordens_servico", "ordens_servico_equipe_uvis", "denuncia_anexos", "relatos_saude_eventos",
    "acoes_publicas_eventos", "acoes_publicas_midias", "alertas_disparos", "vigilancia_sinan_casos",
    "vigilancia_campo_inspecoes", "vigilancia_campo_lote_inspecoes", "vigilancia_campo_os",
    "vigilancia_campo_plano_estratos", "vigilancia_campo_plano_quarteiroes",
    "vigilancia_campo_plano_visitas", "vigilancia_inspecao_midias",
}
PROTECTED_TABLES = {"usuarios", "prefeituras", "pilotos", "equipamentos", "veiculos",
                    "consulta_email_envios", "vigilancia_sinan_lotes", "vigilancia_sinan_casos"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def private_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def identifier(name):
    if not re.fullmatch(r"[a-z_][a-z_0-9]*", name):
        raise ValueError("Identificador de banco não permitido.")
    return '"' + name + '"'


def key_predicate(columns, values, prefix="k"):
    """Chaves sempre parametrizadas; nenhuma condição de exclusão é texto livre."""
    params, clauses = {}, []
    for index, key in enumerate(values):
        bits = []
        for offset, (column, value) in enumerate(zip(columns, key, strict=True)):
            name = f"{prefix}{index}_{offset}"
            bits.append(f"{identifier(column)}=:{name}")
            params[name] = value
        clauses.append("(" + " AND ".join(bits) + ")")
    return " OR ".join(clauses) or "FALSE", params


def validate_rows(table, rows, confirmed_complaint=False):
    """Bloqueia expansão por FK para um registro real ou outro município."""
    if table not in ROOT_FILTERS and table not in CHILD_TABLES and table != "notificacoes":
        raise ValueError(f"Dependência não autorizada: {table}; nenhuma exclusão executada.")
    for row in rows:
        for column in ("prefeitura", "prefeitura_id"):
            if column in row and row[column] not in (None, PID):
                raise ValueError(f"Vínculo com outro município em {table}; limpeza cancelada.")
        if table == "solicitacoes" and not (
            str(row.get("protocolo", "")).startswith("DEMO-CONSULTA-PESQ-202610-")
            and row.get("observacao") == REQUEST_NOTE
        ):
            raise ValueError("Uma solicitação vinculada não é da demonstração; limpeza cancelada.")
        if table == "denuncias" and not (
            (str(row.get("protocolo", "")).startswith("DEMO-20261022-PES-")
             and row.get("user_agent") == "carga-demo-pesqueira-20261022")
            or (row.get("user_agent") == "poc-seed" and row.get("cidadao_nome") == "Cidadão Demonstração")
            or (confirmed_complaint and row.get("id") == 28 and row.get("prefeitura_id") == PID)
        ):
            raise ValueError("Relato sem confirmação de demonstração; limpeza cancelada.")
        if table == "vigilancia_sinan_lotes" and not (row.get("demo") is True and row.get("ibge") == IBGE):
            raise ValueError("Importações públicas reais não podem ser excluídas.")
        if table == "vigilancia_campo_inspecoes" and not (
            row.get("demo") is True or str(row.get("code", "")).startswith("DEMO-MAPA-2610905-")
        ):
            raise ValueError("Inspeção sem identificação demonstrativa; limpeza cancelada.")
        if table == "vigilancia_campo_planos" and not (row.get("demo") is True or row.get("fonte") == COMMON_PARAMS["poc"]):
            raise ValueError("Levantamento sem origem demonstrativa; limpeza cancelada.")
        if table == "acoes_publicas" and not (row.get("demo") is True or (
            row.get("id") == "b3f2cb0b73b24ba5a11869dab0f9e745" and row.get("titulo") == "teste de ação"
            and row.get("origem_os_id") is None
        )):
            raise ValueError("Publicação sem identificação demonstrativa; limpeza cancelada.")


def metadata(conn):
    pks = defaultdict(list)
    for row in conn.execute(sa.text("""SELECT tc.table_name,k.column_name
        FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage k
        ON k.constraint_name=tc.constraint_name AND k.table_schema=tc.table_schema
        WHERE tc.table_schema='public' AND tc.constraint_type='PRIMARY KEY'
        ORDER BY tc.table_name,k.ordinal_position""")).mappings():
        pks[row["table_name"]].append(row["column_name"])
    fks = [dict(row) for row in conn.execute(sa.text("""SELECT child.relname AS child,parent.relname AS parent,
        array_agg(ca.attname ORDER BY x.ord) AS child_columns,
        array_agg(pa.attname ORDER BY x.ord) AS parent_columns
        FROM pg_constraint con JOIN pg_class child ON child.oid=con.conrelid
        JOIN pg_class parent ON parent.oid=con.confrelid JOIN pg_namespace n ON n.oid=child.relnamespace
        CROSS JOIN LATERAL unnest(con.conkey,con.confkey) WITH ORDINALITY AS x(cnum,pnum,ord)
        JOIN pg_attribute ca ON ca.attrelid=child.oid AND ca.attnum=x.cnum
        JOIN pg_attribute pa ON pa.attrelid=parent.oid AND pa.attnum=x.pnum
        WHERE con.contype='f' AND n.nspname='public'
        GROUP BY con.oid,child.relname,parent.relname ORDER BY child.relname,parent.relname""")).mappings()]
    return dict(pks), fks


def read_rows(conn, table, where, params, lock=False):
    sql = f"SELECT row_to_json(t)::text FROM public.{identifier(table)} t WHERE ({where})"
    if lock:
        sql += " FOR UPDATE"
    raw = [row[0] for row in conn.execute(sa.text(sql), params)]
    if len(raw) > 5000:
        raise ValueError("Seleção maior que o limite da POC; limpeza cancelada.")
    return [(json.loads(value), value) for value in raw]


def deletion_order(selected, fks):
    children = {table: set() for table, rows in selected.items() if rows}
    for fk in fks:
        parent, child = fk["parent"], fk["child"]
        if parent not in children or child not in children:
            continue
        parent_keys = {tuple(row[0][col] for col in fk["parent_columns"]) for row in selected[parent].values()}
        if any(tuple(row[0].get(col) for col in fk["child_columns"]) in parent_keys
               for row in selected[child].values()):
            children[parent].add(child)
    result = []
    while children:
        ready = sorted(table for table, deps in children.items() if not deps)
        if not ready:
            raise ValueError("Dependência cíclica: é necessária revisão manual antes de excluir.")
        result.extend(ready)
        for table in ready:
            children.pop(table)
        for deps in children.values():
            deps.difference_update(ready)
    return result


def inventory(conn, pks, fks, confirmed_complaint, lock=False):
    city = read_rows(conn, "prefeituras", "id=:pid AND slug='pesqueira'", COMMON_PARAMS, lock)
    if len(city) != 1:
        raise ValueError("Cadastro de Pesqueira não corresponde ao escopo fixado.")
    selected = defaultdict(dict)

    def add(table, rows):
        validate_rows(table, [row[0] for row in rows], confirmed_complaint)
        for row, raw in rows:
            selected[table][tuple(row[column] for column in pks[table])] = (row, raw)

    for table, where in ROOT_FILTERS.items():
        if table in pks:
            if table == "denuncias" and confirmed_complaint:
                where = f"({where}) OR (prefeitura_id=:pid AND id=28)"
            add(table, read_rows(conn, table, where, COMMON_PARAMS, lock))
    processed = defaultdict(set)
    while True:
        changed = False
        for index, fk in enumerate(fks):
            parents = list(selected.get(fk["parent"], {}).values())
            keys = {tuple(row[0][col] for col in fk["parent_columns"]) for row in parents}
            fresh = keys - processed[index]
            if not fresh:
                continue
            processed[index].update(fresh)
            where, params = key_predicate(fk["child_columns"], sorted(fresh, key=str))
            rows = read_rows(conn, fk["child"], where, params, lock)
            if rows:
                count = len(selected.get(fk["child"], {}))
                add(fk["child"], rows)
                changed |= len(selected[fk["child"]]) != count
        if not changed:
            break
    # Notificações com URLs específicas dos registros fictícios; avisos genéricos ficam.
    links = []
    for table, bases in (("denuncias", ("/denuncias/", "/coordenadoria/denuncias/", "/uvis/denuncias/")),
                         ("relatos_saude", ("/relatos-saude/",))):
        for row, _ in selected.get(table, {}).values():
            links.extend((base + str(row["id"]),) for base in bases)
    if links and "notificacoes" in pks:
        where, params = key_predicate(["link"], links)
        add("notificacoes", read_rows(conn, "notificacoes", where, params, lock))
    snapshot = {table: [raw for _key, (_row, raw) in sorted(rows.items(), key=lambda pair: str(pair[0]))]
                for table, rows in sorted(selected.items()) if rows}
    return snapshot, selected, deletion_order(selected, fks), city[0][1]


def protected_fingerprints(conn, pks, selected):
    fingerprints = {}
    for table in sorted((set(selected) | PROTECTED_TABLES) & set(pks)):
        where, params = key_predicate(pks[table], list(selected.get(table, {})))
        if table == "prefeituras":
            where, params = "id=:pid", {"pid": PID}
        order = ",".join(identifier(col) for col in pks[table])
        result = conn.execute(sa.text(f"SELECT count(*) AS count, md5(COALESCE(string_agg(row_to_json(t)::text,E'\\n' ORDER BY {order}),'')) AS digest FROM public.{identifier(table)} t WHERE NOT ({where})"), params).mappings().one()
        fingerprints[table] = dict(result)
    return fingerprints


def restore_sql(snapshot, order, city_raw):
    statements = ["BEGIN;", "SET LOCAL standard_conforming_strings=on;"]
    for table in reversed(order):
        for raw in snapshot[table]:
            literal = raw.replace("'", "''")
            statements.append(f"INSERT INTO public.{identifier(table)} SELECT (json_populate_record(NULL::public.{identifier(table)}, '{literal}'::json)).*;")
    was_active = json.loads(city_raw)["ativa"]
    statements.extend([f"UPDATE public.prefeituras SET ativa={'TRUE' if was_active else 'FALSE'} WHERE id=14 AND slug='pesqueira';", "COMMIT;"])
    return "\n".join(statements).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--include-confirmed-complaint-28", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-target")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    url = make_url(os.environ.get("DATABASE_URL") or values["DATABASE_URL"])
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg2")
    if url.get_backend_name() != "postgresql":
        raise ValueError("Somente PostgreSQL é permitido para esta manutenção.")
    target = digest(f"{url.host}:{url.port or 5432}/{url.database}".encode())
    folder = args.backup_dir.resolve()
    folder.relative_to((ROOT / "instance/backups").resolve())
    engine = sa.create_engine(url, echo=False, connect_args={"connect_timeout": 12})
    try:
        with engine.connect().execution_options(isolation_level="SERIALIZABLE" if args.apply else "REPEATABLE READ") as conn:
            with conn.begin():
                if not args.apply:
                    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                conn.exec_driver_sql("SET LOCAL statement_timeout='30s'")
                if args.apply:
                    if target != args.expected_target:
                        raise ValueError("Fingerprint de destino divergente; nenhum dado alterado.")
                    conn.execute(sa.text("SELECT pg_advisory_xact_lock(1229603074,14)"))
                pks, fks = metadata(conn)
                snapshot, selected, order, city_raw = inventory(conn, pks, fks, args.include_confirmed_complaint_28, args.apply)
                content = encode(snapshot)
                plan_sha = digest(content)
                counts = {table: len(rows) for table, rows in snapshot.items()}
                if sum(counts.values()) > 5000:
                    raise ValueError("Seleção maior que o limite revisável da POC.")
                before = protected_fingerprints(conn, pks, selected)
                if not args.apply:
                    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
                    backup = gzip.compress(content)
                    sql = gzip.compress(restore_sql(snapshot, order, city_raw))
                    private_write(folder / "dados_antes.json.gz", backup)
                    private_write(folder / "restaurar.sql.gz", sql)
                    manifest = dict(prepared_utc=datetime.now(timezone.utc).isoformat(), target_fingerprint=target,
                                    plan_sha256=plan_sha, backup_sha256=digest(backup), restore_sha256=digest(sql),
                                    counts=counts, delete_order=order, preserved=before,
                                    prefeitura_before=json.loads(city_raw), users_preserved=True,
                                    confirmed_complaint_28=args.include_confirmed_complaint_28)
                    private_write(folder / "manifest.json", encode(manifest))
                else:
                    manifest = json.loads((folder / "manifest.json").read_bytes())
                    if not args.expected_plan or args.expected_plan != plan_sha or manifest["plan_sha256"] != plan_sha:
                        raise ValueError("Dados mudaram desde a revisão; prepare outro plano antes de excluir.")
                    if manifest["target_fingerprint"] != target:
                        raise ValueError("Backup pertence a outro banco.")
                    backup = (folder / "dados_antes.json.gz").read_bytes()
                    restore = (folder / "restaurar.sql.gz").read_bytes()
                    if digest(backup) != manifest["backup_sha256"] or digest(restore) != manifest["restore_sha256"] or gzip.decompress(backup) != content:
                        raise ValueError("Backup divergente; operação cancelada.")
                    for table, raw_rows in snapshot.items():
                        # Confere a reversibilidade de tipos, inclusive bytea/JSON, sem inserir dados.
                        raw_json = "[" + ",".join(raw_rows) + "]"
                        bad = conn.scalar(sa.text(f"SELECT count(*) FROM json_array_elements(CAST(:data AS json)) AS r(value) WHERE row_to_json(json_populate_record(NULL::public.{identifier(table)},r.value))::jsonb <> r.value::jsonb"), {"data": raw_json})
                        if bad:
                            raise ValueError(f"Backup não reproduz fielmente os tipos de {table}.")
                    for table in order:
                        where, params = key_predicate(pks[table], list(selected[table]))
                        result = conn.execute(sa.text(f"DELETE FROM public.{identifier(table)} WHERE ({where})"), params)
                        if result.rowcount != counts[table]:
                            raise ValueError(f"Contagem divergente em {table}; transação revertida.")
                    conn.execute(sa.text("UPDATE prefeituras SET ativa=FALSE WHERE id=:pid AND slug='pesqueira'"), {"pid": PID})
                    after = protected_fingerprints(conn, pks, selected)
                    if before != after:
                        raise ValueError("Registro protegido alterado; transação revertida.")
                    current, *_ = inventory(conn, pks, fks, args.include_confirmed_complaint_28)
                    if any(current.values()):
                        raise ValueError("Restaram dados do plano; transação revertida.")
                    details = dict(plan_sha256=plan_sha, backup_sha256=manifest["backup_sha256"], removed=counts,
                                   users_preserved=True, official_sinan_preserved=True, protected_rows_unchanged=True,
                                   backup_directory=str(folder.relative_to(ROOT)))
                    audit_id = conn.scalar(sa.text("""INSERT INTO auditoria_usuarios
                        (usuario_nome,metodo,tipo_evento,endpoint,path,status_code,prefeitura_id,objeto_tipo,objeto_id,resultado,detalhes,criado_em)
                        VALUES ('Manutenção autorizada','DELETE','LIMPEZA_POC','maintenance.cleanup_pesqueira_poc',
                        '/maintenance/pesqueira-poc-cleanup',200,14,'poc.pesqueira','14','SUCESSO',CAST(:details AS json),NOW()) RETURNING id"""), {"details": json.dumps(details)})
            if args.apply:
                private_write(folder / "resultado.json", encode(dict(executed_utc=datetime.now(timezone.utc).isoformat(), audit_id=audit_id, **details)))
            print(json.dumps(dict(mode="applied" if args.apply else "prepared", backup_dir=str(folder), target_fingerprint=target,
                                  plan_sha256=plan_sha, counts=counts, users_preserved=True,
                                  **({"audit_id": audit_id} if args.apply else {})), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except sa.exc.SQLAlchemyError:
        raise SystemExit("Falha de banco; transação não concluída. Nenhuma credencial é exibida.")
