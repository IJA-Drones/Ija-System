"""add prefeitura scope and prefeitura admin support

Revision ID: b4d1c2e9f301
Revises: 8c1f7e4b2a31
Create Date: 2026-04-06 15:15:00.000000

"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4d1c2e9f301"
down_revision = "8c1f7e4b2a31"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name, column_name):
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name, index_name):
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _has_fk(inspector, table_name, fk_name):
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def _ensure_prefeitura_fk(table_name, fk_name, index_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_col = _has_column(inspector, table_name, "prefeitura_id")
    has_idx = _has_index(inspector, table_name, index_name)
    has_fk = _has_fk(inspector, table_name, fk_name)

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if not has_col:
            batch_op.add_column(sa.Column("prefeitura_id", sa.Integer(), nullable=True))
        if not has_idx:
            batch_op.create_index(index_name, ["prefeitura_id"], unique=False)
        if not has_fk:
            batch_op.create_foreign_key(
                fk_name,
                "prefeituras",
                ["prefeitura_id"],
                ["id"],
            )


def _ensure_prefeituras_table():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("prefeituras"):
        op.create_table(
            "prefeituras",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criada_em", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("nome"),
            sa.UniqueConstraint("slug"),
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "prefeituras", op.f("ix_prefeituras_ativa")):
        op.create_index(op.f("ix_prefeituras_ativa"), "prefeituras", ["ativa"], unique=False)
    if not _has_index(inspector, "prefeituras", op.f("ix_prefeituras_criada_em")):
        op.create_index(op.f("ix_prefeituras_criada_em"), "prefeituras", ["criada_em"], unique=False)
    if not _has_index(inspector, "prefeituras", op.f("ix_prefeituras_nome")):
        op.create_index(op.f("ix_prefeituras_nome"), "prefeituras", ["nome"], unique=False)
    if not _has_index(inspector, "prefeituras", op.f("ix_prefeituras_slug")):
        op.create_index(op.f("ix_prefeituras_slug"), "prefeituras", ["slug"], unique=False)


def _backfill_prefeitura_sao_paulo():
    bind = op.get_bind()

    prefeituras = sa.table(
        "prefeituras",
        sa.column("id", sa.Integer),
        sa.column("nome", sa.String),
        sa.column("slug", sa.String),
        sa.column("ativa", sa.Boolean),
        sa.column("criada_em", sa.DateTime),
    )

    prefeitura_id = bind.execute(
        sa.select(prefeituras.c.id).where(prefeituras.c.slug == "sao-paulo")
    ).scalar()

    if not prefeitura_id:
        bind.execute(
            prefeituras.insert().values(
                nome="Prefeitura de Sao Paulo",
                slug="sao-paulo",
                ativa=True,
                criada_em=datetime.utcnow(),
            )
        )
        prefeitura_id = bind.execute(
            sa.select(prefeituras.c.id).where(prefeituras.c.slug == "sao-paulo")
        ).scalar()

    bind.execute(
        sa.text("UPDATE usuarios SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )

    bind.execute(
        sa.text(
            """
            UPDATE solicitacoes
               SET prefeitura_id = COALESCE(
                   prefeitura_id,
                   (SELECT u.prefeitura_id FROM usuarios u WHERE u.id = solicitacoes.usuario_id)
               )
             WHERE prefeitura_id IS NULL
            """
        )
    )
    bind.execute(
        sa.text("UPDATE solicitacoes SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )

    bind.execute(
        sa.text(
            """
            UPDATE pilotos
               SET prefeitura_id = COALESCE(
                   prefeitura_id,
                   (SELECT u.prefeitura_id FROM usuarios u WHERE u.piloto_id = pilotos.id LIMIT 1)
               )
             WHERE prefeitura_id IS NULL
            """
        )
    )
    bind.execute(
        sa.text("UPDATE pilotos SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )

    bind.execute(
        sa.text("UPDATE clientes SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )
    bind.execute(
        sa.text("UPDATE equipes SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )
    bind.execute(
        sa.text("UPDATE equipamentos SET prefeitura_id = :pid WHERE prefeitura_id IS NULL"),
        {"pid": int(prefeitura_id)},
    )


def upgrade():
    _ensure_prefeituras_table()

    _ensure_prefeitura_fk(
        "usuarios",
        "fk_usuarios_prefeitura_id_prefeituras",
        op.f("ix_usuarios_prefeitura_id"),
    )
    _ensure_prefeitura_fk(
        "solicitacoes",
        "fk_solicitacoes_prefeitura_id_prefeituras",
        op.f("ix_solicitacoes_prefeitura_id"),
    )
    _ensure_prefeitura_fk(
        "pilotos",
        "fk_pilotos_prefeitura_id_prefeituras",
        op.f("ix_pilotos_prefeitura_id"),
    )
    _ensure_prefeitura_fk(
        "clientes",
        "fk_clientes_prefeitura_id_prefeituras",
        op.f("ix_clientes_prefeitura_id"),
    )
    _ensure_prefeitura_fk(
        "equipes",
        "fk_equipes_prefeitura_id_prefeituras",
        op.f("ix_equipes_prefeitura_id"),
    )
    _ensure_prefeitura_fk(
        "equipamentos",
        "fk_equipamentos_prefeitura_id_prefeituras",
        op.f("ix_equipamentos_prefeitura_id"),
    )

    _backfill_prefeitura_sao_paulo()


def downgrade():
    with op.batch_alter_table("equipamentos", schema=None) as batch_op:
        batch_op.drop_constraint("fk_equipamentos_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_equipamentos_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    with op.batch_alter_table("equipes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_equipes_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_equipes_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    with op.batch_alter_table("clientes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_clientes_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_clientes_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    with op.batch_alter_table("pilotos", schema=None) as batch_op:
        batch_op.drop_constraint("fk_pilotos_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_pilotos_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_solicitacoes_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_solicitacoes_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_constraint("fk_usuarios_prefeitura_id_prefeituras", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_usuarios_prefeitura_id"))
        batch_op.drop_column("prefeitura_id")

    op.drop_index(op.f("ix_prefeituras_slug"), table_name="prefeituras")
    op.drop_index(op.f("ix_prefeituras_nome"), table_name="prefeituras")
    op.drop_index(op.f("ix_prefeituras_criada_em"), table_name="prefeituras")
    op.drop_index(op.f("ix_prefeituras_ativa"), table_name="prefeituras")
    op.drop_table("prefeituras")
