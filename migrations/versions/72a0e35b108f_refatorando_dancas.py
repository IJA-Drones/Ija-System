"""refatorando_dancas

Revision ID: 72a0e35b108f
Revises: f1e2d3c4b5a6
Create Date: 2026-04-01 11:39:48.826562

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "72a0e35b108f"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dji_flight_kml_routes", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("dji_flight_kml_routes_file_sha256_key"), type_="unique")
        batch_op.drop_constraint(batch_op.f("dji_flight_kml_routes_flight_record_id_key"), type_="unique")
        batch_op.drop_constraint(batch_op.f("dji_flight_kml_routes_route_code_key"), type_="unique")
        batch_op.drop_index(batch_op.f("ix_dji_flight_kml_routes_flight_record_id"))
        batch_op.create_index(
            batch_op.f("ix_dji_flight_kml_routes_flight_record_id"),
            ["flight_record_id"],
            unique=True,
        )
        batch_op.drop_index(batch_op.f("ix_dji_flight_kml_routes_route_code"))
        batch_op.create_index(
            batch_op.f("ix_dji_flight_kml_routes_route_code"),
            ["route_code"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_dji_flight_kml_routes_file_sha256"),
            ["file_sha256"],
            unique=True,
        )

    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo_operacao", sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f("ix_solicitacoes_tipo_operacao"), ["tipo_operacao"], unique=False)


def downgrade():
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_solicitacoes_tipo_operacao"))
        batch_op.drop_column("tipo_operacao")

    with op.batch_alter_table("dji_flight_kml_routes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dji_flight_kml_routes_file_sha256"))
        batch_op.drop_index(batch_op.f("ix_dji_flight_kml_routes_route_code"))
        batch_op.create_index(
            batch_op.f("ix_dji_flight_kml_routes_route_code"),
            ["route_code"],
            unique=False,
        )
        batch_op.drop_index(batch_op.f("ix_dji_flight_kml_routes_flight_record_id"))
        batch_op.create_index(
            batch_op.f("ix_dji_flight_kml_routes_flight_record_id"),
            ["flight_record_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            batch_op.f("dji_flight_kml_routes_route_code_key"),
            ["route_code"],
            postgresql_nulls_not_distinct=False,
        )
        batch_op.create_unique_constraint(
            batch_op.f("dji_flight_kml_routes_flight_record_id_key"),
            ["flight_record_id"],
            postgresql_nulls_not_distinct=False,
        )
        batch_op.create_unique_constraint(
            batch_op.f("dji_flight_kml_routes_file_sha256_key"),
            ["file_sha256"],
            postgresql_nulls_not_distinct=False,
        )
