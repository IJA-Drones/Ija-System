"""Durable edit leases and optimistic versions for municipal operations."""
from alembic import op
import sqlalchemy as sa

revision = 'b7f2c9d41e60'
down_revision = 'a6e3f8129c40'
branch_labels = None
depends_on = None
TABLES = ('solicitacoes', 'denuncias', 'ordens_servico', 'ordens_servico_equipe_uvis')


def upgrade():
    for name in TABLES:
        op.add_column(name, sa.Column('versao_edicao', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('edicao_reservas',
        sa.Column('tipo', sa.String(20), primary_key=True),
        sa.Column('objeto_id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('usuario_nome', sa.String(100)),
        sa.Column('token_hash', sa.String(64)),
        sa.Column('expira_em', sa.DateTime()),
        sa.Column('iniciado_em', sa.DateTime()),
        sa.Column('geracao', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_edicao_reservas_expira_em', 'edicao_reservas', ['expira_em'])


def downgrade():
    op.drop_table('edicao_reservas')
    for name in reversed(TABLES):
        with op.batch_alter_table(name) as batch:
            batch.drop_column('versao_edicao')
