"""vínculo do Telegram por usuário e canal Telegram nos alertas

Revision ID: a880745899f8
Revises: 9c5309bacdd0
"""
from alembic import op
import sqlalchemy as sa

revision = "a880745899f8"
down_revision = "9c5309bacdd0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("telegram_chat_id", sa.String(32), nullable=True))
    op.add_column("usuarios", sa.Column("telegram_codigo", sa.String(40), nullable=True))
    op.create_index("ix_usuarios_telegram_chat_id", "usuarios", ["telegram_chat_id"])
    op.add_column("alertas_regras", sa.Column("notificar_telegram", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("alertas_regras", "notificar_telegram")
    op.drop_index("ix_usuarios_telegram_chat_id", table_name="usuarios")
    op.drop_column("usuarios", "telegram_codigo")
    op.drop_column("usuarios", "telegram_chat_id")
