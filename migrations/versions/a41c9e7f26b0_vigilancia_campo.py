"""Persistência Focal/LIRAa no banco do IJA.

Revision ID: a41c9e7f26b0
Revises: d9e4f81b203a
"""
from alembic import op
import sqlalchemy as sa

revision = "a41c9e7f26b0"
down_revision = "d9e4f81b203a"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('vigilancia_campo_lotes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('actor', sa.String(length=80), nullable=False),
    sa.Column('source', sa.String(length=120), nullable=False),
    sa.Column('filename', sa.String(length=120), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('layout', sa.String(length=80), nullable=False),
    sa.Column('original', sa.LargeBinary(), nullable=False),
    sa.Column('created', sa.Float(), nullable=False),
    sa.Column('confirmed', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('report', sa.JSON(), nullable=False),
    sa.Column('inserted', sa.Integer(), server_default='0', nullable=False),
    sa.Column('reused', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("status IN ('VALIDADO','REJEITADO','CONCLUIDO')", name='ck_campo_lote_status'),
    sa.ForeignKeyConstraint(['prefeitura'], ['prefeituras.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'prefeitura', 'demo', name='uq_campo_lote_escopo'),
    sa.UniqueConstraint('prefeitura', 'demo', 'actor', 'sha256', 'source', name='uq_campo_lote_origem')
    )
    op.create_index('ix_campo_lote_prefeitura_data', 'vigilancia_campo_lotes', ['prefeitura', 'created'], unique=False)
    op.create_table('vigilancia_campo_imoveis',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('bairro', sa.String(length=120), nullable=False),
    sa.Column('area', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['prefeitura'], ['prefeituras.id'], ),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'code')
    )
    op.create_table('vigilancia_campo_levantamentos',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['prefeitura'], ['prefeituras.id'], ),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'code')
    )
    op.create_table('vigilancia_campo_inspecoes',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('origin', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('property_code', sa.String(length=80), nullable=False),
    sa.Column('survey_code', sa.String(length=80), nullable=True),
    sa.Column('stratum', sa.String(length=80), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'property_code'], ['vigilancia_campo_imoveis.prefeitura', 'vigilancia_campo_imoveis.demo', 'vigilancia_campo_imoveis.code'], name='fk_campo_inspecao_imovel'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'survey_code'], ['vigilancia_campo_levantamentos.prefeitura', 'vigilancia_campo_levantamentos.demo', 'vigilancia_campo_levantamentos.code'], name='fk_campo_inspecao_levantamento'),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'origin', 'code')
    )
    op.create_table('vigilancia_campo_lote_inspecoes',
    sa.Column('batch_id', sa.String(length=32), nullable=False),
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('origin', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('source_line', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id', 'prefeitura', 'demo'], ['vigilancia_campo_lotes.id', 'vigilancia_campo_lotes.prefeitura', 'vigilancia_campo_lotes.demo'], name='fk_campo_lote_inspecao_lote'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'origin', 'code'], ['vigilancia_campo_inspecoes.prefeitura', 'vigilancia_campo_inspecoes.demo', 'vigilancia_campo_inspecoes.origin', 'vigilancia_campo_inspecoes.code'], name='fk_campo_lote_inspecao_registro'),
    sa.PrimaryKeyConstraint('batch_id', 'origin', 'code')
    )


def downgrade():
    op.drop_table('vigilancia_campo_lote_inspecoes')
    op.drop_table('vigilancia_campo_inspecoes')
    op.drop_table('vigilancia_campo_levantamentos')
    op.drop_table('vigilancia_campo_imoveis')
    op.drop_table('vigilancia_campo_lotes')
