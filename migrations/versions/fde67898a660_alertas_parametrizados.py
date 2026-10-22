"""alertas parametrizados e dispositivos push

Revision ID: fde67898a660
Revises: a1d2e3f4b5c6
"""
from alembic import op
import sqlalchemy as sa

revision = "fde67898a660"
down_revision = "a1d2e3f4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("alertas_dispositivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=True, index=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True, index=True),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("subscription", sa.JSON(), nullable=False),
        sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()),
        sa.Column("bairro", sa.String(100)), sa.Column("user_agent", sa.String(255)),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("falhas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False), sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    )
    op.create_table("alertas_regras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False, index=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("fonte", sa.String(20), nullable=False),
        sa.Column("bairro", sa.String(100)),
        sa.Column("janela_dias", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("limiar", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("raio_km", sa.Float(), nullable=False, server_default="2"),
        sa.Column("intervalo_horas", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("notificar_app", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notificar_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notificar_push", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("emails", sa.Text()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("ultimo_disparo_em", sa.DateTime()),
    )
    op.create_table("alertas_disparos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("regra_id", sa.Integer(), sa.ForeignKey("alertas_regras.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False, index=True),
        sa.Column("valor", sa.Integer(), nullable=False), sa.Column("limiar", sa.Integer(), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("bairro", sa.String(100)), sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()),
        sa.Column("teste", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, index=True),
    )


def downgrade():
    op.drop_table("alertas_disparos")
    op.drop_table("alertas_regras")
    op.drop_table("alertas_dispositivos")
