"""Municipal report destinations and delivery journal."""
from alembic import op
import sqlalchemy as sa

revision = 'b72c931ae804'
down_revision = 'a12f07c98e43'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('prefeitura_email_config',
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id'), primary_key=True),
        sa.Column('destinatario', sa.String(254), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('atualizado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False))
    op.create_table('consulta_email_envios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('destinatario', sa.String(254), nullable=False),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False))
    op.create_index('ix_consulta_email_envios_prefeitura_id', 'consulta_email_envios', ['prefeitura_id'])


def downgrade():
    op.drop_table('consulta_email_envios')
    op.drop_table('prefeitura_email_config')
