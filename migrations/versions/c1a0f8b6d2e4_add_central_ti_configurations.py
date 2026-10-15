"""Add Central TI configurations after the document configuration migration.

No existing user, permission, or business record is updated. The isolated Neon
preparation may already have installed the complete structure without advancing
Alembic. Validate and reuse that structure; never repair or recreate it silently.
This inspection-based migration requires an online connection.
"""

import re

from alembic import op
import sqlalchemy as sa


revision = "c1a0f8b6d2e4"
down_revision = "a71d9c4e203b"
branch_labels = None
depends_on = None


EXPECTED_COLUMNS = {
    "central_ti_perfis_configuracoes": {"perfil_codigo", "versao", "atualizado_em", "atualizado_por_id"},
    "central_ti_selecoes": {"perfil_codigo", "codigo"},
    "central_ti_auditoria": {"id", "lote", "perfil_codigo", "usuario_id", "usuario_login", "versao_anterior", "versao_nova", "antes", "depois", "criado_em"},
}


# Keep this revision self-contained: importing application models would load
# current code rather than the historical contract of this migration.
_COLUMN_SPECS = {
    "central_ti_perfis_configuracoes": {
        "perfil_codigo": ("varchar", 20, False),
        "versao": ("integer", None, False),
        "atualizado_em": ("datetime", None, False),
        "atualizado_por_id": ("integer", None, True),
    },
    "central_ti_selecoes": {
        "perfil_codigo": ("varchar", 20, False),
        "codigo": ("varchar", 120, False),
    },
    "central_ti_auditoria": {
        "id": ("integer", None, False),
        "lote": ("varchar", 36, False),
        "perfil_codigo": ("varchar", 20, False),
        "usuario_id": ("integer", None, True),
        "usuario_login": ("varchar", 50, False),
        "versao_anterior": ("integer", None, False),
        "versao_nova": ("integer", None, False),
        "antes": ("json", None, False),
        "depois": ("json", None, False),
        "criado_em": ("datetime", None, False),
    },
}
_PRIMARY_KEYS = {
    "central_ti_perfis_configuracoes": ["perfil_codigo"],
    "central_ti_selecoes": ["perfil_codigo", "codigo"],
    "central_ti_auditoria": ["id"],
}
_FOREIGN_KEYS = {
    "central_ti_perfis_configuracoes": (
        ["atualizado_por_id"], "usuarios", ["id"], "SET NULL",
    ),
    "central_ti_selecoes": (
        ["perfil_codigo"], "central_ti_perfis_configuracoes", ["perfil_codigo"], "CASCADE",
    ),
    "central_ti_auditoria": (["usuario_id"], "usuarios", ["id"], "SET NULL"),
}
_CHECKS = {
    "central_ti_perfis_configuracoes": {
        "ck_central_ti_perfil_versao": "versao >= 1",
    },
    "central_ti_selecoes": {},
    "central_ti_auditoria": {
        "ck_central_ti_auditoria_versao": "versao_anterior >= 0 AND versao_nova > versao_anterior",
    },
}
_INDEXES = {
    "central_ti_perfis_configuracoes": {},
    "central_ti_selecoes": {},
    "central_ti_auditoria": {
        "ix_central_ti_auditoria_lote": ["lote"],
        "ix_central_ti_auditoria_perfil_codigo": ["perfil_codigo"],
    },
}


def _schema_error(detail):
    raise RuntimeError(f"Estrutura incompatível da Central de TI ({detail}); migração interrompida sem correções automáticas.")


def _type_matches(type_, kind, length):
    visit_name = type_.__visit_name__.lower()
    if kind == "varchar":
        return visit_name in {"varchar", "string"} and type_.length == length
    if kind == "datetime":
        return visit_name in {"datetime", "timestamp"} and not type_.timezone
    return visit_name == kind


def _normalized_check(expression):
    # Parse the small expression grammar used here. PostgreSQL adds redundant
    # parentheses during reflection; deleting all parentheses would also accept
    # expressions where changed grouping alters the meaning of the CHECK.
    token_pattern = re.compile(r'\s*("[A-Za-z_][A-Za-z_0-9]*"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|>=|<=|<>|!=|[=><()])')
    tokens = []
    offset = 0
    expression = (expression or "").strip()
    while offset < len(expression):
        match = token_pattern.match(expression, offset)
        if not match:
            return None
        tokens.append(match.group(1).lower())
        offset = match.end()
    position = 0

    def atom():
        nonlocal position
        if position >= len(tokens):
            raise ValueError
        token = tokens[position]
        position += 1
        if token == "(":
            result = conjunction()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError
            position += 1
            return result
        if token.isdecimal():
            return ("integer", int(token))
        if re.fullmatch(r'"?[a-z_][a-z_0-9]*"?', token) and token != "and":
            return ("identifier", token.strip('"'))
        raise ValueError

    def comparison():
        nonlocal position
        left = atom()
        if position < len(tokens) and tokens[position] in {">=", "<=", ">", "<", "=", "!=", "<>"}:
            operator = tokens[position]
            position += 1
            return (operator, left, atom())
        return left

    def conjunction():
        nonlocal position
        result = comparison()
        while position < len(tokens) and tokens[position] == "and":
            position += 1
            result = ("and", result, comparison())
        return result

    try:
        result = conjunction()
        return result if position == len(tokens) else None
    except ValueError:
        return None


def _validate_defaults(table, columns, dialect):
    for name, column in columns.items():
        default = column.get("default")
        if name == "versao" and table == "central_ti_perfis_configuracoes":
            normalized = re.sub(r"[\s()']", "", default or "").lower()
            if normalized not in {"1", "1::integer"}:
                _schema_error(f"{table}.{name}: valor padrão")
        elif name in {"atualizado_em", "criado_em"}:
            if re.sub(r"\s", "", default or "").lower() not in {"now()", "current_timestamp", "(current_timestamp)"}:
                _schema_error(f"{table}.{name}: valor padrão")
        elif name == "id" and table == "central_ti_auditoria" and dialect == "postgresql":
            # SERIAL and GENERATED IDENTITY both generate the existing integer
            # primary key without changing or resetting its sequence.
            if not (column.get("identity") or (
                column.get("autoincrement") and re.fullmatch(
                    r"nextval\('[^']+'::regclass\)", default or "", flags=re.IGNORECASE,
                )
            )):
                _schema_error(f"{table}.{name}: geração da chave primária")
        elif default is not None:
            _schema_error(f"{table}.{name}: valor padrão inesperado")


def _validate_prerequisites(inspector):
    if not inspector.has_table("usuarios"):
        _schema_error("tabela usuarios ausente")
    users_columns = {column["name"]: column for column in inspector.get_columns("usuarios")}
    if "id" not in users_columns or not _type_matches(users_columns["id"]["type"], "integer", None):
        _schema_error("usuarios.id deve ser INTEGER")
    if inspector.get_pk_constraint("usuarios")["constrained_columns"] != ["id"]:
        _schema_error("usuarios.id deve ser a chave primária")


def validate_existing_schema(connection):
    inspector = sa.inspect(connection)
    _validate_prerequisites(inspector)
    existing = set(inspector.get_table_names()) & set(EXPECTED_COLUMNS)
    if existing != set(EXPECTED_COLUMNS):
        _schema_error("estrutura ausente ou parcial")
    for table, expected in EXPECTED_COLUMNS.items():
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        if set(columns) != expected:
            _schema_error(f"{table}: colunas")
        for name, (kind, length, nullable) in _COLUMN_SPECS[table].items():
            column = columns[name]
            if not _type_matches(column["type"], kind, length):
                _schema_error(f"{table}.{name}: tipo ou tamanho")
            if column["nullable"] != nullable or column.get("computed"):
                _schema_error(f"{table}.{name}: nulabilidade ou coluna calculada")
        _validate_defaults(table, columns, connection.dialect.name)
        if inspector.get_pk_constraint(table)["constrained_columns"] != _PRIMARY_KEYS[table]:
            _schema_error(f"{table}: chave primária")
        if inspector.get_unique_constraints(table):
            _schema_error(f"{table}: restrição de unicidade inesperada")

        checks = inspector.get_check_constraints(table)
        actual_checks = {check["name"]: _normalized_check(check["sqltext"]) for check in checks}
        expected_checks = {name: _normalized_check(sql) for name, sql in _CHECKS[table].items()}
        if (
            len(checks) != len(expected_checks)
            or actual_checks != expected_checks
            or any(any((check.get("dialect_options") or {}).values()) for check in checks)
        ):
            _schema_error(f"{table}: expressão CHECK")

        foreign_keys = inspector.get_foreign_keys(table)
        if len(foreign_keys) != 1:
            _schema_error(f"{table}: quantidade de vínculos")
        fk = foreign_keys[0]
        constrained, referred_table, referred_columns, ondelete = _FOREIGN_KEYS[table]
        options = fk.get("options") or {}
        if (
            fk["constrained_columns"] != constrained
            or fk["referred_table"] != referred_table
            or fk["referred_columns"] != referred_columns
            or fk.get("referred_schema") not in {None, inspector.default_schema_name}
            or str(options.get("ondelete", "")).upper() != ondelete
            or str(options.get("onupdate", "NO ACTION")).upper() != "NO ACTION"
            or str(options.get("match", "SIMPLE")).upper() != "SIMPLE"
            or options.get("deferrable")
            or options.get("initially")
        ):
            _schema_error(f"{table}: vínculo ou ON DELETE")

        indexes = inspector.get_indexes(table)
        if {index["name"] for index in indexes} != set(_INDEXES[table]):
            _schema_error(f"{table}: índices")
        for index in indexes:
            options = index.get("dialect_options") or {}
            if (
                index["column_names"] != _INDEXES[table][index["name"]]
                or index.get("unique")
                or index.get("expressions")
                or index.get("column_sorting")
                or any(value for key, value in options.items() if key.endswith(("_where", "_include", "_ops")))
                or options.get("postgresql_using", "btree") != "btree"
            ):
                _schema_error(f"{table}.{index['name']}: definição do índice")


def upgrade():
    if op.get_context().as_sql:
        raise RuntimeError("A migração da Central de TI exige conexão online para validar a estrutura existente.")
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # These settings and the lock last only for this migration transaction;
        # no role/database/global setting is changed. Share the same lock key
        # with the isolated Neon preparation command.
        connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(sa.text("SET LOCAL statement_timeout = '60s'"))
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(481725910063)"))
    inspector = sa.inspect(connection)
    _validate_prerequisites(inspector)
    existing = set(inspector.get_table_names()) & set(EXPECTED_COLUMNS)
    if existing:
        if existing != set(EXPECTED_COLUMNS):
            raise RuntimeError("Estrutura parcial da Central de TI; revise antes de migrar.")
        validate_existing_schema(connection)
        return
    op.create_table(
        "central_ti_perfis_configuracoes",
        sa.Column("perfil_codigo", sa.String(20), primary_key=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("versao >= 1", name="ck_central_ti_perfil_versao"),
    )
    op.create_table(
        "central_ti_selecoes",
        sa.Column("perfil_codigo", sa.String(20), sa.ForeignKey("central_ti_perfis_configuracoes.perfil_codigo", ondelete="CASCADE"), primary_key=True),
        sa.Column("codigo", sa.String(120), primary_key=True),
    )
    op.create_table(
        "central_ti_auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote", sa.String(36), nullable=False),
        sa.Column("perfil_codigo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usuario_login", sa.String(50), nullable=False),
        sa.Column("versao_anterior", sa.Integer(), nullable=False),
        sa.Column("versao_nova", sa.Integer(), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=False),
        sa.Column("depois", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("versao_anterior >= 0 AND versao_nova > versao_anterior", name="ck_central_ti_auditoria_versao"),
    )
    op.create_index("ix_central_ti_auditoria_lote", "central_ti_auditoria", ["lote"])
    op.create_index("ix_central_ti_auditoria_perfil_codigo", "central_ti_auditoria", ["perfil_codigo"])
    validate_existing_schema(connection)


def downgrade():
    # Only remove these configuration tables, never existing users/business data.
    op.drop_table("central_ti_auditoria")
    op.drop_table("central_ti_selecoes")
    op.drop_table("central_ti_perfis_configuracoes")
