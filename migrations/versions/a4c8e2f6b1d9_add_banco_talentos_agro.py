"""add banco de talentos agro

Revision ID: a4c8e2f6b1d9
Revises: f1b2c3d4e5f6
Create Date: 2026-06-11 14:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a4c8e2f6b1d9"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "curriculos_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("criado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=180), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("telefone", sa.String(length=40), nullable=True),
        sa.Column("cidade", sa.String(length=120), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("linkedin", sa.String(length=255), nullable=True),
        sa.Column("titulo_profissional", sa.String(length=180), nullable=True),
        sa.Column("area_principal", sa.String(length=180), nullable=True),
        sa.Column("resumo_perfil", sa.Text(), nullable=True),
        sa.Column("objetivo_profissional", sa.Text(), nullable=True),
        sa.Column("habilidades_tecnicas", sa.JSON(), nullable=False),
        sa.Column("habilidades_comportamentais", sa.JSON(), nullable=False),
        sa.Column("areas_atuacao", sa.JSON(), nullable=False),
        sa.Column("areas_desenvolvimento", sa.JSON(), nullable=False),
        sa.Column("experiencias", sa.JSON(), nullable=False),
        sa.Column("formacoes", sa.JSON(), nullable=False),
        sa.Column("certificacoes", sa.JSON(), nullable=False),
        sa.Column("idiomas", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("analise_status", sa.String(length=30), nullable=False),
        sa.Column("analise_erro", sa.Text(), nullable=True),
        sa.Column("gemini_modelo", sa.String(length=100), nullable=True),
        sa.Column("analisado_em", sa.DateTime(), nullable=True),
        sa.Column("arquivo_nome_original", sa.String(length=255), nullable=False),
        sa.Column("arquivo_mime_type", sa.String(length=100), nullable=False),
        sa.Column("arquivo_tamanho", sa.Integer(), nullable=False),
        sa.Column("arquivo_sha256", sa.String(length=64), nullable=False),
        sa.Column("dropbox_path", sa.String(length=500), nullable=False),
        sa.Column("dropbox_rev", sa.String(length=100), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["criado_por_usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dropbox_path"),
        sa.UniqueConstraint(
            "prefeitura_id",
            "arquivo_sha256",
            name="uq_curriculos_agro_prefeitura_arquivo_sha256",
        ),
    )
    op.create_index(op.f("ix_curriculos_agro_id"), "curriculos_agro", ["id"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_prefeitura_id"), "curriculos_agro", ["prefeitura_id"], unique=False)
    op.create_index(
        op.f("ix_curriculos_agro_criado_por_usuario_id"),
        "curriculos_agro",
        ["criado_por_usuario_id"],
        unique=False,
    )
    op.create_index(op.f("ix_curriculos_agro_nome"), "curriculos_agro", ["nome"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_email"), "curriculos_agro", ["email"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_telefone"), "curriculos_agro", ["telefone"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_cidade"), "curriculos_agro", ["cidade"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_uf"), "curriculos_agro", ["uf"], unique=False)
    op.create_index(
        op.f("ix_curriculos_agro_titulo_profissional"),
        "curriculos_agro",
        ["titulo_profissional"],
        unique=False,
    )
    op.create_index(op.f("ix_curriculos_agro_area_principal"), "curriculos_agro", ["area_principal"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_status"), "curriculos_agro", ["status"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_analise_status"), "curriculos_agro", ["analise_status"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_analisado_em"), "curriculos_agro", ["analisado_em"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_arquivo_sha256"), "curriculos_agro", ["arquivo_sha256"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_criado_em"), "curriculos_agro", ["criado_em"], unique=False)
    op.create_index(op.f("ix_curriculos_agro_atualizado_em"), "curriculos_agro", ["atualizado_em"], unique=False)
    op.create_index(
        "ix_curriculos_agro_status_analise",
        "curriculos_agro",
        ["status", "analise_status"],
        unique=False,
    )
    op.create_index(
        "ix_curriculos_agro_area_criado_em",
        "curriculos_agro",
        ["area_principal", "criado_em"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_curriculos_agro_area_criado_em", table_name="curriculos_agro")
    op.drop_index("ix_curriculos_agro_status_analise", table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_atualizado_em"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_criado_em"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_arquivo_sha256"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_analisado_em"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_analise_status"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_status"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_area_principal"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_titulo_profissional"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_uf"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_cidade"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_telefone"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_email"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_nome"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_criado_por_usuario_id"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_prefeitura_id"), table_name="curriculos_agro")
    op.drop_index(op.f("ix_curriculos_agro_id"), table_name="curriculos_agro")
    op.drop_table("curriculos_agro")
