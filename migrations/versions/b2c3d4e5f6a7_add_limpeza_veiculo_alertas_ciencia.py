"""add limpeza veiculo alertas ciencia

Revision ID: b2c3d4e5f6a7
Revises: a0b1c2d3e4f5
Create Date: 2026-07-30 12:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "limpezas_veiculo_alertas_ciencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("piloto_id", sa.Integer(), nullable=True),
        sa.Column("equipe_id", sa.Integer(), nullable=True),
        sa.Column("referencia_limpeza_em", sa.DateTime(), nullable=False),
        sa.Column("prazo_dias", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("reconhecido_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
        sa.ForeignKeyConstraint(["piloto_id"], ["pilotos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "veiculo_id",
            "usuario_id",
            "referencia_limpeza_em",
            "prazo_dias",
            name="uq_limpeza_alerta_ciencia_ref_usuario",
        ),
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_equipe_id"),
        "limpezas_veiculo_alertas_ciencia",
        ["equipe_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_piloto_id"),
        "limpezas_veiculo_alertas_ciencia",
        ["piloto_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_prazo_dias"),
        "limpezas_veiculo_alertas_ciencia",
        ["prazo_dias"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_reconhecido_em"),
        "limpezas_veiculo_alertas_ciencia",
        ["reconhecido_em"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_referencia_limpeza_em"),
        "limpezas_veiculo_alertas_ciencia",
        ["referencia_limpeza_em"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_usuario_id"),
        "limpezas_veiculo_alertas_ciencia",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_limpezas_veiculo_alertas_ciencia_veiculo_id"),
        "limpezas_veiculo_alertas_ciencia",
        ["veiculo_id"],
        unique=False,
    )
    op.create_index(
        "ix_limpeza_alerta_ciencia_veic_ref",
        "limpezas_veiculo_alertas_ciencia",
        ["veiculo_id", "referencia_limpeza_em"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_limpeza_alerta_ciencia_veic_ref", table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_veiculo_id"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_usuario_id"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_referencia_limpeza_em"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_reconhecido_em"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_prazo_dias"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_piloto_id"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_index(op.f("ix_limpezas_veiculo_alertas_ciencia_equipe_id"), table_name="limpezas_veiculo_alertas_ciencia")
    op.drop_table("limpezas_veiculo_alertas_ciencia")
