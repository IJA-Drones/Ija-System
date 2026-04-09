from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str, schema: str = "public") -> bool:
    return conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).scalar() is not None


def _index_exists(conn, index_name: str, schema: str = "public") -> bool:
    return conn.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND indexname = :index_name
            LIMIT 1
            """
        ),
        {"schema": schema, "index_name": index_name},
    ).scalar() is not None


def _constraint_exists(conn, constraint_name: str, schema: str = "public") -> bool:
    return conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_schema = :schema
              AND constraint_name = :constraint_name
            LIMIT 1
            """
        ),
        {"schema": schema, "constraint_name": constraint_name},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "usuarios", "piloto_agro_id"):
        with op.batch_alter_table("usuarios", schema=None) as batch_op:
            batch_op.add_column(sa.Column("piloto_agro_id", sa.Integer(), nullable=True))

    if not _index_exists(conn, "ix_usuarios_piloto_agro_id"):
        op.create_index("ix_usuarios_piloto_agro_id", "usuarios", ["piloto_agro_id"], unique=False)

    if not _constraint_exists(conn, "usuarios_piloto_agro_id_fkey"):
        with op.batch_alter_table("usuarios", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "usuarios_piloto_agro_id_fkey",
                "pilotos_agro",
                ["piloto_agro_id"],
                ["id"],
            )


def downgrade():
    op.execute(sa.text("ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_piloto_agro_id_fkey"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_usuarios_piloto_agro_id"))
    op.execute(sa.text("ALTER TABLE usuarios DROP COLUMN IF EXISTS piloto_agro_id"))
