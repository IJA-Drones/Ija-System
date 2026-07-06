"""add support routing to feedback

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-07-02 15:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("suporte_operacional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "usuarios",
        sa.Column("suporte_tecnico", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_usuarios_suporte_operacional"), "usuarios", ["suporte_operacional"], unique=False)
    op.create_index(op.f("ix_usuarios_suporte_tecnico"), "usuarios", ["suporte_tecnico"], unique=False)

    op.add_column("feedback_topicos", sa.Column("setor_suporte", sa.String(length=30), nullable=True))
    op.create_index(op.f("ix_feedback_topicos_setor_suporte"), "feedback_topicos", ["setor_suporte"], unique=False)

    op.execute(
        """
        UPDATE feedback_topicos
        SET setor_suporte = CASE
            WHEN categoria = 'bug' THEN 'tecnico'
            WHEN categoria IN ('processo', 'duvida') THEN 'operacional'
            ELSE setor_suporte
        END
        WHERE setor_suporte IS NULL
        """
    )


def downgrade():
    op.drop_index(op.f("ix_feedback_topicos_setor_suporte"), table_name="feedback_topicos")
    op.drop_column("feedback_topicos", "setor_suporte")

    op.drop_index(op.f("ix_usuarios_suporte_tecnico"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_suporte_operacional"), table_name="usuarios")
    op.drop_column("usuarios", "suporte_tecnico")
    op.drop_column("usuarios", "suporte_operacional")
