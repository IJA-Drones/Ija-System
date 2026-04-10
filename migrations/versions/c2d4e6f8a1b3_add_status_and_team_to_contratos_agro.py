"""add status and team to contratos agro

Revision ID: c2d4e6f8a1b3
Revises: 9c4e7a2b1d6f
Create Date: 2026-04-09 13:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c2d4e6f8a1b3"
down_revision = "9c4e7a2b1d6f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        batch_op.add_column(sa.Column("equipe_agro_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="APROVADO",
            )
        )
        batch_op.create_index(batch_op.f("ix_contratos_agro_equipe_agro_id"), ["equipe_agro_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_contratos_agro_status"), ["status"], unique=False)
        batch_op.create_index("ix_contratos_agro_status_equipe", ["status", "equipe_agro_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_contratos_agro_equipe_agro_id_equipes_agro",
            "equipes_agro",
            ["equipe_agro_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        batch_op.drop_constraint("fk_contratos_agro_equipe_agro_id_equipes_agro", type_="foreignkey")
        batch_op.drop_index("ix_contratos_agro_status_equipe")
        batch_op.drop_index(batch_op.f("ix_contratos_agro_status"))
        batch_op.drop_index(batch_op.f("ix_contratos_agro_equipe_agro_id"))
        batch_op.drop_column("status")
        batch_op.drop_column("equipe_agro_id")
