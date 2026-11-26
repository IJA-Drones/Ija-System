"""Control history, preventive reminders and drones carried on a vehicle shift."""
from alembic import op
import sqlalchemy as sa


revision = "a06d4f3c2b91"
down_revision = "f2b6a9c4e830"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controle_remoto_atualizacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("controle_id", sa.Integer(), sa.ForeignKey("controles_remotos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("usuario_nome", sa.String(200), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("alteracoes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_controle_remoto_atualizacoes_controle_id", "controle_remoto_atualizacoes", ["controle_id"])
    op.add_column("logs_veiculo", sa.Column("drones_transportados", sa.JSON(none_as_null=True), nullable=True))
    with op.batch_alter_table("notificacoes") as batch:
        batch.add_column(sa.Column("preventiva_plano_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("chave_preventiva", sa.String(100), nullable=True))
        batch.create_foreign_key("fk_notificacoes_preventiva_plano", "preventiva_planos", ["preventiva_plano_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_notificacoes_preventiva_plano_id", ["preventiva_plano_id"])
        batch.create_index("ix_notificacoes_chave_preventiva", ["chave_preventiva"], unique=True)


def downgrade():
    op.execute("DELETE FROM notificacoes WHERE preventiva_plano_id IS NOT NULL")
    with op.batch_alter_table("notificacoes") as batch:
        batch.drop_index("ix_notificacoes_chave_preventiva")
        batch.drop_index("ix_notificacoes_preventiva_plano_id")
        batch.drop_constraint("fk_notificacoes_preventiva_plano", type_="foreignkey")
        batch.drop_column("chave_preventiva")
        batch.drop_column("preventiva_plano_id")
    op.drop_column("logs_veiculo", "drones_transportados")
    op.drop_index("ix_controle_remoto_atualizacoes_controle_id", table_name="controle_remoto_atualizacoes")
    op.drop_table("controle_remoto_atualizacoes")
