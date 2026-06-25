"""add feedback comment attachments

Revision ID: e4b7c9d1f2a3
Revises: d7f4a9c2e1b8
Create Date: 2026-06-25 16:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e4b7c9d1f2a3"
down_revision = "d7f4a9c2e1b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_comentario_anexos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comentario_id", sa.Integer(), nullable=False),
        sa.Column("arquivo_path", sa.String(length=255), nullable=False),
        sa.Column("arquivo_nome", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["comentario_id"], ["feedback_comentarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_comentario_anexos_comentario_id"), "feedback_comentario_anexos", ["comentario_id"], unique=False)
    op.create_index(op.f("ix_feedback_comentario_anexos_criado_em"), "feedback_comentario_anexos", ["criado_em"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_feedback_comentario_anexos_criado_em"), table_name="feedback_comentario_anexos")
    op.drop_index(op.f("ix_feedback_comentario_anexos_comentario_id"), table_name="feedback_comentario_anexos")
    op.drop_table("feedback_comentario_anexos")
