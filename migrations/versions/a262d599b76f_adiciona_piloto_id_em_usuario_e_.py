from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "a262d599b76f"
down_revision = "7b93d7f7f030"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str, schema: str = "public") -> bool:
    return conn.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
        """),
        {"schema": schema, "table": table, "column": column},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    # ---- usuarios (se a sua migration também adiciona aqui) ----
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        if not _column_exists(conn, "usuarios", "piloto_id"):
            batch_op.add_column(sa.Column("piloto_id", sa.Integer(), nullable=True))
            # se tiver FK/índice aqui, faça com checagem também

    # ---- solicitacoes ----
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        if not _column_exists(conn, "solicitacoes", "piloto_id"):
            batch_op.add_column(sa.Column("piloto_id", sa.Integer(), nullable=True))
            # se a migration cria FK/índice depois, deixe dentro do mesmo if
            # ou faça checagens de existência (igual você fez com índices)


def downgrade():
    # drops seguros (IF EXISTS)
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS piloto_id"))
    op.execute(sa.text("ALTER TABLE solicitacoes DROP COLUMN IF EXISTS piloto_id"))
