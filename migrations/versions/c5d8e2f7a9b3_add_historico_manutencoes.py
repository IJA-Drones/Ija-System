"""add historico manutencoes

Revision ID: c5d8e2f7a9b3
Revises: b4e7c2a9d8f1
Create Date: 2026-08-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c5d8e2f7a9b3"
down_revision = "b4e7c2a9d8f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manutencoes_equipamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("drone_id", sa.Integer(), nullable=False),
        sa.Column("aberta_por_id", sa.Integer(), nullable=True),
        sa.Column("encerrada_por_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("aberta_em", sa.DateTime(), nullable=False),
        sa.Column("encerrada_em", sa.DateTime(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["aberta_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"]),
        sa.ForeignKeyConstraint(["encerrada_por_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manutencoes_equipamentos_aberta_em"), "manutencoes_equipamentos", ["aberta_em"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_aberta_por_id"), "manutencoes_equipamentos", ["aberta_por_id"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_drone_id"), "manutencoes_equipamentos", ["drone_id"], unique=False)
    op.create_index("ix_manutencoes_equipamentos_drone_status", "manutencoes_equipamentos", ["drone_id", "status"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_encerrada_em"), "manutencoes_equipamentos", ["encerrada_em"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_encerrada_por_id"), "manutencoes_equipamentos", ["encerrada_por_id"], unique=False)
    op.create_index("ix_manutencoes_equipamentos_periodo", "manutencoes_equipamentos", ["aberta_em", "encerrada_em"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_prefeitura_id"), "manutencoes_equipamentos", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_manutencoes_equipamentos_status"), "manutencoes_equipamentos", ["status"], unique=False)

    op.add_column("manutencao_pecas_usadas", sa.Column("manutencao_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_manutencao_pecas_usadas_manutencao_id",
        "manutencao_pecas_usadas",
        "manutencoes_equipamentos",
        ["manutencao_id"],
        ["id"],
    )
    op.create_index(op.f("ix_manutencao_pecas_usadas_manutencao_id"), "manutencao_pecas_usadas", ["manutencao_id"], unique=False)

    op.execute(
        """
        INSERT INTO manutencoes_equipamentos (prefeitura_id, drone_id, status, aberta_em)
        SELECT e.prefeitura_id, d.id, 'aberta', COALESCE(e.ultima_manutencao::timestamp, NOW())
        FROM drones d
        JOIN equipamentos e ON e.id = d.id
        WHERE e.status IN ('Em Manutenção', 'Manutenção', 'Manutencao', 'Em Manutencao')
          AND NOT EXISTS (
            SELECT 1
            FROM manutencoes_equipamentos me
            WHERE me.drone_id = d.id
              AND me.status = 'aberta'
          )
        """
    )
    op.execute(
        """
        UPDATE manutencao_pecas_usadas mpu
        SET manutencao_id = me.id
        FROM manutencoes_equipamentos me
        WHERE mpu.manutencao_id IS NULL
          AND mpu.drone_id = me.drone_id
          AND me.status = 'aberta'
        """
    )


def downgrade():
    op.drop_index(op.f("ix_manutencao_pecas_usadas_manutencao_id"), table_name="manutencao_pecas_usadas")
    op.drop_constraint("fk_manutencao_pecas_usadas_manutencao_id", "manutencao_pecas_usadas", type_="foreignkey")
    op.drop_column("manutencao_pecas_usadas", "manutencao_id")
    op.drop_index(op.f("ix_manutencoes_equipamentos_status"), table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_prefeitura_id"), table_name="manutencoes_equipamentos")
    op.drop_index("ix_manutencoes_equipamentos_periodo", table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_encerrada_por_id"), table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_encerrada_em"), table_name="manutencoes_equipamentos")
    op.drop_index("ix_manutencoes_equipamentos_drone_status", table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_drone_id"), table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_aberta_por_id"), table_name="manutencoes_equipamentos")
    op.drop_index(op.f("ix_manutencoes_equipamentos_aberta_em"), table_name="manutencoes_equipamentos")
    op.drop_table("manutencoes_equipamentos")
