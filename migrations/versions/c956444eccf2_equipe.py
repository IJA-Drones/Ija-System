from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "c956444eccf2"
down_revision = "2d00b144d9e1"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str, schema: str = "public") -> bool:
    return conn.execute(
        text("SELECT to_regclass(:name)"),
        {"name": f"{schema}.{table_name}"},
    ).scalar() is not None


def _constraint_exists(conn, constraint_name: str) -> bool:
    return conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
        {"name": constraint_name},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    # Se essa migration cria equipes também, proteja:
    if not _table_exists(conn, "equipes"):
        op.create_table(
            "equipes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )

    # AQUI o ponto principal: não recriar equipe_pilotos
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
        # tabela já existe → só garante constraints se faltarem
        if not _constraint_exists(conn, "uq_equipe_papel_unico"):
            op.create_unique_constraint(
                "uq_equipe_papel_unico", "equipe_pilotos", ["equipe_id", "papel"]
            )

        if not _constraint_exists(conn, "uq_equipe_piloto_unico"):
            op.create_unique_constraint(
                "uq_equipe_piloto_unico", "equipe_pilotos", ["equipe_id", "piloto_id"]
            )


def downgrade():
    op.execute("DROP TABLE IF EXISTS equipe_pilotos CASCADE")
    op.execute("DROP TABLE IF EXISTS equipes CASCADE")
