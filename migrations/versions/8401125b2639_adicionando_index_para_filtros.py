from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "8401125b2639"
down_revision = "cfe2d073d2b9"
branch_labels = None
depends_on = None


def _to_regclass(conn, name: str):
    return conn.execute(text("SELECT to_regclass(:name)"), {"name": name}).scalar()


def _index_exists(conn, index_name: str, schema: str = "public") -> bool:
    # tenta com schema e sem schema (cobre search_path diferente)
    return (_to_regclass(conn, f'{schema}.{index_name}') is not None) or (_to_regclass(conn, index_name) is not None)


def upgrade():
    conn = op.get_bind()

    idx_name = op.f("ix_clientes_id")  # mantém compatível com naming convention
    if not _index_exists(conn, idx_name):
        op.create_index(idx_name, "clientes", ["id"], unique=False)


def downgrade():
    idx_name = op.f("ix_clientes_id")
    op.execute(sa.text(f'DROP INDEX IF EXISTS "{idx_name}"'))
