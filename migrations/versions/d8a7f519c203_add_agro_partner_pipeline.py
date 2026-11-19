"""Parceiros comerciais e histórico de acompanhamento do Agro."""
from alembic import op
import sqlalchemy as sa

revision = 'd8a7f519c203'
down_revision = 'c9e4a7120b65'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('parceiros_agro',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id')),
        sa.Column('chave_unica', sa.String(64), nullable=False, unique=True),
        sa.Column('nome', sa.String(180), nullable=False),
        sa.Column('cidade', sa.String(180), nullable=False),
        sa.Column('telefone', sa.String(100), nullable=False),
        sa.Column('whatsapp', sa.String(100), nullable=False),
        *[sa.Column(k, sa.Text(), nullable=False) for k in ('oportunidade','culturas','abordagem')],
        sa.Column('fontes', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('responsavel', sa.String(180), nullable=False),
        sa.Column('proximo_contato', sa.Date()),
        sa.Column('ultimo_contato', sa.DateTime()),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False))
    for field in ('prefeitura_id','status','proximo_contato'):
        op.create_index('ix_parceiros_agro_'+field, 'parceiros_agro', [field])
    op.create_table('parceiros_agro_historico',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parceiro_id', sa.Integer(), sa.ForeignKey('parceiros_agro.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('autor', sa.String(180), nullable=False),
        sa.Column('acao', sa.String(40), nullable=False),
        sa.Column('status_anterior', sa.String(30)),
        sa.Column('status_novo', sa.String(30), nullable=False),
        sa.Column('observacao', sa.Text(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False))
    op.create_index('ix_parceiros_agro_historico_parceiro_id','parceiros_agro_historico',['parceiro_id'])


def downgrade():
    op.drop_table('parceiros_agro_historico')
    op.drop_table('parceiros_agro')
