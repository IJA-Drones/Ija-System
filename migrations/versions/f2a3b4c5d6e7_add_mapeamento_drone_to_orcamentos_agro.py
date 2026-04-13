"""add mapeamento drone to orcamentos agro

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-13 12:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = inspect(conn)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(conn, table_name: str, constraint_name: str) -> bool:
    inspector = inspect(conn)
    return any(fk["name"] == constraint_name for fk in inspector.get_foreign_keys(table_name))


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_agro_id"):
            batch_op.add_column(sa.Column("drone_mapeamento_agro_id", sa.Integer(), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_identificacao"):
            batch_op.add_column(sa.Column("drone_mapeamento_identificacao", sa.String(length=100), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_modelo"):
            batch_op.add_column(sa.Column("drone_mapeamento_modelo", sa.String(length=100), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_funcao_operacional"):
            batch_op.add_column(sa.Column("drone_mapeamento_funcao_operacional", sa.String(length=30), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_registro_anatel"):
            batch_op.add_column(sa.Column("drone_mapeamento_registro_anatel", sa.String(length=50), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_mapeamento_registro_anac"):
            batch_op.add_column(sa.Column("drone_mapeamento_registro_anac", sa.String(length=50), nullable=True))

        if not _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_drone_mapeamento_agro_id"):
            batch_op.create_index(
                batch_op.f("ix_orcamentos_agro_drone_mapeamento_agro_id"),
                ["drone_mapeamento_agro_id"],
                unique=False,
            )
        if not _foreign_key_exists(conn, "orcamentos_agro", "fk_orcamentos_agro_drone_mapeamento_agro_id_equipamentos_agro"):
            batch_op.create_foreign_key(
                "fk_orcamentos_agro_drone_mapeamento_agro_id_equipamentos_agro",
                "equipamentos_agro",
                ["drone_mapeamento_agro_id"],
                ["id"],
            )


def downgrade():
    conn = op.get_bind()

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if _foreign_key_exists(conn, "orcamentos_agro", "fk_orcamentos_agro_drone_mapeamento_agro_id_equipamentos_agro"):
            batch_op.drop_constraint("fk_orcamentos_agro_drone_mapeamento_agro_id_equipamentos_agro", type_="foreignkey")
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_drone_mapeamento_agro_id"):
            batch_op.drop_index(batch_op.f("ix_orcamentos_agro_drone_mapeamento_agro_id"))

        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_registro_anac"):
            batch_op.drop_column("drone_mapeamento_registro_anac")
        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_registro_anatel"):
            batch_op.drop_column("drone_mapeamento_registro_anatel")
        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_funcao_operacional"):
            batch_op.drop_column("drone_mapeamento_funcao_operacional")
        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_modelo"):
            batch_op.drop_column("drone_mapeamento_modelo")
        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_identificacao"):
            batch_op.drop_column("drone_mapeamento_identificacao")
        if _column_exists(conn, "orcamentos_agro", "drone_mapeamento_agro_id"):
            batch_op.drop_column("drone_mapeamento_agro_id")
