"""add feedback central

Revision ID: d7f4a9c2e1b8
Revises: a4c8e2f6b1d9
Create Date: 2026-06-25 15:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d7f4a9c2e1b8"
down_revision = "a4c8e2f6b1d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_topicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("uvis_usuario_id", sa.Integer(), nullable=False),
        sa.Column("uvis_nome", sa.String(length=100), nullable=False),
        sa.Column("regiao", sa.String(length=50), nullable=True),
        sa.Column("criado_por_id", sa.Integer(), nullable=False),
        sa.Column("criado_por_nome", sa.String(length=100), nullable=False),
        sa.Column("criado_por_tipo", sa.String(length=20), nullable=True),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("prioridade", sa.String(length=20), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=True),
        sa.Column("resolvido_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.ForeignKeyConstraint(["responsavel_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["uvis_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_topicos_atualizado_em"), "feedback_topicos", ["atualizado_em"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_categoria"), "feedback_topicos", ["categoria"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_criado_em"), "feedback_topicos", ["criado_em"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_criado_por_id"), "feedback_topicos", ["criado_por_id"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_criado_por_tipo"), "feedback_topicos", ["criado_por_tipo"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_prefeitura_id"), "feedback_topicos", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_prioridade"), "feedback_topicos", ["prioridade"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_regiao"), "feedback_topicos", ["regiao"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_resolvido_em"), "feedback_topicos", ["resolvido_em"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_responsavel_id"), "feedback_topicos", ["responsavel_id"], unique=False)
    op.create_index("ix_feedback_topicos_scope", "feedback_topicos", ["prefeitura_id", "regiao", "uvis_usuario_id"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_status"), "feedback_topicos", ["status"], unique=False)
    op.create_index("ix_feedback_topicos_status_updated", "feedback_topicos", ["status", "atualizado_em"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_titulo"), "feedback_topicos", ["titulo"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_uvis_nome"), "feedback_topicos", ["uvis_nome"], unique=False)
    op.create_index(op.f("ix_feedback_topicos_uvis_usuario_id"), "feedback_topicos", ["uvis_usuario_id"], unique=False)

    op.create_table(
        "feedback_comentarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topico_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("usuario_nome", sa.String(length=100), nullable=False),
        sa.Column("usuario_tipo", sa.String(length=20), nullable=True),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("interno", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["topico_id"], ["feedback_topicos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_comentarios_criado_em"), "feedback_comentarios", ["criado_em"], unique=False)
    op.create_index(op.f("ix_feedback_comentarios_interno"), "feedback_comentarios", ["interno"], unique=False)
    op.create_index(op.f("ix_feedback_comentarios_topico_id"), "feedback_comentarios", ["topico_id"], unique=False)
    op.create_index(op.f("ix_feedback_comentarios_usuario_id"), "feedback_comentarios", ["usuario_id"], unique=False)
    op.create_index(op.f("ix_feedback_comentarios_usuario_tipo"), "feedback_comentarios", ["usuario_tipo"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_feedback_comentarios_usuario_tipo"), table_name="feedback_comentarios")
    op.drop_index(op.f("ix_feedback_comentarios_usuario_id"), table_name="feedback_comentarios")
    op.drop_index(op.f("ix_feedback_comentarios_topico_id"), table_name="feedback_comentarios")
    op.drop_index(op.f("ix_feedback_comentarios_interno"), table_name="feedback_comentarios")
    op.drop_index(op.f("ix_feedback_comentarios_criado_em"), table_name="feedback_comentarios")
    op.drop_table("feedback_comentarios")

    op.drop_index(op.f("ix_feedback_topicos_uvis_usuario_id"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_uvis_nome"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_titulo"), table_name="feedback_topicos")
    op.drop_index("ix_feedback_topicos_status_updated", table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_status"), table_name="feedback_topicos")
    op.drop_index("ix_feedback_topicos_scope", table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_responsavel_id"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_resolvido_em"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_regiao"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_prioridade"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_prefeitura_id"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_criado_por_tipo"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_criado_por_id"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_criado_em"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_categoria"), table_name="feedback_topicos")
    op.drop_index(op.f("ix_feedback_topicos_atualizado_em"), table_name="feedback_topicos")
    op.drop_table("feedback_topicos")
