"""Vehicle maintenance worksheets and weekly checklist alerts."""
from alembic import op
import sqlalchemy as sa


revision = "e93d7c4a210b"
down_revision = "a06d4f3c2b91"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("manutencoes_equipamentos") as batch:
        batch.add_column(sa.Column("veiculo_id", sa.Integer()))
        batch.add_column(sa.Column("checklist_veiculo_id", sa.Integer()))
        batch.add_column(sa.Column("km_recebimento", sa.Float()))
        batch.alter_column("drone_id", existing_type=sa.Integer(), nullable=True)
        batch.create_foreign_key("fk_manutencao_veiculo", "veiculos", ["veiculo_id"], ["id"])
        batch.create_foreign_key("fk_manutencao_checklist", "checklists_semanais_veiculo", ["checklist_veiculo_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_manutencoes_equipamentos_veiculo_id", ["veiculo_id"])
        batch.create_unique_constraint("uq_manutencao_checklist_veiculo", ["checklist_veiculo_id"])
        batch.create_check_constraint("ck_manutencao_equipamento", "(drone_id IS NOT NULL) <> (veiculo_id IS NOT NULL)")
        batch.create_check_constraint("ck_manutencao_checklist_veiculo", "checklist_veiculo_id IS NULL OR veiculo_id IS NOT NULL")
    with op.batch_alter_table("manutencao_pecas_usadas") as batch:
        batch.add_column(sa.Column("veiculo_id", sa.Integer()))
        batch.alter_column("drone_id", existing_type=sa.Integer(), nullable=True)
        batch.create_foreign_key("fk_peca_usada_veiculo", "veiculos", ["veiculo_id"], ["id"])
        batch.create_index("ix_manutencao_pecas_usadas_veiculo_id", ["veiculo_id"])
        batch.create_check_constraint("ck_manutencao_peca_equipamento", "(drone_id IS NOT NULL) <> (veiculo_id IS NOT NULL)")
    with op.batch_alter_table("notificacoes") as batch:
        batch.add_column(sa.Column("checklist_veiculo_id", sa.Integer()))
        batch.create_foreign_key("fk_notificacao_checklist_veiculo", "checklists_semanais_veiculo", ["checklist_veiculo_id"], ["id"], ondelete="CASCADE")
        batch.create_unique_constraint("uq_notificacao_usuario_checklist_veiculo", ["usuario_id", "checklist_veiculo_id"])
        batch.create_index("ix_notificacoes_checklist_veiculo_id", ["checklist_veiculo_id"])


def downgrade():
    for table, column in (("manutencoes_equipamentos", "veiculo_id"), ("manutencao_pecas_usadas", "veiculo_id"), ("notificacoes", "checklist_veiculo_id")):
        if op.get_bind().execute(sa.text(f"SELECT id FROM {table} WHERE {column} IS NOT NULL LIMIT 1")).first():
            raise RuntimeError("Preserve as OS de veículos e os avisos do checklist antes de reverter a migração.")
    with op.batch_alter_table("notificacoes") as batch:
        batch.drop_index("ix_notificacoes_checklist_veiculo_id")
        batch.drop_constraint("uq_notificacao_usuario_checklist_veiculo", type_="unique")
        batch.drop_constraint("fk_notificacao_checklist_veiculo", type_="foreignkey")
        batch.drop_column("checklist_veiculo_id")
    with op.batch_alter_table("manutencao_pecas_usadas") as batch:
        batch.drop_constraint("ck_manutencao_peca_equipamento", type_="check")
        batch.drop_index("ix_manutencao_pecas_usadas_veiculo_id")
        batch.drop_constraint("fk_peca_usada_veiculo", type_="foreignkey")
        batch.alter_column("drone_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("veiculo_id")
    with op.batch_alter_table("manutencoes_equipamentos") as batch:
        batch.drop_constraint("ck_manutencao_checklist_veiculo", type_="check")
        batch.drop_constraint("ck_manutencao_equipamento", type_="check")
        batch.drop_constraint("uq_manutencao_checklist_veiculo", type_="unique")
        batch.drop_index("ix_manutencoes_equipamentos_veiculo_id")
        batch.drop_constraint("fk_manutencao_checklist", type_="foreignkey")
        batch.drop_constraint("fk_manutencao_veiculo", type_="foreignkey")
        batch.alter_column("drone_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("km_recebimento")
        batch.drop_column("checklist_veiculo_id")
        batch.drop_column("veiculo_id")
