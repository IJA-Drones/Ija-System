"""Ações realizadas: rascunho, publicação aprovada, mídias e histórico.

Revision ID: a73e5c9b204f
Revises: f2a6d9c1074e
"""
from alembic import op
import sqlalchemy as sa

revision = 'a73e5c9b204f'
down_revision = 'f2a6d9c1074e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('acoes_publicas',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('prefeitura_id', sa.Integer(), sa.ForeignKey('prefeituras.id'), nullable=False),
        sa.Column('origem_os_id', sa.Integer(), sa.ForeignKey('solicitacoes.id', ondelete='SET NULL')),
        sa.Column('demo', sa.Boolean(), nullable=False),
        sa.Column('titulo', sa.String(160), nullable=False),
        sa.Column('tipo', sa.String(30), nullable=False),
        sa.Column('bairro', sa.String(120), nullable=False),
        sa.Column('inicio', sa.Date(), nullable=False),
        sa.Column('fim', sa.Date(), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('publicado', sa.Boolean(), nullable=False),
        sa.Column('publicacao', sa.JSON()),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('criado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('publicado_em', sa.DateTime()),
        sa.CheckConstraint("status IN ('RASCUNHO','EM_REVISAO','PUBLICADO','RETIRADO')", name='ck_acoes_publicas_status'),
        sa.CheckConstraint('fim >= inicio', name='ck_acoes_publicas_periodo'),
        sa.UniqueConstraint('id', 'prefeitura_id', name='uq_acoes_publicas_municipio'))
    op.create_index('ix_acoes_publicas_municipio_demo', 'acoes_publicas', ['prefeitura_id', 'demo', 'atualizado_em'])
    op.create_index('ix_acoes_publicas_publicadas', 'acoes_publicas', ['publicado', 'demo', 'publicado_em'])
    op.create_table('acoes_publicas_midias',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('acao_id', sa.String(32), nullable=False),
        sa.Column('prefeitura_id', sa.Integer(), nullable=False),
        sa.Column('stored_path', sa.String(512), nullable=False),
        sa.Column('mime', sa.String(40), nullable=False),
        sa.Column('legenda', sa.String(240), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('tamanho', sa.Integer(), nullable=False),
        sa.Column('selecionada', sa.Boolean(), nullable=False),
        sa.Column('criado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['acao_id', 'prefeitura_id'], ['acoes_publicas.id', 'acoes_publicas.prefeitura_id'], name='fk_acao_midia_municipio'))
    op.create_index('ix_acoes_midias_acao', 'acoes_publicas_midias', ['acao_id'])
    op.create_table('acoes_publicas_eventos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('acao_id', sa.String(32), nullable=False),
        sa.Column('prefeitura_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('usuario_nome', sa.String(150), nullable=False),
        sa.Column('evento', sa.String(30), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('conteudo', sa.JSON(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['acao_id', 'prefeitura_id'], ['acoes_publicas.id', 'acoes_publicas.prefeitura_id'], name='fk_acao_evento_municipio'))
    op.create_index('ix_acoes_eventos_acao', 'acoes_publicas_eventos', ['acao_id', 'id'])


def downgrade():
    op.drop_index('ix_acoes_eventos_acao', table_name='acoes_publicas_eventos')
    op.drop_table('acoes_publicas_eventos')
    op.drop_index('ix_acoes_midias_acao', table_name='acoes_publicas_midias')
    op.drop_table('acoes_publicas_midias')
    op.drop_index('ix_acoes_publicas_publicadas', table_name='acoes_publicas')
    op.drop_index('ix_acoes_publicas_municipio_demo', table_name='acoes_publicas')
    op.drop_table('acoes_publicas')
