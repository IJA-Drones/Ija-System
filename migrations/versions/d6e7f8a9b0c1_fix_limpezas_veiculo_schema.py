"""fix limpezas veiculo schema

Revision ID: d6e7f8a9b0c1
Revises: c1d2e3f4a5b6
Create Date: 2026-07-29 00:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d6e7f8a9b0c1"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name, column_name):
    if not _has_table(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "limpezas_veiculo"):
        op.create_table(
            "limpezas_veiculo",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("log_veiculo_id", sa.Integer(), nullable=False),
            sa.Column("veiculo_id", sa.Integer(), nullable=False),
            sa.Column("piloto_id", sa.Integer(), nullable=True),
            sa.Column("equipe_id", sa.Integer(), nullable=True),
            sa.Column("data_hora", sa.DateTime(), nullable=False),
            sa.Column("limpeza_realizada", sa.Boolean(), nullable=False),
            sa.Column("tipo_limpeza", sa.String(length=30), nullable=False),
            sa.Column("valor_total", sa.Numeric(10, 2), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
            sa.ForeignKeyConstraint(["log_veiculo_id"], ["logs_veiculo.id"]),
            sa.ForeignKeyConstraint(["piloto_id"], ["pilotos.id"]),
            sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_limpezas_veiculo_data_hora"), ["data_hora"], unique=False)
            batch_op.create_index(batch_op.f("ix_limpezas_veiculo_equipe_id"), ["equipe_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_limpezas_veiculo_log_veiculo_id"), ["log_veiculo_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_limpezas_veiculo_piloto_id"), ["piloto_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_limpezas_veiculo_veiculo_id"), ["veiculo_id"], unique=False)

    inspector = sa.inspect(bind)
    if _has_column(inspector, "checklists_semanais_veiculo", "limpeza_veiculo_realizada"):
        with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
            batch_op.drop_column("limpeza_veiculo_realizada")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "checklists_semanais_drone", "limpeza_equipamento_realizada"):
        with op.batch_alter_table("checklists_semanais_drone", schema=None) as batch_op:
            batch_op.drop_column("limpeza_equipamento_realizada")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "limpezas_veiculo"):
        with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
            for index_name in (
                "ix_limpezas_veiculo_veiculo_id",
                "ix_limpezas_veiculo_piloto_id",
                "ix_limpezas_veiculo_log_veiculo_id",
                "ix_limpezas_veiculo_equipe_id",
                "ix_limpezas_veiculo_data_hora",
            ):
                batch_op.drop_index(index_name)
        op.drop_table("limpezas_veiculo")
