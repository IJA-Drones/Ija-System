"""add rd mapeamento agro table

Revision ID: d2f4c6b8a9e1
Revises: c8d9e0f1a2b3
Create Date: 2026-05-11 11:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "d2f4c6b8a9e1"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _existing_indexes(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False):
    if index_name not in _existing_indexes(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str):
    if _has_table(table_name) and index_name in _existing_indexes(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade():
    if not _has_table("rds_mapeamento_agro"):
        op.create_table(
            "rds_mapeamento_agro",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("orcamento_agro_id", sa.Integer(), nullable=False),
            sa.Column("equipe_agro_id", sa.Integer(), nullable=True),
            sa.Column("piloto_agro_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("cliente_nome", sa.String(length=150), nullable=False),
            sa.Column("numero_os", sa.String(length=80), nullable=True),
            sa.Column("propriedade_nome", sa.String(length=150), nullable=False),
            sa.Column("municipio", sa.String(length=100), nullable=False),
            sa.Column("uf", sa.String(length=2), nullable=True),
            sa.Column("proprietario_ou_preposto", sa.String(length=150), nullable=True),
            sa.Column("tipo_servico", sa.String(length=120), nullable=True),
            sa.Column("cultura", sa.String(length=150), nullable=True),
            sa.Column("equipamento", sa.String(length=150), nullable=True),
            sa.Column("altura_voo_m", sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column("area_ha", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("sobreposicao_frontal_pct", sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column("sobreposicao_lateral_pct", sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column("gsd", sa.String(length=50), nullable=True),
            sa.Column("outros", sa.Text(), nullable=True),
            sa.Column("data_relatorio", sa.Date(), nullable=True),
            sa.Column("rede_energia_baixa", sa.String(length=3), nullable=True),
            sa.Column("rede_energia_alta_media", sa.String(length=3), nullable=True),
            sa.Column("poste", sa.String(length=3), nullable=True),
            sa.Column("poste_com_tirante", sa.String(length=3), nullable=True),
            sa.Column("acesso_area", sa.String(length=3), nullable=True),
            sa.Column("arvores_secas", sa.String(length=3), nullable=True),
            sa.Column("outros_area", sa.Text(), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("responsavel_nome", sa.String(length=150), nullable=True),
            sa.Column("enviado_em", sa.DateTime(), nullable=False),
            sa.Column("preenchido_em", sa.DateTime(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["equipe_agro_id"], ["equipes_agro.id"]),
            sa.ForeignKeyConstraint(["orcamento_agro_id"], ["orcamentos_agro.id"]),
            sa.ForeignKeyConstraint(["piloto_agro_id"], ["pilotos_agro.id"]),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_atualizado_em"), "rds_mapeamento_agro", ["atualizado_em"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_cliente_nome"), "rds_mapeamento_agro", ["cliente_nome"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_criado_em"), "rds_mapeamento_agro", ["criado_em"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_data_relatorio"), "rds_mapeamento_agro", ["data_relatorio"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_enviado_em"), "rds_mapeamento_agro", ["enviado_em"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_equipe_agro_id"), "rds_mapeamento_agro", ["equipe_agro_id"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_id"), "rds_mapeamento_agro", ["id"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_municipio"), "rds_mapeamento_agro", ["municipio"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_numero_os"), "rds_mapeamento_agro", ["numero_os"])
    _create_index_if_missing(
        op.f("ix_rds_mapeamento_agro_orcamento_agro_id"),
        "rds_mapeamento_agro",
        ["orcamento_agro_id"],
        unique=True,
    )
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_piloto_agro_id"), "rds_mapeamento_agro", ["piloto_agro_id"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_preenchido_em"), "rds_mapeamento_agro", ["preenchido_em"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_prefeitura_id"), "rds_mapeamento_agro", ["prefeitura_id"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_propriedade_nome"), "rds_mapeamento_agro", ["propriedade_nome"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_status"), "rds_mapeamento_agro", ["status"])
    _create_index_if_missing(op.f("ix_rds_mapeamento_agro_uf"), "rds_mapeamento_agro", ["uf"])
    _create_index_if_missing("ix_rd_mapeamento_orcamento_status", "rds_mapeamento_agro", ["orcamento_agro_id", "status"])
    _create_index_if_missing("ix_rd_mapeamento_status_equipe", "rds_mapeamento_agro", ["status", "equipe_agro_id"])


def downgrade():
    _drop_index_if_exists("ix_rd_mapeamento_status_equipe", "rds_mapeamento_agro")
    _drop_index_if_exists("ix_rd_mapeamento_orcamento_status", "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_uf"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_status"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_propriedade_nome"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_prefeitura_id"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_preenchido_em"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_piloto_agro_id"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_orcamento_agro_id"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_numero_os"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_municipio"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_id"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_equipe_agro_id"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_enviado_em"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_data_relatorio"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_criado_em"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_cliente_nome"), "rds_mapeamento_agro")
    _drop_index_if_exists(op.f("ix_rds_mapeamento_agro_atualizado_em"), "rds_mapeamento_agro")
    if _has_table("rds_mapeamento_agro"):
        op.drop_table("rds_mapeamento_agro")
