"""Public municipal contacts and publication history."""
from alembic import op
import sqlalchemy as sa
revision = 'd82b46fa910c'
down_revision = 'c94a820d173b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('prefeitura_contatos_publicos',
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id'), primary_key=True),
        sa.Column('publicado', sa.Boolean(), nullable=False),
        *[sa.Column(k, sa.String(n), nullable=False) for k,n in [('telefone',20),('whatsapp',20),('instagram',30),('email',254),('horario',300),('servicos',1500)]],
        sa.Column('versao',sa.Integer(),nullable=False),
        sa.Column('atualizado_por_id',sa.Integer(),sa.ForeignKey('usuarios.id'),nullable=False),
        sa.Column('atualizado_em',sa.DateTime(),nullable=False))
    op.create_table('prefeitura_contatos_historico',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('prefeitura_id',sa.Integer(),sa.ForeignKey('prefeituras.id'),nullable=False),
        sa.Column('usuario_id',sa.Integer(),sa.ForeignKey('usuarios.id'),nullable=False),
        sa.Column('antes',sa.JSON(),nullable=False),sa.Column('depois',sa.JSON(),nullable=False),
        sa.Column('criado_em',sa.DateTime(),nullable=False))
    op.create_index('ix_prefeitura_contatos_historico_prefeitura_id','prefeitura_contatos_historico',['prefeitura_id'])


def downgrade():
    op.drop_index('ix_prefeitura_contatos_historico_prefeitura_id',table_name='prefeitura_contatos_historico')
    op.drop_table('prefeitura_contatos_historico')
    op.drop_table('prefeitura_contatos_publicos')
