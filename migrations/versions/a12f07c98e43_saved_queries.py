"""Personal reusable reporting definitions; no materialized business data."""
from alembic import op
import sqlalchemy as sa
revision = 'a12f07c98e43'
down_revision = 'f2a91d0c6b38'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('consultas_salvas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id')),
        sa.Column('nome', sa.String(100), nullable=False),
        sa.Column('definicao', sa.JSON(), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False))
    op.create_index('ix_consultas_salvas_usuario_id', 'consultas_salvas', ['usuario_id'])
    op.create_index('ix_consultas_salvas_prefeitura_id', 'consultas_salvas', ['prefeitura_id'])

def downgrade():
    op.drop_table('consultas_salvas')
