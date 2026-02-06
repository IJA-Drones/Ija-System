"""empty message

Revision ID: 887397110b50
Revises: 78ea473985fd
Create Date: 2026-01-30 10:20:11.796026

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '887397110b50'
down_revision = '78ea473985fd'
branch_labels = None
depends_on = None


# Função para verificar se a coluna existe
def column_exists(conn, table_name, column_name):
    result = conn.execute(text(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name}).fetchone()
    return result is not None

def upgrade():
    conn = op.get_bind()
    
    # Verificar se a coluna já existe
    if not column_exists(conn, 'solicitacoes', 'area_restrita'):
        op.add_column('solicitacoes', sa.Column('area_restrita', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('solicitacoes', 'area_restrita')
