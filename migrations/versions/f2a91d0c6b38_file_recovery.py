"""Durable recovery of external files after interrupted transactions."""
from alembic import op
import sqlalchemy as sa

revision = 'f2a91d0c6b38'
down_revision = 'e4b8c0d129fa'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('arquivo_operacoes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('backend', sa.String(12), nullable=False),
        sa.Column('destino', sa.Text(), nullable=False),
        sa.Column('identidade', sa.String(255), nullable=False),
        sa.Column('lock_key', sa.BigInteger(), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=False),
        sa.Column('acao', sa.String(10), nullable=False),
        sa.Column('estado', sa.String(16), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('proxima_tentativa', sa.DateTime(), nullable=False),
        sa.Column('tentativas', sa.Integer(), nullable=False),
        sa.Column('ultimo_erro', sa.String(100)),
        sa.Column('concluido_em', sa.DateTime()))
    op.create_index('ix_arquivo_operacoes_pendentes', 'arquivo_operacoes', ['estado', 'proxima_tentativa'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM arquivo_operacoes WHERE estado = 'pendente'")).scalar():
        raise RuntimeError('Existem recuperações pendentes. Resolva e preserve o histórico antes do downgrade.')
    op.drop_table('arquivo_operacoes')
