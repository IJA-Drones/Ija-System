"""add_dji_flight_log_tables

Revision ID: 3a2c4e5f6a7b
Revises: 1600d07df8f3, 474b4b2bccd6, 9922f618dc90
Create Date: 2026-03-25 11:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a2c4e5f6a7b"
down_revision = ("1600d07df8f3", "474b4b2bccd6", "9922f618dc90")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dji_flight_log_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(), nullable=True),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dji_flight_log_imports_file_sha256"),
        "dji_flight_log_imports",
        ["file_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dji_flight_log_imports_period_end"),
        "dji_flight_log_imports",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dji_flight_log_imports_period_start"),
        "dji_flight_log_imports",
        ["period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dji_flight_log_imports_uploaded_at"),
        "dji_flight_log_imports",
        ["uploaded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dji_flight_log_imports_uploaded_by_id"),
        "dji_flight_log_imports",
        ["uploaded_by_id"],
        unique=False,
    )

    op.create_table(
        "dji_flight_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("flight_window", sa.String(length=80), nullable=False),
        sa.Column("flight_start", sa.DateTime(), nullable=False),
        sa.Column("flight_end", sa.DateTime(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("aircraft_name", sa.String(length=120), nullable=True),
        sa.Column("task_type", sa.String(length=80), nullable=True),
        sa.Column("sprayed_area_ha", sa.Float(), nullable=True),
        sa.Column("total_amount_l_kg", sa.Float(), nullable=True),
        sa.Column("flight_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("flight_duration_label", sa.String(length=20), nullable=True),
        sa.Column("crop", sa.String(length=80), nullable=True),
        sa.Column("pilot_name", sa.String(length=120), nullable=True),
        sa.Column("team_name", sa.String(length=120), nullable=True),
        sa.Column("field_name", sa.String(length=150), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("starting_battery_level", sa.Integer(), nullable=True),
        sa.Column("ending_battery_level", sa.Integer(), nullable=True),
        sa.Column("battery_consumed_level", sa.Integer(), nullable=True),
        sa.Column("battery_sn", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["dji_flight_log_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index(
        "ix_dji_flight_record_aircraft_start",
        "dji_flight_records",
        ["aircraft_name", "flight_start"],
        unique=False,
    )
    op.create_index(
        "ix_dji_flight_record_pilot_start",
        "dji_flight_records",
        ["pilot_name", "flight_start"],
        unique=False,
    )
    op.create_index(
        "ix_dji_flight_record_serial_start",
        "dji_flight_records",
        ["serial_number", "flight_start"],
        unique=False,
    )
    op.create_index(
        "ix_dji_flight_record_team_start",
        "dji_flight_records",
        ["team_name", "flight_start"],
        unique=False,
    )
    op.create_index(op.f("ix_dji_flight_records_aircraft_name"), "dji_flight_records", ["aircraft_name"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_battery_sn"), "dji_flight_records", ["battery_sn"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_crop"), "dji_flight_records", ["crop"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_field_name"), "dji_flight_records", ["field_name"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_fingerprint"), "dji_flight_records", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_flight_end"), "dji_flight_records", ["flight_end"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_flight_start"), "dji_flight_records", ["flight_start"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_import_id"), "dji_flight_records", ["import_id"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_imported_at"), "dji_flight_records", ["imported_at"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_pilot_name"), "dji_flight_records", ["pilot_name"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_serial_number"), "dji_flight_records", ["serial_number"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_task_type"), "dji_flight_records", ["task_type"], unique=False)
    op.create_index(op.f("ix_dji_flight_records_team_name"), "dji_flight_records", ["team_name"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_dji_flight_records_team_name"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_task_type"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_serial_number"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_pilot_name"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_imported_at"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_import_id"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_flight_start"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_flight_end"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_fingerprint"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_field_name"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_crop"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_battery_sn"), table_name="dji_flight_records")
    op.drop_index(op.f("ix_dji_flight_records_aircraft_name"), table_name="dji_flight_records")
    op.drop_index("ix_dji_flight_record_team_start", table_name="dji_flight_records")
    op.drop_index("ix_dji_flight_record_serial_start", table_name="dji_flight_records")
    op.drop_index("ix_dji_flight_record_pilot_start", table_name="dji_flight_records")
    op.drop_index("ix_dji_flight_record_aircraft_start", table_name="dji_flight_records")
    op.drop_table("dji_flight_records")

    op.drop_index(op.f("ix_dji_flight_log_imports_uploaded_by_id"), table_name="dji_flight_log_imports")
    op.drop_index(op.f("ix_dji_flight_log_imports_uploaded_at"), table_name="dji_flight_log_imports")
    op.drop_index(op.f("ix_dji_flight_log_imports_period_start"), table_name="dji_flight_log_imports")
    op.drop_index(op.f("ix_dji_flight_log_imports_period_end"), table_name="dji_flight_log_imports")
    op.drop_index(op.f("ix_dji_flight_log_imports_file_sha256"), table_name="dji_flight_log_imports")
    op.drop_table("dji_flight_log_imports")
