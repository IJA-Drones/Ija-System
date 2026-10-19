"""Independent syslog delivery state; existing audit rows are the durable queue."""
from alembic import op
import sqlalchemy as sa

revision = 'e4b8c0d129fa'
down_revision = 'd9e4f81b203a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auditoria_syslog_entregas',
        sa.Column('auditoria_id', sa.Integer(), sa.ForeignKey('auditoria_usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('enviado_em', sa.DateTime(), nullable=True),
        sa.Column('tentativas', sa.Integer(), nullable=False),
        sa.Column('proxima_tentativa', sa.DateTime(), nullable=False),
        sa.Column('lease_token', sa.String(36), nullable=True),
        sa.Column('lease_ate', sa.DateTime(), nullable=True),
        sa.Column('ultimo_erro', sa.String(200), nullable=True))


def downgrade():
    op.drop_table('auditoria_syslog_entregas')
