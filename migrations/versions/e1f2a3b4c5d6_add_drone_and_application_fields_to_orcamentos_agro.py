"""add drone and application fields to orcamentos agro

Revision ID: e1f2a3b4c5d6
Revises: bc23de45fa67
Create Date: 2026-04-13 11:40:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "e1f2a3b4c5d6"
down_revision = "bc23de45fa67"
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
        if not _column_exists(conn, "orcamentos_agro", "drone_agro_id"):
            batch_op.add_column(sa.Column("drone_agro_id", sa.Integer(), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_tipo"):
            batch_op.add_column(sa.Column("drone_tipo", sa.String(length=50), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_identificacao"):
            batch_op.add_column(sa.Column("drone_identificacao", sa.String(length=100), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_modelo"):
            batch_op.add_column(sa.Column("drone_modelo", sa.String(length=100), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_funcao_operacional"):
            batch_op.add_column(sa.Column("drone_funcao_operacional", sa.String(length=30), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_registro_anatel"):
            batch_op.add_column(sa.Column("drone_registro_anatel", sa.String(length=50), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_registro_anac"):
            batch_op.add_column(sa.Column("drone_registro_anac", sa.String(length=50), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "drone_capacidade_tanque_l"):
            batch_op.add_column(sa.Column("drone_capacidade_tanque_l", sa.Numeric(precision=10, scale=2), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "possui_produto_aplicado"):
            batch_op.add_column(
                sa.Column(
                    "possui_produto_aplicado",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if not _column_exists(conn, "orcamentos_agro", "produto_aplicado_receituario"):
            batch_op.add_column(sa.Column("produto_aplicado_receituario", sa.Text(), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "inicio_aplicacao_prevista"):
            batch_op.add_column(sa.Column("inicio_aplicacao_prevista", sa.Date(), nullable=True))
        if not _column_exists(conn, "orcamentos_agro", "fim_aplicacao_prevista"):
            batch_op.add_column(sa.Column("fim_aplicacao_prevista", sa.Date(), nullable=True))

        if not _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_drone_agro_id"):
            batch_op.create_index(batch_op.f("ix_orcamentos_agro_drone_agro_id"), ["drone_agro_id"], unique=False)
        if not _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_possui_produto_aplicado"):
            batch_op.create_index(
                batch_op.f("ix_orcamentos_agro_possui_produto_aplicado"),
                ["possui_produto_aplicado"],
                unique=False,
            )
        if not _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_inicio_aplicacao_prevista"):
            batch_op.create_index(
                batch_op.f("ix_orcamentos_agro_inicio_aplicacao_prevista"),
                ["inicio_aplicacao_prevista"],
                unique=False,
            )
        if not _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_fim_aplicacao_prevista"):
            batch_op.create_index(
                batch_op.f("ix_orcamentos_agro_fim_aplicacao_prevista"),
                ["fim_aplicacao_prevista"],
                unique=False,
            )
        if not _foreign_key_exists(conn, "orcamentos_agro", "fk_orcamentos_agro_drone_agro_id_equipamentos_agro"):
            batch_op.create_foreign_key(
                "fk_orcamentos_agro_drone_agro_id_equipamentos_agro",
                "equipamentos_agro",
                ["drone_agro_id"],
                ["id"],
            )


def downgrade():
    conn = op.get_bind()

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if _foreign_key_exists(conn, "orcamentos_agro", "fk_orcamentos_agro_drone_agro_id_equipamentos_agro"):
            batch_op.drop_constraint("fk_orcamentos_agro_drone_agro_id_equipamentos_agro", type_="foreignkey")
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_fim_aplicacao_prevista"):
            batch_op.drop_index(batch_op.f("ix_orcamentos_agro_fim_aplicacao_prevista"))
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_inicio_aplicacao_prevista"):
            batch_op.drop_index(batch_op.f("ix_orcamentos_agro_inicio_aplicacao_prevista"))
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_possui_produto_aplicado"):
            batch_op.drop_index(batch_op.f("ix_orcamentos_agro_possui_produto_aplicado"))
        if _index_exists(conn, "orcamentos_agro", "ix_orcamentos_agro_drone_agro_id"):
            batch_op.drop_index(batch_op.f("ix_orcamentos_agro_drone_agro_id"))

        if _column_exists(conn, "orcamentos_agro", "fim_aplicacao_prevista"):
            batch_op.drop_column("fim_aplicacao_prevista")
        if _column_exists(conn, "orcamentos_agro", "inicio_aplicacao_prevista"):
            batch_op.drop_column("inicio_aplicacao_prevista")
        if _column_exists(conn, "orcamentos_agro", "produto_aplicado_receituario"):
            batch_op.drop_column("produto_aplicado_receituario")
        if _column_exists(conn, "orcamentos_agro", "possui_produto_aplicado"):
            batch_op.drop_column("possui_produto_aplicado")
        if _column_exists(conn, "orcamentos_agro", "drone_capacidade_tanque_l"):
            batch_op.drop_column("drone_capacidade_tanque_l")
        if _column_exists(conn, "orcamentos_agro", "drone_registro_anac"):
            batch_op.drop_column("drone_registro_anac")
        if _column_exists(conn, "orcamentos_agro", "drone_registro_anatel"):
            batch_op.drop_column("drone_registro_anatel")
        if _column_exists(conn, "orcamentos_agro", "drone_funcao_operacional"):
            batch_op.drop_column("drone_funcao_operacional")
        if _column_exists(conn, "orcamentos_agro", "drone_modelo"):
            batch_op.drop_column("drone_modelo")
        if _column_exists(conn, "orcamentos_agro", "drone_identificacao"):
            batch_op.drop_column("drone_identificacao")
        if _column_exists(conn, "orcamentos_agro", "drone_tipo"):
            batch_op.drop_column("drone_tipo")
        if _column_exists(conn, "orcamentos_agro", "drone_agro_id"):
            batch_op.drop_column("drone_agro_id")
