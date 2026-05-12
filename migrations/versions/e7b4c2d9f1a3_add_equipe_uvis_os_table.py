"""add equipe uvis os table

Revision ID: e7b4c2d9f1a3
Revises: d2f4c6b8a9e1
Create Date: 2026-05-12 15:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "e7b4c2d9f1a3"
down_revision = "d2f4c6b8a9e1"
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
    if not _has_table("ordens_servico_equipe_uvis"):
        op.create_table(
            "ordens_servico_equipe_uvis",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("solicitacao_id", sa.Integer(), nullable=False),
            sa.Column("equipe_uvis_nome", sa.String(length=100), nullable=False),
            sa.Column("equipe_id", sa.Integer(), nullable=True),
            sa.Column("identificador_os", sa.String(length=100), nullable=True),
            sa.Column("respondido_por", sa.String(length=150), nullable=True),
            sa.Column("respondido_em", sa.DateTime(), nullable=True),
            sa.Column("situacao_aplicacao", sa.String(length=100), nullable=True),
            sa.Column("tratamento_adicional_realizado", sa.String(length=20), nullable=True),
            sa.Column("quantos_quais", sa.Text(), nullable=True),
            sa.Column("quantidade_produto_administrada_ml", sa.Float(), nullable=True),
            sa.Column("motivo_nao_realizacao", sa.String(length=255), nullable=True),
            sa.Column("larva_visualizada", sa.String(length=20), nullable=True),
            sa.Column("retornar_proxima_semana_monitorar_larvas", sa.String(length=20), nullable=True),
            sa.Column("retorno_monitoramento_em", sa.DateTime(), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
            sa.ForeignKeyConstraint(["solicitacao_id"], ["solicitacoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_id"), "ordens_servico_equipe_uvis", ["id"])
    _create_index_if_missing(
        op.f("ix_ordens_servico_equipe_uvis_solicitacao_id"),
        "ordens_servico_equipe_uvis",
        ["solicitacao_id"],
        unique=True,
    )
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_equipe_uvis_nome"), "ordens_servico_equipe_uvis", ["equipe_uvis_nome"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_equipe_id"), "ordens_servico_equipe_uvis", ["equipe_id"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_identificador_os"), "ordens_servico_equipe_uvis", ["identificador_os"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_respondido_por"), "ordens_servico_equipe_uvis", ["respondido_por"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_respondido_em"), "ordens_servico_equipe_uvis", ["respondido_em"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_situacao_aplicacao"), "ordens_servico_equipe_uvis", ["situacao_aplicacao"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_criado_em"), "ordens_servico_equipe_uvis", ["criado_em"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_atualizado_em"), "ordens_servico_equipe_uvis", ["atualizado_em"])
    _create_index_if_missing(op.f("ix_ordens_servico_equipe_uvis_retorno_monitoramento_em"), "ordens_servico_equipe_uvis", ["retorno_monitoramento_em"])

def downgrade():
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_retorno_monitoramento_em"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_atualizado_em"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_criado_em"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_situacao_aplicacao"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_respondido_em"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_respondido_por"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_identificador_os"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_equipe_id"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_equipe_uvis_nome"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_solicitacao_id"), "ordens_servico_equipe_uvis")
    _drop_index_if_exists(op.f("ix_ordens_servico_equipe_uvis_id"), "ordens_servico_equipe_uvis")
    if _has_table("ordens_servico_equipe_uvis"):
        op.drop_table("ordens_servico_equipe_uvis")
