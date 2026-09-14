"""add RedGPS tracking tables

Revision ID: b7c1e4f2a9d6
Revises: a6d4e2b8c9f1
Create Date: 2026-09-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c1e4f2a9d6"
down_revision = "a6d4e2b8c9f1"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return sa.inspect(bind).has_table(table_name)


def upgrade():
    bind = op.get_bind()
    if _table_exists(bind, "rastreamento_posicoes"):
        return

    op.create_table(
        "rastreamento_posicoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("velocidade_kmh", sa.Float(), nullable=True),
        sa.Column("ignicao", sa.Boolean(), nullable=True),
        sa.Column("hodometro_km", sa.Float(), nullable=True),
        sa.Column("endereco", sa.String(length=255), nullable=True),
        sa.Column("reportado_em", sa.DateTime(), nullable=False),
        sa.Column("provedor", sa.String(length=40), nullable=False, server_default="RedGPS"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chave_fixture", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_fixture", name="uq_rastreamento_posicoes_chave_fixture"),
    )
    op.create_index("ix_rastreamento_posicoes_id", "rastreamento_posicoes", ["id"], unique=False)
    op.create_index("ix_rastreamento_posicoes_veiculo_id", "rastreamento_posicoes", ["veiculo_id"], unique=False)
    op.create_index("ix_rastreamento_posicoes_prefeitura_id", "rastreamento_posicoes", ["prefeitura_id"], unique=False)
    op.create_index("ix_rastreamento_posicoes_reportado_em", "rastreamento_posicoes", ["reportado_em"], unique=False)
    op.create_index("ix_rastreamento_posicoes_provedor", "rastreamento_posicoes", ["provedor"], unique=False)
    op.create_index("ix_rastreamento_posicoes_is_demo", "rastreamento_posicoes", ["is_demo"], unique=False)
    op.create_index("ix_rastreamento_posicoes_chave_fixture", "rastreamento_posicoes", ["chave_fixture"], unique=False)
    op.create_index("ix_rastreamento_posicoes_veiculo_reportado", "rastreamento_posicoes", ["veiculo_id", "reportado_em"], unique=False)

    op.create_table(
        "rastreamento_historicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("velocidade_kmh", sa.Float(), nullable=True),
        sa.Column("ignicao", sa.Boolean(), nullable=True),
        sa.Column("hodometro_km", sa.Float(), nullable=True),
        sa.Column("reportado_em", sa.DateTime(), nullable=False),
        sa.Column("provedor", sa.String(length=40), nullable=False, server_default="RedGPS"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chave_fixture", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_fixture", name="uq_rastreamento_historicos_chave_fixture"),
    )
    op.create_index("ix_rastreamento_historicos_id", "rastreamento_historicos", ["id"], unique=False)
    op.create_index("ix_rastreamento_historicos_veiculo_id", "rastreamento_historicos", ["veiculo_id"], unique=False)
    op.create_index("ix_rastreamento_historicos_prefeitura_id", "rastreamento_historicos", ["prefeitura_id"], unique=False)
    op.create_index("ix_rastreamento_historicos_reportado_em", "rastreamento_historicos", ["reportado_em"], unique=False)
    op.create_index("ix_rastreamento_historicos_provedor", "rastreamento_historicos", ["provedor"], unique=False)
    op.create_index("ix_rastreamento_historicos_is_demo", "rastreamento_historicos", ["is_demo"], unique=False)
    op.create_index("ix_rastreamento_historicos_chave_fixture", "rastreamento_historicos", ["chave_fixture"], unique=False)
    op.create_index("ix_rastreamento_historicos_veiculo_reportado", "rastreamento_historicos", ["veiculo_id", "reportado_em"], unique=False)

    op.create_table(
        "rastreamento_alertas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False, server_default="media"),
        sa.Column("mensagem", sa.String(length=255), nullable=False),
        sa.Column("reportado_em", sa.DateTime(), nullable=False),
        sa.Column("resolvido", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provedor", sa.String(length=40), nullable=False, server_default="RedGPS"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chave_fixture", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_fixture", name="uq_rastreamento_alertas_chave_fixture"),
    )
    op.create_index("ix_rastreamento_alertas_id", "rastreamento_alertas", ["id"], unique=False)
    op.create_index("ix_rastreamento_alertas_veiculo_id", "rastreamento_alertas", ["veiculo_id"], unique=False)
    op.create_index("ix_rastreamento_alertas_prefeitura_id", "rastreamento_alertas", ["prefeitura_id"], unique=False)
    op.create_index("ix_rastreamento_alertas_tipo", "rastreamento_alertas", ["tipo"], unique=False)
    op.create_index("ix_rastreamento_alertas_severidade", "rastreamento_alertas", ["severidade"], unique=False)
    op.create_index("ix_rastreamento_alertas_reportado_em", "rastreamento_alertas", ["reportado_em"], unique=False)
    op.create_index("ix_rastreamento_alertas_resolvido", "rastreamento_alertas", ["resolvido"], unique=False)
    op.create_index("ix_rastreamento_alertas_provedor", "rastreamento_alertas", ["provedor"], unique=False)
    op.create_index("ix_rastreamento_alertas_is_demo", "rastreamento_alertas", ["is_demo"], unique=False)
    op.create_index("ix_rastreamento_alertas_chave_fixture", "rastreamento_alertas", ["chave_fixture"], unique=False)
    op.create_index("ix_rastreamento_alertas_veiculo_reportado", "rastreamento_alertas", ["veiculo_id", "reportado_em"], unique=False)


def downgrade():
    bind = op.get_bind()
    for table, indexes in (
        ("rastreamento_alertas", [
            "ix_rastreamento_alertas_veiculo_reportado", "ix_rastreamento_alertas_chave_fixture",
            "ix_rastreamento_alertas_is_demo", "ix_rastreamento_alertas_provedor",
            "ix_rastreamento_alertas_resolvido", "ix_rastreamento_alertas_reportado_em",
            "ix_rastreamento_alertas_severidade", "ix_rastreamento_alertas_tipo",
            "ix_rastreamento_alertas_prefeitura_id", "ix_rastreamento_alertas_veiculo_id", "ix_rastreamento_alertas_id",
        ]),
        ("rastreamento_historicos", [
            "ix_rastreamento_historicos_veiculo_reportado", "ix_rastreamento_historicos_chave_fixture",
            "ix_rastreamento_historicos_is_demo", "ix_rastreamento_historicos_provedor",
            "ix_rastreamento_historicos_reportado_em", "ix_rastreamento_historicos_prefeitura_id",
            "ix_rastreamento_historicos_veiculo_id", "ix_rastreamento_historicos_id",
        ]),
        ("rastreamento_posicoes", [
            "ix_rastreamento_posicoes_veiculo_reportado", "ix_rastreamento_posicoes_chave_fixture",
            "ix_rastreamento_posicoes_is_demo", "ix_rastreamento_posicoes_provedor",
            "ix_rastreamento_posicoes_reportado_em", "ix_rastreamento_posicoes_prefeitura_id",
            "ix_rastreamento_posicoes_veiculo_id", "ix_rastreamento_posicoes_id",
        ]),
    ):
        if _table_exists(bind, table):
            for index in indexes:
                op.drop_index(index, table_name=table)
            op.drop_table(table)
