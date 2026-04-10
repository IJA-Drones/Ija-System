"""add area_ha and relax cliente_agro required fields

Revision ID: f7b6c5d4e3a2
Revises: e8b1c2d3f4a5
Create Date: 2026-04-10 12:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "f7b6c5d4e3a2"
down_revision = "e8b1c2d3f4a5"
branch_labels = None
depends_on = None


def _column_map(conn, table_name: str) -> dict:
    inspector = inspect(conn)
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def upgrade():
    conn = op.get_bind()
    orcamento_columns = _column_map(conn, "orcamentos_agro")
    cliente_columns = _column_map(conn, "clientes_agro")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if "area_ha" not in orcamento_columns:
            batch_op.add_column(sa.Column("area_ha", sa.Numeric(precision=12, scale=2), nullable=True))

    if "area_ha" in _column_map(conn, "orcamentos_agro"):
        op.execute(text("UPDATE orcamentos_agro SET area_ha = 0 WHERE area_ha IS NULL"))

    nullable_fields = (
        "documento",
        "cep",
        "logradouro",
        "numero",
        "bairro",
        "cidade",
        "uf",
    )

    with op.batch_alter_table("clientes_agro", schema=None) as batch_op:
        for field_name in nullable_fields:
            column = cliente_columns.get(field_name)
            if column is not None and not column.get("nullable", True):
                batch_op.alter_column(
                    field_name,
                    existing_type=column["type"],
                    nullable=True,
                )


def downgrade():
    conn = op.get_bind()
    cliente_columns = _column_map(conn, "clientes_agro")

    op.execute(text("UPDATE clientes_agro SET documento = 'SEM-DOC-' || id::text WHERE documento IS NULL"))
    op.execute(text("UPDATE clientes_agro SET cep = '' WHERE cep IS NULL"))
    op.execute(text("UPDATE clientes_agro SET logradouro = '' WHERE logradouro IS NULL"))
    op.execute(text("UPDATE clientes_agro SET numero = '' WHERE numero IS NULL"))
    op.execute(text("UPDATE clientes_agro SET bairro = '' WHERE bairro IS NULL"))
    op.execute(text("UPDATE clientes_agro SET cidade = '' WHERE cidade IS NULL"))
    op.execute(text("UPDATE clientes_agro SET uf = '' WHERE uf IS NULL"))

    non_nullable_fields = (
        "documento",
        "cep",
        "logradouro",
        "numero",
        "bairro",
        "cidade",
        "uf",
    )

    with op.batch_alter_table("clientes_agro", schema=None) as batch_op:
        for field_name in non_nullable_fields:
            column = cliente_columns.get(field_name)
            if column is not None and column.get("nullable", True):
                batch_op.alter_column(
                    field_name,
                    existing_type=column["type"],
                    nullable=False,
                )

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if "area_ha" in _column_map(conn, "orcamentos_agro"):
            batch_op.drop_column("area_ha")
