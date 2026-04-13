"""add cultura alternativa and adicional spraying values to agro

Revision ID: ab12cd34ef56
Revises: f7b6c5d4e3a2
Create Date: 2026-04-13 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "f7b6c5d4e3a2"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = inspect(conn)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if not _column_exists(conn, "orcamentos_agro", "cultura_alternativa"):
            batch_op.add_column(sa.Column("cultura_alternativa", sa.String(length=100), nullable=True))
            batch_op.create_index(batch_op.f("ix_orcamentos_agro_cultura_alternativa"), ["cultura_alternativa"], unique=False)
        if not _column_exists(conn, "orcamentos_agro", "preco_pulverizacao_adicional"):
            batch_op.add_column(
                sa.Column("preco_pulverizacao_adicional", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0")
            )

    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        if not _column_exists(conn, "contratos_agro", "cultura_alternativa"):
            batch_op.add_column(sa.Column("cultura_alternativa", sa.String(length=100), nullable=True))
            batch_op.create_index(batch_op.f("ix_contratos_agro_cultura_alternativa"), ["cultura_alternativa"], unique=False)
        if not _column_exists(conn, "contratos_agro", "valor_pulverizacao_adicional_ha"):
            batch_op.add_column(
                sa.Column("valor_pulverizacao_adicional_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0")
            )

    op.execute(text("UPDATE orcamentos_agro SET preco_pulverizacao_adicional = 0 WHERE preco_pulverizacao_adicional IS NULL"))
    op.execute(text("UPDATE contratos_agro SET valor_pulverizacao_adicional_ha = 0 WHERE valor_pulverizacao_adicional_ha IS NULL"))
def downgrade():
    conn = op.get_bind()

    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        if _index_exists(conn, "contratos_agro", "ix_contratos_agro_cultura_alternativa"):
            batch_op.drop_index("ix_contratos_agro_cultura_alternativa")
        if _column_exists(conn, "contratos_agro", "valor_pulverizacao_adicional_ha"):
            batch_op.drop_column("valor_pulverizacao_adicional_ha")
        if _column_exists(conn, "contratos_agro", "cultura_alternativa"):
            batch_op.drop_column("cultura_alternativa")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_cultura_alternativa"):
            batch_op.drop_index("ix_orcamentos_agro_cultura_alternativa")
        if _column_exists(conn, "orcamentos_agro", "preco_pulverizacao_adicional"):
            batch_op.drop_column("preco_pulverizacao_adicional")
        if _column_exists(conn, "orcamentos_agro", "cultura_alternativa"):
            batch_op.drop_column("cultura_alternativa")
