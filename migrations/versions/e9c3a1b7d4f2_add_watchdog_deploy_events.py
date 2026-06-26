"""add watchdog deploy events

Revision ID: e9c3a1b7d4f2
Revises: e4b7c9d1f2a3
Create Date: 2026-06-26 16:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e9c3a1b7d4f2"
down_revision = "e4b7c9d1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "watchdog_deploy_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("health_url", sa.String(length=255), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("recovered_at", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_watchdog_deploy_events_criado_em"), "watchdog_deploy_events", ["criado_em"], unique=False)
    op.create_index(op.f("ix_watchdog_deploy_events_event_id"), "watchdog_deploy_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_watchdog_deploy_events_recovered_at"), "watchdog_deploy_events", ["recovered_at"], unique=False)
    op.create_index(op.f("ix_watchdog_deploy_events_source"), "watchdog_deploy_events", ["source"], unique=False)
    op.create_index(op.f("ix_watchdog_deploy_events_started_at"), "watchdog_deploy_events", ["started_at"], unique=False)
    op.create_index(op.f("ix_watchdog_deploy_events_status"), "watchdog_deploy_events", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_watchdog_deploy_events_status"), table_name="watchdog_deploy_events")
    op.drop_index(op.f("ix_watchdog_deploy_events_started_at"), table_name="watchdog_deploy_events")
    op.drop_index(op.f("ix_watchdog_deploy_events_source"), table_name="watchdog_deploy_events")
    op.drop_index(op.f("ix_watchdog_deploy_events_recovered_at"), table_name="watchdog_deploy_events")
    op.drop_index(op.f("ix_watchdog_deploy_events_event_id"), table_name="watchdog_deploy_events")
    op.drop_index(op.f("ix_watchdog_deploy_events_criado_em"), table_name="watchdog_deploy_events")
    op.drop_table("watchdog_deploy_events")
