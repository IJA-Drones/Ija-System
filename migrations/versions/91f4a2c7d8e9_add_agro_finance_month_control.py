"""add agro finance month control

Revision ID: 91f4a2c7d8e9
Revises: 7b3f2c1a8d44
Create Date: 2026-04-17 11:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "91f4a2c7d8e9"
down_revision = "7b3f2c1a8d44"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade():
    bind = op.get_bind()
    if _table_exists(bind, "financeiro_agro_competencia_controle"):
        return

    op.create_table(
        "financeiro_agro_competencia_controle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competencia_ano", sa.Integer(), nullable=False),
        sa.Column("competencia_mes", sa.Integer(), nullable=False),
        sa.Column("liberado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("atualizado_por_nome", sa.String(length=120), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competencia_ano", "competencia_mes", name="uq_financeiro_agro_competencia_controle"),
    )

    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_id"),
        "financeiro_agro_competencia_controle",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_competencia_ano"),
        "financeiro_agro_competencia_controle",
        ["competencia_ano"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_competencia_mes"),
        "financeiro_agro_competencia_controle",
        ["competencia_mes"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_liberado"),
        "financeiro_agro_competencia_controle",
        ["liberado"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_criado_em"),
        "financeiro_agro_competencia_controle",
        ["criado_em"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financeiro_agro_competencia_controle_atualizado_em"),
        "financeiro_agro_competencia_controle",
        ["atualizado_em"],
        unique=False,
    )
    op.create_index(
        "ix_financeiro_agro_competencia_controle_ano_mes",
        "financeiro_agro_competencia_controle",
        ["competencia_ano", "competencia_mes"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "financeiro_agro_competencia_controle"):
        return

    op.drop_index(
        "ix_financeiro_agro_competencia_controle_ano_mes",
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_atualizado_em"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_criado_em"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_liberado"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_competencia_mes"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_competencia_ano"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_index(
        op.f("ix_financeiro_agro_competencia_controle_id"),
        table_name="financeiro_agro_competencia_controle",
    )
    op.drop_table("financeiro_agro_competencia_controle")
