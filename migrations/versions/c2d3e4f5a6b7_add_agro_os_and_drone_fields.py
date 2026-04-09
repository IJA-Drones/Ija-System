from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _table_exists(conn, table_name: str) -> bool:
    return table_name in inspect(conn).get_table_names()


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = inspect(conn)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade():
    conn = op.get_bind()

    equipamento_columns = (
        ("funcao_operacional", sa.String(length=30)),
        ("registro_anatel", sa.String(length=50)),
        ("registro_anac", sa.String(length=50)),
        ("capacidade_tanque_l", sa.Numeric(10, 2)),
        ("largura_faixa_m", sa.Numeric(10, 2)),
        ("altura_voo_padrao_m", sa.Numeric(10, 2)),
        ("ponta_pulverizacao", sa.String(length=100)),
    )

    with op.batch_alter_table("equipamentos_agro", schema=None) as batch_op:
        for column_name, column_type in equipamento_columns:
            if not _column_exists(conn, "equipamentos_agro", column_name):
                batch_op.add_column(sa.Column(column_name, column_type, nullable=True))

    if not _table_exists(conn, "ordens_servico_agro"):
        op.create_table(
            "ordens_servico_agro",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("contrato_agro_id", sa.Integer(), nullable=False),
            sa.Column("orcamento_agro_id", sa.Integer(), nullable=False),
            sa.Column("equipe_agro_id", sa.Integer(), nullable=False),
            sa.Column("piloto_agro_id", sa.Integer(), nullable=True),
            sa.Column("drone_pulverizacao_id", sa.Integer(), nullable=True),
            sa.Column("drone_mapeamento_id", sa.Integer(), nullable=True),
            sa.Column("identificador_os", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("data_aplicacao", sa.Date(), nullable=True),
            sa.Column("periodo_aplicacao", sa.String(length=120), nullable=True),
            sa.Column("cliente_nome", sa.String(length=150), nullable=False),
            sa.Column("propriedade_nome", sa.String(length=150), nullable=False),
            sa.Column("cultura", sa.String(length=100), nullable=True),
            sa.Column("servico", sa.String(length=50), nullable=True),
            sa.Column("protocolo", sa.String(length=80), nullable=True),
            sa.Column("cidade_operacao", sa.String(length=100), nullable=True),
            sa.Column("uf_operacao", sa.String(length=2), nullable=True),
            sa.Column("drone_pulverizacao_identificacao", sa.String(length=100), nullable=True),
            sa.Column("drone_pulverizacao_modelo", sa.String(length=100), nullable=True),
            sa.Column("drone_pulverizacao_tipo", sa.String(length=50), nullable=True),
            sa.Column("drone_pulverizacao_registro_anatel", sa.String(length=50), nullable=True),
            sa.Column("drone_pulverizacao_registro_anac", sa.String(length=50), nullable=True),
            sa.Column("drone_mapeamento_identificacao", sa.String(length=100), nullable=True),
            sa.Column("drone_mapeamento_modelo", sa.String(length=100), nullable=True),
            sa.Column("drone_mapeamento_tipo", sa.String(length=50), nullable=True),
            sa.Column("drone_mapeamento_registro_anatel", sa.String(length=50), nullable=True),
            sa.Column("drone_mapeamento_registro_anac", sa.String(length=50), nullable=True),
            sa.Column("altura_voo_m", sa.Numeric(10, 2), nullable=True),
            sa.Column("largura_faixa_m", sa.Numeric(10, 2), nullable=True),
            sa.Column("ponta_pulverizacao", sa.String(length=100), nullable=True),
            sa.Column("mapeamento_descricao", sa.String(length=120), nullable=True),
            sa.Column("temperatura_min_c", sa.Numeric(10, 2), nullable=True),
            sa.Column("temperatura_max_c", sa.Numeric(10, 2), nullable=True),
            sa.Column("umidade_min_pct", sa.Numeric(10, 2), nullable=True),
            sa.Column("umidade_max_pct", sa.Numeric(10, 2), nullable=True),
            sa.Column("vento_min_kmh", sa.Numeric(10, 2), nullable=True),
            sa.Column("vento_max_kmh", sa.Numeric(10, 2), nullable=True),
            sa.Column("area_total_ha", sa.Numeric(12, 2), nullable=True),
            sa.Column("total_calda_l", sa.Numeric(12, 2), nullable=True),
            sa.Column("media_aplicada_l_ha", sa.Numeric(12, 2), nullable=True),
            sa.Column("taxa_aplicacao_l_ha", sa.Numeric(12, 2), nullable=True),
            sa.Column("tipo_aplicacao", sa.String(length=100), nullable=True),
            sa.Column("produto_aplicado", sa.String(length=200), nullable=True),
            sa.Column("formulacao_produto", sa.String(length=200), nullable=True),
            sa.Column("dosagem", sa.String(length=100), nullable=True),
            sa.Column("classe_toxica", sa.String(length=100), nullable=True),
            sa.Column("relatorio_pdf_path", sa.String(length=255), nullable=True),
            sa.Column("relatorio_pdf_nome", sa.String(length=255), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.Column("finalizado_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["contrato_agro_id"], ["contratos_agro.id"]),
            sa.ForeignKeyConstraint(["drone_mapeamento_id"], ["equipamentos_agro.id"]),
            sa.ForeignKeyConstraint(["drone_pulverizacao_id"], ["equipamentos_agro.id"]),
            sa.ForeignKeyConstraint(["equipe_agro_id"], ["equipes_agro.id"]),
            sa.ForeignKeyConstraint(["orcamento_agro_id"], ["orcamentos_agro.id"]),
            sa.ForeignKeyConstraint(["piloto_agro_id"], ["pilotos_agro.id"]),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("identificador_os"),
        )

    index_specs = (
        ("ix_ordens_servico_agro_prefeitura_id", ["prefeitura_id"]),
        ("ix_ordens_servico_agro_contrato_agro_id", ["contrato_agro_id"]),
        ("ix_ordens_servico_agro_orcamento_agro_id", ["orcamento_agro_id"]),
        ("ix_ordens_servico_agro_equipe_agro_id", ["equipe_agro_id"]),
        ("ix_ordens_servico_agro_piloto_agro_id", ["piloto_agro_id"]),
        ("ix_ordens_servico_agro_drone_pulverizacao_id", ["drone_pulverizacao_id"]),
        ("ix_ordens_servico_agro_drone_mapeamento_id", ["drone_mapeamento_id"]),
        ("ix_ordens_servico_agro_identificador_os", ["identificador_os"]),
        ("ix_ordens_servico_agro_status", ["status"]),
        ("ix_ordens_servico_agro_data_aplicacao", ["data_aplicacao"]),
        ("ix_ordens_servico_agro_criado_em", ["criado_em"]),
        ("ix_ordens_servico_agro_atualizado_em", ["atualizado_em"]),
        ("ix_ordens_servico_agro_finalizado_em", ["finalizado_em"]),
        ("ix_os_agro_status_equipe", ["status", "equipe_agro_id"]),
        ("ix_os_agro_contrato_data", ["contrato_agro_id", "data_aplicacao"]),
        ("ix_os_agro_piloto_status", ["piloto_agro_id", "status"]),
    )

    for index_name, columns in index_specs:
        if not _index_exists(conn, "ordens_servico_agro", index_name):
            op.create_index(index_name, "ordens_servico_agro", columns, unique=False)


def downgrade():
    op.execute(text("DROP TABLE IF EXISTS ordens_servico_agro CASCADE"))
    for column_name in (
        "funcao_operacional",
        "registro_anatel",
        "registro_anac",
        "capacidade_tanque_l",
        "largura_faixa_m",
        "altura_voo_padrao_m",
        "ponta_pulverizacao",
    ):
        op.execute(text(f"ALTER TABLE equipamentos_agro DROP COLUMN IF EXISTS {column_name}"))
