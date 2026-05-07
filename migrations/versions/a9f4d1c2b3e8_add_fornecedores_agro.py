"""add fornecedores agro

Revision ID: a9f4d1c2b3e8
Revises: 6e2b1c4d8f90
Create Date: 2026-05-07 10:30:00.000000

"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "a9f4d1c2b3e8"
down_revision = "6e2b1c4d8f90"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _find_fornecedor_id(bind, prefeitura_id, nome, documento):
    if documento:
        row = bind.execute(
            sa.text("SELECT id FROM fornecedores_agro WHERE documento = :documento LIMIT 1"),
            {"documento": documento},
        ).first()
        if row:
            return row[0]

    return bind.execute(
        sa.text(
            """
            SELECT id
              FROM fornecedores_agro
             WHERE lower(nome) = lower(:nome)
               AND (
                    prefeitura_id = :prefeitura_id
                    OR (prefeitura_id IS NULL AND :prefeitura_id IS NULL)
               )
             LIMIT 1
            """
        ),
        {"nome": nome, "prefeitura_id": prefeitura_id},
    ).scalar()


def _backfill_fornecedores_from_saidas(bind):
    if not _table_exists(bind, "financeiro_agro_saidas"):
        return

    saidas_columns = _column_names(bind, "financeiro_agro_saidas")
    if "fornecedor_agro_id" not in saidas_columns:
        return

    rows = bind.execute(
        sa.text(
            """
            SELECT
                s.id,
                s.prefeitura_id,
                s.favorecido,
                s.descricao,
                s.cliente_agro_id,
                s.cep,
                s.logradouro,
                s.numero,
                s.complemento,
                s.bairro,
                s.cidade,
                s.uf,
                c.nome AS cliente_nome,
                c.documento AS cliente_documento,
                c.cep AS cliente_cep,
                c.logradouro AS cliente_logradouro,
                c.numero AS cliente_numero,
                c.complemento AS cliente_complemento,
                c.bairro AS cliente_bairro,
                c.cidade AS cliente_cidade,
                c.uf AS cliente_uf
            FROM financeiro_agro_saidas s
            LEFT JOIN clientes_agro c ON c.id = s.cliente_agro_id
            WHERE s.fornecedor_agro_id IS NULL
            """
        )
    ).mappings()

    for row in rows:
        nome = (row["favorecido"] or row["cliente_nome"] or row["descricao"] or "").strip()
        if not nome:
            continue

        documento = row["cliente_documento"] or None
        fornecedor_id = _find_fornecedor_id(bind, row["prefeitura_id"], nome, documento)
        if fornecedor_id is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO fornecedores_agro (
                        prefeitura_id,
                        documento,
                        nome,
                        cep,
                        logradouro,
                        numero,
                        complemento,
                        bairro,
                        cidade,
                        uf,
                        criado_em
                    ) VALUES (
                        :prefeitura_id,
                        :documento,
                        :nome,
                        :cep,
                        :logradouro,
                        :numero,
                        :complemento,
                        :bairro,
                        :cidade,
                        :uf,
                        :criado_em
                    )
                    """
                ),
                {
                    "prefeitura_id": row["prefeitura_id"],
                    "documento": documento,
                    "nome": nome,
                    "cep": row["cep"] or row["cliente_cep"],
                    "logradouro": row["logradouro"] or row["cliente_logradouro"],
                    "numero": row["numero"] or row["cliente_numero"],
                    "complemento": row["complemento"] or row["cliente_complemento"],
                    "bairro": row["bairro"] or row["cliente_bairro"],
                    "cidade": row["cidade"] or row["cliente_cidade"],
                    "uf": row["uf"] or row["cliente_uf"],
                    "criado_em": datetime.now(),
                },
            )
            fornecedor_id = _find_fornecedor_id(bind, row["prefeitura_id"], nome, documento)

        if fornecedor_id is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE financeiro_agro_saidas
                       SET fornecedor_agro_id = :fornecedor_id
                     WHERE id = :saida_id
                    """
                ),
                {"fornecedor_id": fornecedor_id, "saida_id": row["id"]},
            )


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "fornecedores_agro"):
        op.create_table(
            "fornecedores_agro",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("documento", sa.String(length=50), nullable=True),
            sa.Column("nome", sa.String(length=150), nullable=False),
            sa.Column("cep", sa.String(length=9), nullable=True),
            sa.Column("logradouro", sa.String(length=150), nullable=True),
            sa.Column("numero", sa.String(length=20), nullable=True),
            sa.Column("complemento", sa.String(length=100), nullable=True),
            sa.Column("bairro", sa.String(length=100), nullable=True),
            sa.Column("cidade", sa.String(length=100), nullable=True),
            sa.Column("uf", sa.String(length=2), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("documento"),
        )

    indexes = _index_names(bind, "fornecedores_agro")
    if "ix_fornecedores_agro_id" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_id"), "fornecedores_agro", ["id"], unique=False)
    if "ix_fornecedores_agro_prefeitura_id" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_prefeitura_id"), "fornecedores_agro", ["prefeitura_id"], unique=False)
    if "ix_fornecedores_agro_documento" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_documento"), "fornecedores_agro", ["documento"], unique=True)
    if "ix_fornecedores_agro_nome" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_nome"), "fornecedores_agro", ["nome"], unique=False)
    if "ix_fornecedores_agro_bairro" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_bairro"), "fornecedores_agro", ["bairro"], unique=False)
    if "ix_fornecedores_agro_cidade" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_cidade"), "fornecedores_agro", ["cidade"], unique=False)
    if "ix_fornecedores_agro_uf" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_uf"), "fornecedores_agro", ["uf"], unique=False)
    if "ix_fornecedores_agro_criado_em" not in indexes:
        op.create_index(op.f("ix_fornecedores_agro_criado_em"), "fornecedores_agro", ["criado_em"], unique=False)

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "fornecedor_agro_id" not in columns:
                batch_op.add_column(sa.Column("fornecedor_agro_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_financeiro_agro_saidas_fornecedor_agro_id",
                    "fornecedores_agro",
                    ["fornecedor_agro_id"],
                    ["id"],
                )
                batch_op.create_index(
                    batch_op.f("ix_financeiro_agro_saidas_fornecedor_agro_id"),
                    ["fornecedor_agro_id"],
                    unique=False,
                )

    _backfill_fornecedores_from_saidas(bind)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "fornecedor_agro_id" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_fornecedor_agro_id"))
                batch_op.drop_constraint("fk_financeiro_agro_saidas_fornecedor_agro_id", type_="foreignkey")
                batch_op.drop_column("fornecedor_agro_id")

    if _table_exists(bind, "fornecedores_agro"):
        op.drop_index(op.f("ix_fornecedores_agro_criado_em"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_uf"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_cidade"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_bairro"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_nome"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_documento"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_prefeitura_id"), table_name="fornecedores_agro")
        op.drop_index(op.f("ix_fornecedores_agro_id"), table_name="fornecedores_agro")
        op.drop_table("fornecedores_agro")
