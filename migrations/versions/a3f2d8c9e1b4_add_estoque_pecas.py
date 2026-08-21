"""add estoque pecas

Revision ID: a3f2d8c9e1b4
Revises: 5a6b7c8d9e0f
Create Date: 2026-08-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a3f2d8c9e1b4"
down_revision = "5a6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "estoque_pecas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("drone_id", sa.Integer(), nullable=True),
        sa.Column("numero_serie", sa.String(length=100), nullable=True),
        sa.Column("modelo_peca", sa.String(length=120), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantidade >= 0", name="ck_estoque_pecas_quantidade_nao_negativa"),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_serie"),
    )
    op.create_index(op.f("ix_estoque_pecas_criado_em"), "estoque_pecas", ["criado_em"], unique=False)
    op.create_index(op.f("ix_estoque_pecas_drone_id"), "estoque_pecas", ["drone_id"], unique=False)
    op.create_index("ix_estoque_pecas_drone_status", "estoque_pecas", ["drone_id", "status"], unique=False)
    op.create_index(op.f("ix_estoque_pecas_modelo_peca"), "estoque_pecas", ["modelo_peca"], unique=False)
    op.create_index(op.f("ix_estoque_pecas_numero_serie"), "estoque_pecas", ["numero_serie"], unique=False)
    op.create_index(op.f("ix_estoque_pecas_prefeitura_id"), "estoque_pecas", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_estoque_pecas_status"), "estoque_pecas", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_estoque_pecas_status"), table_name="estoque_pecas")
    op.drop_index(op.f("ix_estoque_pecas_prefeitura_id"), table_name="estoque_pecas")
    op.drop_index(op.f("ix_estoque_pecas_numero_serie"), table_name="estoque_pecas")
    op.drop_index(op.f("ix_estoque_pecas_modelo_peca"), table_name="estoque_pecas")
    op.drop_index("ix_estoque_pecas_drone_status", table_name="estoque_pecas")
    op.drop_index(op.f("ix_estoque_pecas_drone_id"), table_name="estoque_pecas")
    op.drop_index(op.f("ix_estoque_pecas_criado_em"), table_name="estoque_pecas")
    op.drop_table("estoque_pecas")
