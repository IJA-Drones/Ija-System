"""adiciona retorno automatico em solicitacoes

Revision ID: 474b4b2bccd6
Revises: a44146ee66f1
Create Date: 2026-03-16 09:49:54.768555

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '474b4b2bccd6'
down_revision = 'a44146ee66f1'
branch_labels = None
depends_on = None


def upgrade():
    # 1) adiciona colunas sem forcar NOT NULL de imediato
    with op.batch_alter_table('solicitacoes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('origem_retorno_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('gerada_automaticamente', sa.Boolean(), nullable=True))

    # 2) preenche registros antigos
    op.execute(
        "UPDATE solicitacoes "
        "SET gerada_automaticamente = FALSE "
        "WHERE gerada_automaticamente IS NULL"
    )

    # 3) aplica restricoes e indices
    with op.batch_alter_table('solicitacoes', schema=None) as batch_op:
        batch_op.alter_column(
            'gerada_automaticamente',
            existing_type=sa.Boolean(),
            nullable=False
        )
        batch_op.create_index(
            batch_op.f('ix_solicitacoes_gerada_automaticamente'),
            ['gerada_automaticamente'],
            unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_solicitacoes_origem_retorno_id'),
            ['origem_retorno_id'],
            unique=False
        )
        batch_op.create_foreign_key(
            'fk_solicitacoes_origem_retorno_id',
            'solicitacoes',
            ['origem_retorno_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('solicitacoes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_solicitacoes_origem_retorno_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_solicitacoes_origem_retorno_id'))
        batch_op.drop_index(batch_op.f('ix_solicitacoes_gerada_automaticamente'))
        batch_op.drop_column('gerada_automaticamente')
        batch_op.drop_column('origem_retorno_id')