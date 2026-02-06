from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '78ea473985fd'
down_revision = '937343e3998a'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str, schema: str = 'public') -> bool:
    # Verifica se a coluna já existe
    result = conn.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
        """),
        {"schema": schema, "table": table, "column": column}
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()

    # Verifica se a coluna 'nome_equipe' já existe
    if not _column_exists(conn, 'equipe_uvis', 'nome_equipe'):
        op.add_column('equipe_uvis', sa.Column('nome_equipe', sa.String(length=100), nullable=False))


def downgrade():
    # Se necessário, remova a coluna durante o downgrade
    op.drop_column('equipe_uvis', 'nome_equipe')
