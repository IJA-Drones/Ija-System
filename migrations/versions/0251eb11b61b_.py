"""add rastreamento tables and quadra admin flags

This migration is intentionally safe to rerun against databases where the
tracking tables were created before Alembic recorded this revision.
"""

from alembic import op
import sqlalchemy as sa


revision = "0251eb11b61b"
down_revision = "d6304a5d4c0d"
branch_labels = None
depends_on = None


def _create_table_if_missing(name, *columns, **kwargs):
    bind = op.get_bind()
    metadata = sa.MetaData()
    table = sa.Table(name, metadata, *columns, **kwargs)
    table.create(bind=bind, checkfirst=True)
    return table


def _create_index_if_missing(name, table_name, columns, unique=False):
    bind = op.get_bind()
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    _create_table_if_missing(
        "rastreamento_alertas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("veiculo_id", sa.Integer, sa.ForeignKey("veiculos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prefeitura_id", sa.Integer, sa.ForeignKey("prefeituras.id")),
        sa.Column("tipo", sa.String(80), nullable=False),
        sa.Column("severidade", sa.String(20), nullable=False),
        sa.Column("mensagem", sa.String(255), nullable=False),
        sa.Column("reportado_em", sa.DateTime, nullable=False),
        sa.Column("resolvido", sa.Boolean, nullable=False),
        sa.Column("provedor", sa.String(40), nullable=False),
        sa.Column("is_demo", sa.Boolean, nullable=False),
        sa.Column("chave_fixture", sa.String(160)),
    )
    _create_table_if_missing(
        "rastreamento_historicos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("veiculo_id", sa.Integer, sa.ForeignKey("veiculos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prefeitura_id", sa.Integer, sa.ForeignKey("prefeituras.id")),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("velocidade_kmh", sa.Float),
        sa.Column("ignicao", sa.Boolean),
        sa.Column("hodometro_km", sa.Float),
        sa.Column("reportado_em", sa.DateTime, nullable=False),
        sa.Column("provedor", sa.String(40), nullable=False),
        sa.Column("is_demo", sa.Boolean, nullable=False),
        sa.Column("chave_fixture", sa.String(160)),
    )
    _create_table_if_missing(
        "rastreamento_posicoes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("veiculo_id", sa.Integer, sa.ForeignKey("veiculos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prefeitura_id", sa.Integer, sa.ForeignKey("prefeituras.id")),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("velocidade_kmh", sa.Float),
        sa.Column("ignicao", sa.Boolean),
        sa.Column("hodometro_km", sa.Float),
        sa.Column("endereco", sa.String(255)),
        sa.Column("reportado_em", sa.DateTime, nullable=False),
        sa.Column("provedor", sa.String(40), nullable=False),
        sa.Column("is_demo", sa.Boolean, nullable=False),
        sa.Column("chave_fixture", sa.String(160)),
    )

    for table_name, columns in {
        "rastreamento_alertas": [("chave_fixture", True), ("is_demo", False), ("prefeitura_id", False), ("provedor", False), ("reportado_em", False), ("resolvido", False), ("severidade", False), ("tipo", False), ("veiculo_id", False), ("veiculo_reportado", False)],
        "rastreamento_historicos": [("chave_fixture", True), ("is_demo", False), ("prefeitura_id", False), ("provedor", False), ("reportado_em", False), ("veiculo_id", False), ("veiculo_reportado", False)],
        "rastreamento_posicoes": [("chave_fixture", True), ("is_demo", False), ("prefeitura_id", False), ("provedor", False), ("reportado_em", False), ("veiculo_id", False), ("veiculo_reportado", False)],
    }.items():
        for column, unique in columns:
            index_name = f"ix_{table_name}_{column}"
            index_columns = ["veiculo_id", "reportado_em"] if column == "veiculo_reportado" else [column]
            _create_index_if_missing(index_name, table_name, index_columns, unique=unique)

    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("solicitacoes")}
    for name, column in (
        ("quadra_confirmada_admin", sa.Boolean),
        ("quadra_visualizada_admin", sa.Boolean),
        ("quadra_visualizada_admin_em", sa.DateTime),
    ):
        if name not in existing:
            op.add_column("solicitacoes", sa.Column(name, column, server_default=sa.false() if column is sa.Boolean else None, nullable=column is not sa.DateTime))


def downgrade():
    # This revision may have adopted pre-existing tables; never remove them
    # automatically during downgrade.
    pass