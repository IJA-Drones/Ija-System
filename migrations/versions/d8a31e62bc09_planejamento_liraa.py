"""Território e planejamento LIRAa; preserva as inspeções existentes.

Revision ID: d8a31e62bc09
Revises: c7f2a9d810e4
"""
from alembic import op
import sqlalchemy as sa

revision = "d8a31e62bc09"
down_revision = "c7f2a9d810e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('vigilancia_campo_quarteiroes',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('bairro', sa.String(length=120), nullable=False),
    sa.Column('area', sa.String(length=80), nullable=False),
    sa.Column('imoveis', sa.Integer(), nullable=False),
    sa.Column('referencia', sa.String(length=200), nullable=False),
    sa.Column('atualizado_por', sa.String(length=80), nullable=False),
    sa.Column('atualizado_em', sa.Float(), nullable=False),
    sa.CheckConstraint('imoveis > 0', name='ck_campo_quarteirao_imoveis'),
    sa.ForeignKeyConstraint(['prefeitura'], ['prefeituras.id'], ),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'code')
    )
    op.create_table('vigilancia_campo_planos',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('titulo', sa.String(length=120), nullable=False),
    sa.Column('inicio', sa.Date(), nullable=False),
    sa.Column('fim', sa.Date(), nullable=False),
    sa.Column('responsavel', sa.String(length=120), nullable=False),
    sa.Column('fonte', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('historico', sa.JSON(), nullable=False),
    sa.CheckConstraint("status IN ('RASCUNHO','LIBERADO','ENCERRADO')", name='ck_campo_plano_status'),
    sa.CheckConstraint('fim >= inicio', name='ck_campo_plano_periodo'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'code'], ['vigilancia_campo_levantamentos.prefeitura', 'vigilancia_campo_levantamentos.demo', 'vigilancia_campo_levantamentos.code'], name='fk_campo_plano_levantamento'),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'code')
    )
    op.create_table('vigilancia_campo_plano_estratos',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('plano', sa.String(length=80), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('imoveis', sa.Integer(), nullable=False),
    sa.Column('meta', sa.Integer(), nullable=False),
    sa.Column('criterio', sa.String(length=200), nullable=False),
    sa.CheckConstraint('imoveis > 0 AND meta > 0 AND meta <= imoveis', name='ck_campo_estrato_meta'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'plano'], ['vigilancia_campo_planos.prefeitura', 'vigilancia_campo_planos.demo', 'vigilancia_campo_planos.code'], name='fk_campo_estrato_plano'),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'plano', 'code')
    )
    op.create_table('vigilancia_campo_plano_quarteiroes',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('plano', sa.String(length=80), nullable=False),
    sa.Column('quarteirao', sa.String(length=80), nullable=False),
    sa.Column('estrato', sa.String(length=80), nullable=False),
    sa.Column('meta', sa.Integer(), nullable=False),
    sa.Column('agente_id', sa.Integer(), nullable=True),
    sa.Column('territorio', sa.JSON(), nullable=False),
    sa.CheckConstraint('meta > 0', name='ck_campo_plano_quarteirao_meta'),
    sa.ForeignKeyConstraint(['agente_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'plano', 'estrato'], ['vigilancia_campo_plano_estratos.prefeitura', 'vigilancia_campo_plano_estratos.demo', 'vigilancia_campo_plano_estratos.plano', 'vigilancia_campo_plano_estratos.code'], name='fk_campo_quarteirao_estrato'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'quarteirao'], ['vigilancia_campo_quarteiroes.prefeitura', 'vigilancia_campo_quarteiroes.demo', 'vigilancia_campo_quarteiroes.code'], name='fk_campo_quarteirao_rg'),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'plano', 'quarteirao')
    )
    op.create_table('vigilancia_campo_plano_visitas',
    sa.Column('prefeitura', sa.Integer(), nullable=False),
    sa.Column('demo', sa.Boolean(), nullable=False),
    sa.Column('origin', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('plano', sa.String(length=80), nullable=False),
    sa.Column('quarteirao', sa.String(length=80), nullable=False),
    sa.Column('autor', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'origin', 'code'], ['vigilancia_campo_inspecoes.prefeitura', 'vigilancia_campo_inspecoes.demo', 'vigilancia_campo_inspecoes.origin', 'vigilancia_campo_inspecoes.code'], name='fk_campo_plano_visita_inspecao'),
    sa.ForeignKeyConstraint(['prefeitura', 'demo', 'plano', 'quarteirao'], ['vigilancia_campo_plano_quarteiroes.prefeitura', 'vigilancia_campo_plano_quarteiroes.demo', 'vigilancia_campo_plano_quarteiroes.plano', 'vigilancia_campo_plano_quarteiroes.quarteirao'], name='fk_campo_plano_visita_quarteirao'),
    sa.PrimaryKeyConstraint('prefeitura', 'demo', 'origin', 'code')
    )


def downgrade():
    op.drop_table("vigilancia_campo_plano_visitas")
    op.drop_table("vigilancia_campo_plano_quarteiroes")
    op.drop_table("vigilancia_campo_plano_estratos")
    op.drop_table("vigilancia_campo_planos")
    op.drop_table("vigilancia_campo_quarteiroes")
