"""Isola os dados financeiros das empresas cadastradas."""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4


revision = "b7d4f2a91c30"
down_revision = "ea54d8c17b20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("financeiro_empresa_perfis") as batch:
        batch.add_column(sa.Column("prefeitura_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_fin_empresa_prefeitura", "prefeituras", ["prefeitura_id"], ["id"])
        batch.create_unique_constraint("uq_fin_empresa_prefeitura", ["prefeitura_id"])
        batch.create_index("ix_financeiro_empresa_perfis_prefeitura_id", ["prefeitura_id"])

    connection = op.get_bind()
    perfis = connection.execute(sa.text(
        "SELECT empresa_slug, nome FROM financeiro_empresa_perfis "
        "WHERE cadastrada = :cadastrada AND empresa_slug <> 'ija' AND prefeitura_id IS NULL"
    ), {"cadastrada": True}).mappings().all()
    for perfil in perfis:
        token = uuid4().hex
        prefeitura_id = connection.execute(sa.text(
            "INSERT INTO prefeituras (nome, slug, ativa, criada_em) "
            "VALUES (:nome, :slug, :ativa, CURRENT_TIMESTAMP) RETURNING id"
        ), {
            "nome": f"Financeiro · {perfil['nome'] or 'Empresa'} · {token[:8]}",
            "slug": f"financeiro-{perfil['empresa_slug']}-{token[:8]}",
            "ativa": True,
        }).scalar_one()
        connection.execute(sa.text(
            "UPDATE financeiro_empresa_perfis SET prefeitura_id = :prefeitura_id "
            "WHERE empresa_slug = :empresa_slug"
        ), {"prefeitura_id": prefeitura_id, "empresa_slug": perfil["empresa_slug"]})

    with op.batch_alter_table("financeiro_agro_competencia_controle") as batch:
        batch.drop_constraint("uq_financeiro_agro_competencia_controle", type_="unique")
        batch.add_column(sa.Column("prefeitura_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_fin_competencia_prefeitura", "prefeituras", ["prefeitura_id"], ["id"])
        batch.create_index("ix_financeiro_agro_competencia_controle_prefeitura_id", ["prefeitura_id"])
        batch.create_unique_constraint(
            "uq_financeiro_agro_competencia_controle",
            ["prefeitura_id", "competencia_ano", "competencia_mes"],
        )


def downgrade():
    with op.batch_alter_table("financeiro_agro_competencia_controle") as batch:
        batch.drop_constraint("uq_financeiro_agro_competencia_controle", type_="unique")
        batch.drop_index("ix_financeiro_agro_competencia_controle_prefeitura_id")
        batch.drop_constraint("fk_fin_competencia_prefeitura", type_="foreignkey")
        batch.drop_column("prefeitura_id")
        batch.create_unique_constraint(
            "uq_financeiro_agro_competencia_controle", ["competencia_ano", "competencia_mes"]
        )

    with op.batch_alter_table("financeiro_empresa_perfis") as batch:
        batch.drop_index("ix_financeiro_empresa_perfis_prefeitura_id")
        batch.drop_constraint("uq_fin_empresa_prefeitura", type_="unique")
        batch.drop_constraint("fk_fin_empresa_prefeitura", type_="foreignkey")
        batch.drop_column("prefeitura_id")
