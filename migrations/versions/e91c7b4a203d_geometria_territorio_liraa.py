"""Contorno opcional do quarteirão selecionado no mapa.

Revision ID: e91c7b4a203d
Revises: d8a31e62bc09
"""
from alembic import op
import sqlalchemy as sa

revision = "e91c7b4a203d"
down_revision = "d8a31e62bc09"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vigilancia_campo_quarteiroes", sa.Column("geometria", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("vigilancia_campo_quarteiroes", "geometria")
