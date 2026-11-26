"""Unified maintenance worksheet and DJI part numbers (additive only)."""
from alembic import op
import sqlalchemy as sa

revision = "f2b6a9c4e830"
down_revision = "d4a92e5b7c18"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("estoque_pecas", sa.Column("codigo_dji", sa.String(120), nullable=True))
    for name, type_ in (
        ("recebido_em", sa.DateTime()), ("condicao_chegada", sa.String(40)),
        ("diagnostico_tecnico", sa.Text()), ("tipo_manutencao", sa.String(20)),
        ("servicos_realizados", sa.Text()), ("condicao_final", sa.String(40)),
        ("pecas_avariadas", sa.JSON()), ("pecas_reparo", sa.JSON()),
        ("atualizada_em", sa.DateTime()),
    ):
        op.add_column("manutencoes_equipamentos", sa.Column(name, type_, nullable=True))
    op.add_column("manutencoes_equipamentos", sa.Column("versao", sa.Integer(), nullable=False, server_default="0"))
    for name, size in (("nome_peca_snapshot", 120), ("codigo_dji_snapshot", 120), ("numero_serie_snapshot", 100)):
        op.add_column("manutencao_pecas_usadas", sa.Column(name, sa.String(size), nullable=True))
    # No stock movements, model renames, permission changes or invented history.


def downgrade():
    for name in ("numero_serie_snapshot", "codigo_dji_snapshot", "nome_peca_snapshot"):
        op.drop_column("manutencao_pecas_usadas", name)
    for name in ("versao", "atualizada_em", "pecas_reparo", "pecas_avariadas", "condicao_final",
                 "servicos_realizados", "tipo_manutencao", "diagnostico_tecnico", "condicao_chegada", "recebido_em"):
        op.drop_column("manutencoes_equipamentos", name)
    op.drop_column("estoque_pecas", "codigo_dji")
