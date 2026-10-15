"""Private municipality orthomosaics and durable processing state."""
from alembic import op
import sqlalchemy as sa

revision = 'c8d3e70a192f'
down_revision = 'b7f2c9d41e60'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ortomosaicos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('arquivo_nome', sa.String(255), nullable=False),
        sa.Column('original_path', sa.String(512), nullable=False),
        sa.Column('cog_path', sa.String(512)),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('tamanho_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('metadados', sa.JSON()),
        sa.Column('erro', sa.String(500)),
        sa.Column('processamento_token', sa.String(36)),
        sa.Column('processamento_ate', sa.DateTime()),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False))
    op.create_index('ix_ortomosaicos_prefeitura_id', 'ortomosaicos', ['prefeitura_id'])
    op.create_index('ix_ortomosaicos_status', 'ortomosaicos', ['status'])


def downgrade():
    op.drop_table('ortomosaicos')
