"""Citizen illness reports and their restricted attendance journal."""
from alembic import op
import sqlalchemy as sa

revision = "c94a820d173b"
down_revision = "b72c931ae804"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('relatos_saude',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('prefeitura_id', sa.Integer(), nullable=False),
    sa.Column('uvis_usuario_id', sa.Integer(), nullable=True),
    sa.Column('protocolo', sa.String(length=40), nullable=False),
    sa.Column('envio_id', sa.String(length=64), nullable=False),
    sa.Column('origem_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('cidadao_nome', sa.String(length=150), nullable=False),
    sa.Column('cidadao_telefone', sa.String(length=30), nullable=False),
    sa.Column('logradouro', sa.String(length=150), nullable=False),
    sa.Column('numero', sa.String(length=20), nullable=False),
    sa.Column('bairro', sa.String(length=100), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=False),
    sa.Column('inicio_sintomas', sa.Date(), nullable=True),
    sa.Column('consentimento', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.Column('concluido_em', sa.DateTime(), nullable=True),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['prefeitura_id'], ['prefeituras.id'], ),
    sa.ForeignKeyConstraint(['uvis_usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('envio_id'),
    sa.UniqueConstraint('protocolo')
    )
    op.create_index(op.f('ix_relatos_saude_origem_hash'), 'relatos_saude', ['origem_hash'], unique=False)
    op.create_index(op.f('ix_relatos_saude_prefeitura_id'), 'relatos_saude', ['prefeitura_id'], unique=False)
    op.create_index(op.f('ix_relatos_saude_status'), 'relatos_saude', ['status'], unique=False)
    op.create_index(op.f('ix_relatos_saude_uvis_usuario_id'), 'relatos_saude', ['uvis_usuario_id'], unique=False)
    op.create_table('relatos_saude_eventos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('relato_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('uvis_usuario_id', sa.Integer(), nullable=True),
    sa.Column('responsavel', sa.String(length=150), nullable=False),
    sa.Column('acao', sa.String(length=30), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('observacao', sa.Text(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['relato_id'], ['relatos_saude.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['uvis_usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_relatos_saude_eventos_relato_id'), 'relatos_saude_eventos', ['relato_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_relatos_saude_eventos_relato_id'), table_name='relatos_saude_eventos')
    op.drop_table('relatos_saude_eventos')
    op.drop_index(op.f('ix_relatos_saude_uvis_usuario_id'), table_name='relatos_saude')
    op.drop_index(op.f('ix_relatos_saude_status'), table_name='relatos_saude')
    op.drop_index(op.f('ix_relatos_saude_prefeitura_id'), table_name='relatos_saude')
    op.drop_index(op.f('ix_relatos_saude_origem_hash'), table_name='relatos_saude')
    op.drop_table('relatos_saude')
