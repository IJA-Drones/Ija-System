"""ajuste sincronizacao assinaturas

Revision ID: 045bb998500a
Revises: 1985ab785618
Create Date: 2026-03-03 13:29:34.359825
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "045bb998500a"
down_revision = "1985ab785618"
branch_labels = None
depends_on = None


def _index_names(insp, table_name: str) -> set[str]:
    """
    Retorna set com nomes de índices existentes na tabela.
    """
    try:
        idx = insp.get_indexes(table_name) or []
        return {i.get("name") for i in idx if i.get("name")}
    except Exception:
        return set()


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    tables = set(insp.get_table_names())

    # ---------------------------------------------------------
    # 1) Cria a tabela apenas se NÃO existir
    # ---------------------------------------------------------
    if "ordens_servico" not in tables:
        op.create_table(
            "ordens_servico",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("solicitacao_id", sa.Integer(), nullable=False),
            sa.Column("equipe_id", sa.Integer(), nullable=False),
            sa.Column("identificador_os", sa.String(length=100), nullable=True),
            sa.Column("respondido_por", sa.String(length=150), nullable=True),
            sa.Column("respondido_em", sa.DateTime(), nullable=True),
            sa.Column("situacao_aplicacao", sa.String(length=100), nullable=True),
            sa.Column("larva_visualizada", sa.String(length=20), nullable=True),
            sa.Column("retornar_proxima_semana_monitorar_larvas", sa.String(length=20), nullable=True),
            sa.Column("distrito_administrativo", sa.String(length=100), nullable=True),
            sa.Column("nome_rf_ace_responsavel_os", sa.String(length=200), nullable=True),
            sa.Column("criadouro_os_tipo_volume", sa.Text(), nullable=True),
            sa.Column("data_aplicacao", sa.Date(), nullable=True),
            sa.Column("hora_inicio_aplicacao", sa.Time(), nullable=True),
            sa.Column("hora_termino_aplicacao", sa.Time(), nullable=True),
            sa.Column("tratamento_adicional_realizado", sa.String(length=20), nullable=True),
            sa.Column("quantos_quais", sa.Text(), nullable=True),
            sa.Column("descricao_produto", sa.String(length=200), nullable=True),
            sa.Column("formulacao_produto", sa.String(length=200), nullable=True),
            sa.Column("dosagem_g_10l", sa.String(length=50), nullable=True),
            sa.Column("tipo_aplicacao", sa.String(length=100), nullable=True),
            sa.Column("quantidade_produto_administrada_ml", sa.Float(), nullable=True),
            sa.Column("pulverizacao_area_l_ha", sa.Float(), nullable=True),
            sa.Column("prefixo_aeronave_pulverizacao", sa.String(length=100), nullable=True),
            sa.Column("prefixo_aeronave_monitoramento", sa.String(length=100), nullable=True),
            sa.Column("quantidade_videos_registradas", sa.Integer(), nullable=True),
            sa.Column("quantidade_imagens_registradas", sa.Integer(), nullable=True),
            sa.Column("ponta_pulverizacao", sa.String(length=100), nullable=True),
            sa.Column("temperatura_c", sa.Float(), nullable=True),
            sa.Column("umidade_relativa_pct", sa.Float(), nullable=True),
            sa.Column("velocidade_vento_kmh", sa.Float(), nullable=True),
            sa.Column("motivo_nao_realizacao", sa.String(length=255), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("piloto", sa.String(length=150), nullable=True),
            sa.Column("assinatura_piloto", sa.Text(), nullable=True),
            sa.Column("auxiliar", sa.String(length=150), nullable=True),
            sa.Column("proprietario_ou_preposto", sa.String(length=200), nullable=True),
            sa.Column("assinatura_proprietario_ou_preposto", sa.Text(), nullable=True),
            sa.Column("drone_id", sa.Integer(), nullable=True),
            sa.Column("drone_monitoramento_id", sa.Integer(), nullable=True),
            sa.Column("drone_denominacao", sa.String(length=100), nullable=True),
            sa.Column("drone_modelo", sa.String(length=100), nullable=True),
            sa.Column("drone_numero_serie", sa.String(length=100), nullable=True),
            sa.Column("drone_registro_anatel", sa.String(length=50), nullable=True),
            sa.Column("drone_registro_anac", sa.String(length=50), nullable=True),
            sa.Column("drone_monitoramento_denominacao", sa.String(length=100), nullable=True),
            sa.Column("drone_monitoramento_modelo", sa.String(length=100), nullable=True),
            sa.Column("drone_monitoramento_numero_serie", sa.String(length=100), nullable=True),
            sa.Column("drone_monitoramento_registro_anatel", sa.String(length=50), nullable=True),
            sa.Column("drone_monitoramento_registro_anac", sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(["drone_id"], ["drones.id"]),
            sa.ForeignKeyConstraint(["drone_monitoramento_id"], ["drones.id"]),
            sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
            sa.ForeignKeyConstraint(["solicitacao_id"], ["solicitacoes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # Recarrega índices existentes (agora a tabela existe com certeza)
    existing_idx = _index_names(insp, "ordens_servico")

    # ---------------------------------------------------------
    # 2) Cria índices somente se não existirem
    # ---------------------------------------------------------
    # Atenção: batch_alter_table + create_index dá erro se o índice já existe.
    # Então fazemos create_index condicional fora do batch.
    def _create_index_if_missing(name: str, cols: list[str], unique: bool = False):
        if name not in existing_idx:
            op.create_index(name, "ordens_servico", cols, unique=unique)
            existing_idx.add(name)

    # índices "f(...)" do alembic normalmente viram esses nomes (como no seu downgrade)
    _create_index_if_missing("ix_ordens_servico_auxiliar", ["auxiliar"], unique=False)
    _create_index_if_missing("ix_ordens_servico_data_aplicacao", ["data_aplicacao"], unique=False)
    _create_index_if_missing("ix_ordens_servico_drone_id", ["drone_id"], unique=False)
    _create_index_if_missing("ix_ordens_servico_drone_monitoramento_id", ["drone_monitoramento_id"], unique=False)
    _create_index_if_missing("ix_ordens_servico_equipe_id", ["equipe_id"], unique=False)
    _create_index_if_missing("ix_ordens_servico_identificador_os", ["identificador_os"], unique=False)
    _create_index_if_missing("ix_ordens_servico_piloto", ["piloto"], unique=False)
    _create_index_if_missing("ix_ordens_servico_prefixo_aeronave_monitoramento", ["prefixo_aeronave_monitoramento"], unique=False)
    _create_index_if_missing("ix_ordens_servico_prefixo_aeronave_pulverizacao", ["prefixo_aeronave_pulverizacao"], unique=False)
    _create_index_if_missing("ix_ordens_servico_respondido_em", ["respondido_em"], unique=False)
    _create_index_if_missing("ix_ordens_servico_respondido_por", ["respondido_por"], unique=False)
    _create_index_if_missing("ix_ordens_servico_situacao_aplicacao", ["situacao_aplicacao"], unique=False)
    _create_index_if_missing("ix_ordens_servico_solicitacao_id", ["solicitacao_id"], unique=True)
    _create_index_if_missing("ix_ordens_servico_tipo_aplicacao", ["tipo_aplicacao"], unique=False)

    # índices "extras" com nomes fixos que você criou
    _create_index_if_missing("ix_os_data_aplicacao", ["data_aplicacao"], unique=False)
    _create_index_if_missing("ix_os_equipe", ["equipe_id"], unique=False)
    _create_index_if_missing("ix_os_equipe_drone", ["equipe_id", "drone_id"], unique=False)
    _create_index_if_missing("ix_os_identificador", ["identificador_os"], unique=False)
    _create_index_if_missing("ix_os_respondido_em", ["respondido_em"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    if "ordens_servico" not in set(insp.get_table_names()):
        return

    existing_idx = _index_names(insp, "ordens_servico")

    def _drop_index_if_exists(name: str):
        if name in existing_idx:
            op.drop_index(name, table_name="ordens_servico")
            existing_idx.remove(name)

    # drop na mesma ordem que você tinha
    _drop_index_if_exists("ix_os_respondido_em")
    _drop_index_if_exists("ix_os_identificador")
    _drop_index_if_exists("ix_os_equipe_drone")
    _drop_index_if_exists("ix_os_equipe")
    _drop_index_if_exists("ix_os_data_aplicacao")
    _drop_index_if_exists("ix_ordens_servico_tipo_aplicacao")
    _drop_index_if_exists("ix_ordens_servico_solicitacao_id")
    _drop_index_if_exists("ix_ordens_servico_situacao_aplicacao")
    _drop_index_if_exists("ix_ordens_servico_respondido_por")
    _drop_index_if_exists("ix_ordens_servico_respondido_em")
    _drop_index_if_exists("ix_ordens_servico_prefixo_aeronave_pulverizacao")
    _drop_index_if_exists("ix_ordens_servico_prefixo_aeronave_monitoramento")
    _drop_index_if_exists("ix_ordens_servico_piloto")
    _drop_index_if_exists("ix_ordens_servico_identificador_os")
    _drop_index_if_exists("ix_ordens_servico_equipe_id")
    _drop_index_if_exists("ix_ordens_servico_drone_monitoramento_id")
    _drop_index_if_exists("ix_ordens_servico_drone_id")
    _drop_index_if_exists("ix_ordens_servico_data_aplicacao")
    _drop_index_if_exists("ix_ordens_servico_auxiliar")

    op.drop_table("ordens_servico")