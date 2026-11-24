"""Oculta tenants financeiros de todos os catálogos municipais públicos."""

from alembic import op
import sqlalchemy as sa


revision = "c81f0e2a4d67"
down_revision = "b7d4f2a91c30"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE prefeituras SET ativa = FALSE WHERE id IN ("
        "SELECT prefeitura_id FROM financeiro_empresa_perfis WHERE prefeitura_id IS NOT NULL"
        ")"
    ))


def downgrade():
    # Não reativa automaticamente registros municipais: o estado anterior pode
    # ter sido inativo por outros motivos administrativos.
    pass
