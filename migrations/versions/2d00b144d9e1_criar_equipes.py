"""criar equipes

Revision ID: 2d00b144d9e1
Revises: 6324a2cd00fc
Create Date: YYYY-MM-DD ...

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "2d00b144d9e1"
down_revision = "6324a2cd00fc"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str, schema: str = "public") -> bool:
    full = f"{schema}.{table_name}"
    return conn.execute(text("SELECT to_regclass(:name)"), {"name": full}).scalar() is not None


def _constraint_exists(conn, constraint_name: str) -> bool:
    return conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
        {"name": constraint_name},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    # 1) equipes (se essa migration também criar "equipes", deixa seguro)
    if not _table_exists(conn, "equipes"):
        op.create_table(
            "equipes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )

    # 2) equipe_pilotos (tabela de vínculo) - segura contra duplicidade
    if not _table_exists(conn, "equipe_pilotos"):
        op.create_table(
            "equipe_pilotos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("equipe_id", sa.Integer(), nullable=False),
            sa.Column("piloto_id", sa.Integer(), nullable=False),
            sa.Column("papel", sa.String(length=20), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
            sa.ForeignKeyConstraint(["piloto_id"], ["pilotos.id"]),
            sa.UniqueConstraint("equipe_id", "papel", name="uq_equipe_papel_unico"),
            sa.UniqueConstraint("equipe_id", "piloto_id", name="uq_equipe_piloto_unico"),
        )
    else:
        # Se a tabela já existe, só garante as constraints (caso faltem)
        if not _constraint_exists(conn, "uq_equipe_papel_unico"):
            op.create_unique_constraint("uq_equipe_papel_unico", "equipe_pilotos", ["equipe_id", "papel"])

        if not _constraint_exists(conn, "uq_equipe_piloto_unico"):
            op.create_unique_constraint("uq_equipe_piloto_unico", "equipe_pilotos", ["equipe_id", "piloto_id"])


def downgrade():
    op.execute("DROP TABLE IF EXISTS equipe_pilotos CASCADE")
    op.execute("DROP TABLE IF EXISTS equipes CASCADE")
