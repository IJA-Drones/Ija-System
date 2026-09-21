"""add denuncias portal cidadao

Revision ID: 2f6b8d1c9a43
Revises: a6d4e2b8c9f1
Create Date: 2026-09-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2f6b8d1c9a43"
down_revision = "a6d4e2b8c9f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "denuncias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("protocolo", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("tipo_visita", sa.String(length=50), nullable=False),
        sa.Column("tipo_imovel", sa.String(length=30), nullable=True),
        sa.Column("foco", sa.String(length=80), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("cep", sa.String(length=9), nullable=True),
        sa.Column("logradouro", sa.String(length=150), nullable=False),
        sa.Column("numero", sa.String(length=20), nullable=False),
        sa.Column("complemento", sa.String(length=100), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=False),
        sa.Column("cidade", sa.String(length=100), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.String(length=50), nullable=True),
        sa.Column("longitude", sa.String(length=50), nullable=True),
        sa.Column("place_id", sa.String(length=255), nullable=True),
        sa.Column("cidadao_nome", sa.String(length=150), nullable=False),
        sa.Column("cidadao_cpf", sa.String(length=14), nullable=False),
        sa.Column("cidadao_rg", sa.String(length=30), nullable=False),
        sa.Column("cidadao_telefone", sa.String(length=30), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("coordenadoria", sa.String(length=100), nullable=True),
        sa.Column("uvis_usuario_id", sa.Integer(), nullable=True),
        sa.Column("solicitacao_id", sa.Integer(), nullable=True),
        sa.Column("ip_origem", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("consentimento", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.ForeignKeyConstraint(["solicitacao_id"], ["solicitacoes.id"]),
        sa.ForeignKeyConstraint(["uvis_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocolo"),
        sa.UniqueConstraint("solicitacao_id"),
    )
    op.create_index(op.f("ix_denuncias_bairro"), "denuncias", ["bairro"], unique=False)
    op.create_index(op.f("ix_denuncias_cep"), "denuncias", ["cep"], unique=False)
    op.create_index(op.f("ix_denuncias_cidade"), "denuncias", ["cidade"], unique=False)
    op.create_index(op.f("ix_denuncias_cidadao_cpf"), "denuncias", ["cidadao_cpf"], unique=False)
    op.create_index(op.f("ix_denuncias_cidadao_rg"), "denuncias", ["cidadao_rg"], unique=False)
    op.create_index(op.f("ix_denuncias_coordenadoria"), "denuncias", ["coordenadoria"], unique=False)
    op.create_index(op.f("ix_denuncias_criado_em"), "denuncias", ["criado_em"], unique=False)
    op.create_index(op.f("ix_denuncias_fluxo"), "denuncias", ["coordenadoria", "uvis_usuario_id", "status"], unique=False)
    op.create_index(op.f("ix_denuncias_foco"), "denuncias", ["foco"], unique=False)
    op.create_index(op.f("ix_denuncias_localizacao"), "denuncias", ["cidade", "uf", "bairro"], unique=False)
    op.create_index(op.f("ix_denuncias_place_id"), "denuncias", ["place_id"], unique=False)
    op.create_index(op.f("ix_denuncias_prefeitura_id"), "denuncias", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_denuncias_protocolo"), "denuncias", ["protocolo"], unique=True)
    op.create_index(op.f("ix_denuncias_solicitacao_id"), "denuncias", ["solicitacao_id"], unique=True)
    op.create_index(op.f("ix_denuncias_status"), "denuncias", ["status"], unique=False)
    op.create_index(op.f("ix_denuncias_status_criado"), "denuncias", ["status", "criado_em"], unique=False)
    op.create_index(op.f("ix_denuncias_tipo_imovel"), "denuncias", ["tipo_imovel"], unique=False)
    op.create_index(op.f("ix_denuncias_tipo_visita"), "denuncias", ["tipo_visita"], unique=False)
    op.create_index(op.f("ix_denuncias_uf"), "denuncias", ["uf"], unique=False)
    op.create_index(op.f("ix_denuncias_uvis_usuario_id"), "denuncias", ["uvis_usuario_id"], unique=False)

    op.create_table(
        "denuncia_anexos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("denuncia_id", sa.Integer(), nullable=False),
        sa.Column("arquivo_path", sa.String(length=255), nullable=False),
        sa.Column("arquivo_nome", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
        sa.Column("tipo_midia", sa.String(length=20), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["denuncia_id"], ["denuncias.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_denuncia_anexos_criado_em"), "denuncia_anexos", ["criado_em"], unique=False)
    op.create_index(op.f("ix_denuncia_anexos_denuncia_id"), "denuncia_anexos", ["denuncia_id"], unique=False)
    op.create_index(op.f("ix_denuncia_anexos_tipo_midia"), "denuncia_anexos", ["tipo_midia"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_denuncia_anexos_tipo_midia"), table_name="denuncia_anexos")
    op.drop_index(op.f("ix_denuncia_anexos_denuncia_id"), table_name="denuncia_anexos")
    op.drop_index(op.f("ix_denuncia_anexos_criado_em"), table_name="denuncia_anexos")
    op.drop_table("denuncia_anexos")
    op.drop_index(op.f("ix_denuncias_uvis_usuario_id"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_uf"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_tipo_visita"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_tipo_imovel"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_status_criado"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_status"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_solicitacao_id"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_protocolo"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_prefeitura_id"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_place_id"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_localizacao"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_foco"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_fluxo"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_criado_em"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_coordenadoria"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_cidadao_rg"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_cidadao_cpf"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_cidade"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_cep"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_bairro"), table_name="denuncias")
    op.drop_table("denuncias")
