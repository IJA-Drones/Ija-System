"""add place_id to dji logs and kml

Revision ID: 5a6b7c8d9e0f
Revises: 4d9e8f1a2b3c
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "5a6b7c8d9e0f"
down_revision = "4d9e8f1a2b3c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dji_flight_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("place_id", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_dji_flight_records_place_id", ["place_id"], unique=False)

    with op.batch_alter_table("dji_flight_kml_routes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("place_id", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_dji_flight_kml_routes_place_id", ["place_id"], unique=False)


def downgrade():
    with op.batch_alter_table("dji_flight_kml_routes", schema=None) as batch_op:
        batch_op.drop_index("ix_dji_flight_kml_routes_place_id")
        batch_op.drop_column("place_id")

    with op.batch_alter_table("dji_flight_records", schema=None) as batch_op:
        batch_op.drop_index("ix_dji_flight_records_place_id")
        batch_op.drop_column("place_id")
