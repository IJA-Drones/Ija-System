"""add_dji_kml_route_to_os

Revision ID: 0f4a6b8c2d1e
Revises: b7c8d9e0f1a2
Create Date: 2026-07-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0f4a6b8c2d1e"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dji_kml_route_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_ordens_servico_dji_kml_route_id"), ["dji_kml_route_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_ordens_servico_dji_kml_route_id_dji_flight_kml_routes",
            "dji_flight_kml_routes",
            ["dji_kml_route_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.drop_constraint("fk_ordens_servico_dji_kml_route_id_dji_flight_kml_routes", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_ordens_servico_dji_kml_route_id"))
        batch_op.drop_column("dji_kml_route_id")
