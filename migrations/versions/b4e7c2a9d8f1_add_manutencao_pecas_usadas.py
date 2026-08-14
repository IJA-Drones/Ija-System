"""add manutencao pecas usadas

Revision ID: b4e7c2a9d8f1
Revises: a3f2d8c9e1b4
Create Date: 2026-08-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b4e7c2a9d8f1"
down_revision = "a3f2d8c9e1b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manutencao_pecas_usadas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("drone_id", sa.Integer(), nullable=False),
        sa.Column("peca_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("quantidade_usada", sa.Integer(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantidade_usada > 0", name="ck_manutencao_pecas_usadas_quantidade_positiva"),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"]),
        sa.ForeignKeyConstraint(["peca_id"], ["estoque_pecas.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manutencao_pecas_usadas_criado_em"), "manutencao_pecas_usadas", ["criado_em"], unique=False)
    op.create_index("ix_manutencao_pecas_usadas_drone_criado", "manutencao_pecas_usadas", ["drone_id", "criado_em"], unique=False)
    op.create_index(op.f("ix_manutencao_pecas_usadas_drone_id"), "manutencao_pecas_usadas", ["drone_id"], unique=False)
    op.create_index(op.f("ix_manutencao_pecas_usadas_peca_id"), "manutencao_pecas_usadas", ["peca_id"], unique=False)
    op.create_index(op.f("ix_manutencao_pecas_usadas_prefeitura_id"), "manutencao_pecas_usadas", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_manutencao_pecas_usadas_usuario_id"), "manutencao_pecas_usadas", ["usuario_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_manutencao_pecas_usadas_usuario_id"), table_name="manutencao_pecas_usadas")
    op.drop_index(op.f("ix_manutencao_pecas_usadas_prefeitura_id"), table_name="manutencao_pecas_usadas")
    op.drop_index(op.f("ix_manutencao_pecas_usadas_peca_id"), table_name="manutencao_pecas_usadas")
    op.drop_index(op.f("ix_manutencao_pecas_usadas_drone_id"), table_name="manutencao_pecas_usadas")
    op.drop_index("ix_manutencao_pecas_usadas_drone_criado", table_name="manutencao_pecas_usadas")
    op.drop_index(op.f("ix_manutencao_pecas_usadas_criado_em"), table_name="manutencao_pecas_usadas")
    op.drop_table("manutencao_pecas_usadas")
