"""piloto: vinculo uvis e os

Revision ID: 6324a2cd00fc
Revises: a262d599b76f
Create Date: YYYY-MM-DD ...

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "6324a2cd00fc"
down_revision = "a262d599b76f"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str, schema: str = "public") -> bool:
    # to_regclass retorna NULL se não existir
    full = f"{schema}.{table_name}"
    return conn.execute(text("SELECT to_regclass(:name)"), {"name": full}).scalar() is not None


def _constraint_exists(conn, constraint_name: str) -> bool:
    return conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
        {"name": constraint_name},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    # ✅ se já existe, não tenta criar de novo
    if not _table_exists(conn, "piloto_uvis"):
        op.create_table(
            "piloto_uvis",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("piloto_id", sa.Integer(), nullable=False),
            sa.Column("uvis_usuario_id", sa.Integer(), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["piloto_id"], ["pilotos.id"]),
            sa.ForeignKeyConstraint(["uvis_usuario_id"], ["usuarios.id"]),
            sa.UniqueConstraint("piloto_id", "uvis_usuario_id", name="uq_piloto_uvis"),
        )
    else:
        # (opcional) garante unique se por algum motivo não existir
        if not _constraint_exists(conn, "uq_piloto_uvis"):
            op.create_unique_constraint(
                "uq_piloto_uvis",
                "piloto_uvis",
                ["piloto_id", "uvis_usuario_id"],
            )


def downgrade():
    # drop seguro
    op.execute("DROP TABLE IF EXISTS piloto_uvis CASCADE")
