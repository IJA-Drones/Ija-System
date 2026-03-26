"""add_dji_kml_routes

Revision ID: 6b7c8d9e0f1a
Revises: 3a2c4e5f6a7b
Create Date: 2026-03-26 14:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6b7c8d9e0f1a"
down_revision = "3a2c4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dji_flight_kml_routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flight_record_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("route_code", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("aircraft_name", sa.String(length=120), nullable=True),
        sa.Column("pilot_name", sa.String(length=120), nullable=True),
        sa.Column("flight_controller_id", sa.String(length=120), nullable=True),
        sa.Column("route_timestamp", sa.DateTime(), nullable=True),
        sa.Column("mode_selection", sa.String(length=40), nullable=True),
        sa.Column("flight_time_raw", sa.String(length=40), nullable=True),
        sa.Column("task_area", sa.Float(), nullable=True),
        sa.Column("spray_amount", sa.Float(), nullable=True),
        sa.Column("route_color", sa.String(length=20), nullable=True),
        sa.Column("route_width", sa.Float(), nullable=True),
        sa.Column("point_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_json", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["flight_record_id"], ["dji_flight_records.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_sha256"),
        sa.UniqueConstraint("flight_record_id"),
        sa.UniqueConstraint("route_code"),
    )
    op.create_index(op.f("ix_dji_flight_kml_routes_aircraft_name"), "dji_flight_kml_routes", ["aircraft_name"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_flight_controller_id"), "dji_flight_kml_routes", ["flight_controller_id"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_flight_record_id"), "dji_flight_kml_routes", ["flight_record_id"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_imported_at"), "dji_flight_kml_routes", ["imported_at"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_pilot_name"), "dji_flight_kml_routes", ["pilot_name"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_route_code"), "dji_flight_kml_routes", ["route_code"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_route_timestamp"), "dji_flight_kml_routes", ["route_timestamp"], unique=False)
    op.create_index(op.f("ix_dji_flight_kml_routes_uploaded_by_id"), "dji_flight_kml_routes", ["uploaded_by_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_dji_flight_kml_routes_uploaded_by_id"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_route_timestamp"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_route_code"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_pilot_name"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_imported_at"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_flight_record_id"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_flight_controller_id"), table_name="dji_flight_kml_routes")
    op.drop_index(op.f("ix_dji_flight_kml_routes_aircraft_name"), table_name="dji_flight_kml_routes")
    op.drop_table("dji_flight_kml_routes")
