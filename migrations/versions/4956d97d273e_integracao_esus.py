"""integração e-SUS APS (PEC): configuração, execuções, visitas ACS/ACE e domicílios

Revision ID: 4956d97d273e
Revises: 5b8e1f0c2d47
"""
from alembic import op
import sqlalchemy as sa

revision = "4956d97d273e"
down_revision = "5b8e1f0c2d47"
branch_labels = None
depends_on = None


def _prefeitura():
    return sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id", ondelete="CASCADE"), nullable=False)


def upgrade():
    op.create_table(
        "integracao_esus_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        _prefeitura(),
        sa.Column("modo", sa.String(10), nullable=False, server_default="simulado"),
        sa.Column("ibge", sa.String(7)),
        sa.Column("host", sa.String(200)),
        sa.Column("porta", sa.Integer(), nullable=False, server_default="5432"),
        sa.Column("base", sa.String(120)),
        sa.Column("usuario", sa.String(120)),
        sa.Column("senha_cifrada", sa.Text()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("intervalo_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_hash", sa.String(64)),
        sa.Column("token_prefixo", sa.String(16)),
        sa.Column("token_criado_em", sa.DateTime()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por_id", sa.Integer()),
        sa.UniqueConstraint("prefeitura_id", name="uq_integracao_esus_config_prefeitura"),
        sa.UniqueConstraint("token_hash", name="uq_integracao_esus_config_token"),
        sa.CheckConstraint("modo IN ('pec', 'simulado')", name="ck_integracao_esus_config_modo"),
    )
    op.create_table(
        "integracao_esus_execucoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        _prefeitura(),
        sa.Column("processo", sa.String(20), nullable=False),
        sa.Column("forma", sa.String(12), nullable=False),
        sa.Column("modo", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="executando"),
        sa.Column("iniciado_em", sa.DateTime(), nullable=False),
        sa.Column("finalizado_em", sa.DateTime()),
        *[sa.Column(c, sa.Integer(), nullable=False, server_default="0") for c in ("lidos", "inseridos", "atualizados", "removidos", "erros")],
        sa.Column("mensagem", sa.Text()),
        sa.Column("usuario_id", sa.Integer()),
    )
    op.create_index("ix_integracao_esus_execucoes_prefeitura_id", "integracao_esus_execucoes", ["prefeitura_id"])
    op.create_index("ix_integracao_esus_execucoes_iniciado_em", "integracao_esus_execucoes", ["iniciado_em"])
    op.create_table(
        "integracao_esus_visitas",
        sa.Column("id", sa.Integer(), primary_key=True),
        _prefeitura(),
        sa.Column("origem", sa.String(10), nullable=False),
        sa.Column("chave", sa.String(40), nullable=False),
        sa.Column("ficha_uuid", sa.String(92)),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("hora", sa.String(5)),
        sa.Column("turno", sa.String(20)),
        sa.Column("profissional_cns", sa.String(15)),
        sa.Column("profissional_nome", sa.String(255), nullable=False),
        sa.Column("cbo", sa.String(6)),
        sa.Column("categoria", sa.String(3)),
        sa.Column("equipe_ine", sa.String(20)),
        sa.Column("equipe_nome", sa.String(255)),
        sa.Column("unidade_cnes", sa.String(20)),
        sa.Column("unidade_nome", sa.String(255)),
        sa.Column("microarea", sa.String(3)),
        sa.Column("domicilio_uuid", sa.String(92)),
        sa.Column("tipo_imovel", sa.String(120)),
        sa.Column("desfecho", sa.String(15), nullable=False),
        sa.Column("motivos", sa.String(500)),
        sa.Column("motivo_aedes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("sincronizado_em", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("prefeitura_id", "chave", name="uq_esus_visita_chave"),
    )
    op.create_index("ix_esus_visita_periodo", "integracao_esus_visitas", ["prefeitura_id", "data"])
    op.create_table(
        "integracao_esus_domicilios",
        sa.Column("id", sa.Integer(), primary_key=True),
        _prefeitura(),
        sa.Column("origem", sa.String(10), nullable=False),
        sa.Column("chave", sa.String(92), nullable=False),
        sa.Column("microarea", sa.String(3)),
        sa.Column("logradouro", sa.String(288)),
        sa.Column("numero", sa.String(64)),
        sa.Column("bairro", sa.String(200)),
        sa.Column("cep", sa.String(10)),
        sa.Column("tipo_imovel", sa.String(120)),
        sa.Column("moradores", sa.Integer()),
        sa.Column("recusa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profissional_nome", sa.String(255)),
        sa.Column("equipe_ine", sa.String(20)),
        sa.Column("data_cadastro", sa.Date()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("sincronizado_em", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("prefeitura_id", "chave", name="uq_esus_domicilio_chave"),
    )


def downgrade():
    op.drop_table("integracao_esus_domicilios")
    op.drop_index("ix_esus_visita_periodo", table_name="integracao_esus_visitas")
    op.drop_table("integracao_esus_visitas")
    op.drop_index("ix_integracao_esus_execucoes_iniciado_em", table_name="integracao_esus_execucoes")
    op.drop_index("ix_integracao_esus_execucoes_prefeitura_id", table_name="integracao_esus_execucoes")
    op.drop_table("integracao_esus_execucoes")
    op.drop_table("integracao_esus_config")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP SCHEMA IF EXISTS esus_sim CASCADE")  # PEC simulado gerado pela tela
