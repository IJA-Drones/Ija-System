"""Ciclos opcionais e histórico de atualizações das baterias."""
from alembic import op
import sqlalchemy as sa

revision = "b7d3e91a6204"
down_revision = "f79c31d5a802"
branch_labels = None
depends_on = None


def upgrade():
    # Existing cycle values remain intact; no historical confirmation is invented.
    with op.batch_alter_table("baterias") as batch:
        batch.alter_column("ciclo", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("atualizado_em", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("atualizado_por_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ciclos_atualizados_em", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_baterias_atualizado_por", "usuarios", ["atualizado_por_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_baterias_atualizado_em", ["atualizado_em"])
    op.create_table("bateria_atualizacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bateria_id", sa.Integer(), sa.ForeignKey("baterias.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id")),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("usuario_nome", sa.String(200), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("alteracoes", sa.JSON(), nullable=False),
    )
    for column in ("bateria_id", "prefeitura_id", "criado_em"):
        op.create_index("ix_bateria_atualizacoes_" + column, "bateria_atualizacoes", [column])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM bateria_atualizacoes LIMIT 1")).first():
        raise RuntimeError("O histórico das baterias precisa ser preservado antes de reverter esta migração.")
    op.drop_table("bateria_atualizacoes")
    with op.batch_alter_table("baterias") as batch:
        batch.drop_index("ix_baterias_atualizado_em")
        batch.drop_constraint("fk_baterias_atualizado_por", type_="foreignkey")
        batch.drop_column("atualizado_por_id")
        batch.drop_column("atualizado_em")
        batch.drop_column("ciclos_atualizados_em")
