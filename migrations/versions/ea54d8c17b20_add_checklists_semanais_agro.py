"""Checklists semanais de veículos e drones do Agro."""

from alembic import op
import sqlalchemy as sa


revision = "ea54d8c17b20"
down_revision = "d8a7f519c203"
branch_labels = None
depends_on = None


TABLE = "checklists_semanais_agro"
REFERENCES = {
    "prefeitura_id": "prefeituras",
    "equipe_agro_id": "equipes_agro",
    "piloto_agro_id": "pilotos_agro",
    "equipamento_agro_id": "equipamentos_agro",
}
UNIQUE_FIELDS = ("piloto_agro_id", "equipe_agro_id", "semana_inicio", "equipamento_agro_id")


def _columns():
    return (
        sa.Column("id", sa.Integer(), primary_key=True),
        *(sa.Column(field, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="SET NULL"))
          for field, table in REFERENCES.items()),
        sa.Column("semana_inicio", sa.Date(), nullable=False),
        sa.Column("data_registro", sa.DateTime(), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("equipamento_identificacao", sa.String(100), nullable=False),
        sa.Column("equipamento_modelo", sa.String(100), nullable=False),
        sa.Column("nome_responsavel", sa.String(150), nullable=False),
        sa.Column("assinatura_piloto", sa.Text(), nullable=False),
        sa.Column("respostas", sa.JSON(), nullable=False),
    )


def validate_existing_schema(connection):
    inspector = sa.inspect(connection)
    dialect = inspector.bind.dialect
    existing = {column["name"]: column for column in inspector.get_columns(TABLE)}
    expected = {column.name: column for column in _columns()}
    if existing.keys() != expected.keys() or any(
        actual["type"].compile(dialect=dialect) != expected[name].type.compile(dialect=dialect)
        or actual["nullable"] != expected[name].nullable
        for name, actual in existing.items()
    ):
        raise RuntimeError(f"Colunas incompatíveis em {TABLE}.")

    identity = existing["id"]
    if inspector.get_pk_constraint(TABLE)["constrained_columns"] != ["id"] or (
        dialect.name == "postgresql" and not (
            identity.get("identity") or (identity.get("default") or "").startswith("nextval(")
        )
    ):
        raise RuntimeError(f"Chave primária incompatível em {TABLE}.")

    foreign_keys = {
        (tuple(key["constrained_columns"]), key["referred_table"], tuple(key["referred_columns"]),
         key.get("options", {}).get("ondelete"), key["referred_schema"] or inspector.default_schema_name)
        for key in inspector.get_foreign_keys(TABLE)
    }
    expected_keys = {((field,), table, ("id",), "SET NULL", inspector.default_schema_name)
                     for field, table in REFERENCES.items()}
    unique_constraints = {tuple(key["column_names"]) for key in inspector.get_unique_constraints(TABLE)}
    if foreign_keys != expected_keys or UNIQUE_FIELDS not in unique_constraints:
        raise RuntimeError(f"Vínculos ou unicidade incompatíveis em {TABLE}.")


def upgrade():
    # The test database may install this table before the intervening revisions.
    if not op.get_context().as_sql and sa.inspect(op.get_bind()).has_table(TABLE):
        validate_existing_schema(op.get_bind())
        return
    op.create_table(
        TABLE,
        *_columns(),
        sa.UniqueConstraint(*UNIQUE_FIELDS, name="uq_checklists_semanais_agro_registro"),
    )


def downgrade():
    op.drop_table(TABLE)
