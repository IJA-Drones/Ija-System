"""fix agro flight logs after split

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-24 14:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return sa.inspect(bind).has_table(table_name)


def _column_exists(bind, table_name, column_name):
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(bind, table_name, index_name):
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _fk_exists(bind, table_name, fk_name):
    inspector = sa.inspect(bind)
    return fk_name in {
        constraint.get("name")
        for constraint in inspector.get_foreign_keys(table_name)
    }


def _create_agro_flight_tables(bind):
    if not _table_exists(bind, "agro_flight_log_imports"):
        op.create_table(
            "agro_flight_log_imports",
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
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["uploaded_by_id"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("file_sha256"),
        )

    for column in ("uploaded_by_id", "file_sha256", "period_start", "period_end", "uploaded_at"):
        index_name = f"ix_agro_flight_log_imports_{column}"
        if not _index_exists(bind, "agro_flight_log_imports", index_name):
            op.create_index(op.f(index_name), "agro_flight_log_imports", [column], unique=False)

    if not _table_exists(bind, "agro_flight_records"):
        op.create_table(
            "agro_flight_records",
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
            sa.Column("imported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["import_id"], ["agro_flight_log_imports.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fingerprint"),
        )

    for name, columns in (
        ("ix_agro_flight_record_aircraft_start", ["aircraft_name", "flight_start"]),
        ("ix_agro_flight_record_pilot_start", ["pilot_name", "flight_start"]),
        ("ix_agro_flight_record_team_start", ["team_name", "flight_start"]),
        ("ix_agro_flight_record_serial_start", ["serial_number", "flight_start"]),
    ):
        if not _index_exists(bind, "agro_flight_records", name):
            op.create_index(name, "agro_flight_records", columns, unique=False)

    for column in (
        "import_id", "fingerprint", "flight_start", "flight_end", "imported_at",
        "aircraft_name", "task_type", "crop", "pilot_name", "team_name",
        "field_name", "serial_number", "battery_sn",
    ):
        index_name = f"ix_agro_flight_records_{column}"
        if not _index_exists(bind, "agro_flight_records", index_name):
            op.create_index(op.f(index_name), "agro_flight_records", [column], unique=False)

    if not _table_exists(bind, "agro_flight_kml_routes"):
        op.create_table(
            "agro_flight_kml_routes",
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
            sa.Column("imported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["flight_record_id"], ["agro_flight_records.id"]),
            sa.ForeignKeyConstraint(["uploaded_by_id"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("file_sha256"),
            sa.UniqueConstraint("flight_record_id"),
            sa.UniqueConstraint("route_code"),
        )

    for column in (
        "flight_record_id", "uploaded_by_id", "route_code", "file_sha256",
        "aircraft_name", "pilot_name", "flight_controller_id",
        "route_timestamp", "imported_at",
    ):
        index_name = f"ix_agro_flight_kml_routes_{column}"
        if not _index_exists(bind, "agro_flight_kml_routes", index_name):
            op.create_index(op.f(index_name), "agro_flight_kml_routes", [column], unique=False)


def upgrade():
    bind = op.get_bind()
    _create_agro_flight_tables(bind)

    if _table_exists(bind, "ordens_servico_agro"):
        with op.batch_alter_table("ordens_servico_agro", schema=None) as batch_op:
            if not _column_exists(bind, "ordens_servico_agro", "agro_kml_route_id"):
                batch_op.add_column(sa.Column("agro_kml_route_id", sa.Integer(), nullable=True))
            if not _index_exists(bind, "ordens_servico_agro", "ix_ordens_servico_agro_agro_kml_route_id"):
                batch_op.create_index(batch_op.f("ix_ordens_servico_agro_agro_kml_route_id"), ["agro_kml_route_id"], unique=False)
            if not _fk_exists(bind, "ordens_servico_agro", "fk_ordens_servico_agro_agro_kml_route_id_agro_flight_kml_routes"):
                batch_op.create_foreign_key(
                    "fk_ordens_servico_agro_agro_kml_route_id_agro_flight_kml_routes",
                    "agro_flight_kml_routes",
                    ["agro_kml_route_id"],
                    ["id"],
                )

        if _column_exists(bind, "ordens_servico_agro", "dji_kml_route_id"):
            with op.batch_alter_table("ordens_servico_agro", schema=None) as batch_op:
                if _fk_exists(bind, "ordens_servico_agro", "fk_ordens_servico_agro_dji_kml_route_id_dji_flight_kml_routes"):
                    batch_op.drop_constraint(
                        "fk_ordens_servico_agro_dji_kml_route_id_dji_flight_kml_routes",
                        type_="foreignkey",
                    )
                if _index_exists(bind, "ordens_servico_agro", "ix_ordens_servico_agro_dji_kml_route_id"):
                    batch_op.drop_index(batch_op.f("ix_ordens_servico_agro_dji_kml_route_id"))
                batch_op.drop_column("dji_kml_route_id")


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "ordens_servico_agro") and _column_exists(bind, "ordens_servico_agro", "agro_kml_route_id"):
        with op.batch_alter_table("ordens_servico_agro", schema=None) as batch_op:
            if _fk_exists(bind, "ordens_servico_agro", "fk_ordens_servico_agro_agro_kml_route_id_agro_flight_kml_routes"):
                batch_op.drop_constraint(
                    "fk_ordens_servico_agro_agro_kml_route_id_agro_flight_kml_routes",
                    type_="foreignkey",
                )
            if _index_exists(bind, "ordens_servico_agro", "ix_ordens_servico_agro_agro_kml_route_id"):
                batch_op.drop_index(batch_op.f("ix_ordens_servico_agro_agro_kml_route_id"))
            batch_op.drop_column("agro_kml_route_id")

    if _table_exists(bind, "agro_flight_kml_routes"):
        op.drop_table("agro_flight_kml_routes")
    if _table_exists(bind, "agro_flight_records"):
        op.drop_table("agro_flight_records")
    if _table_exists(bind, "agro_flight_log_imports"):
        op.drop_table("agro_flight_log_imports")
