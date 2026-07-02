"""add_status_to_equipe_uvis_os

Revision ID: b7c8d9e0f1a2
Revises: f6a1b2c3d4e5
Create Date: 2026-07-02 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE ordens_servico_equipe_uvis
        ADD COLUMN IF NOT EXISTS status VARCHAR(30)
        """
    )
    op.execute(
        """
        UPDATE ordens_servico_equipe_uvis
        SET status = 'EM_ANDAMENTO'
        WHERE status IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE ordens_servico_equipe_uvis
        ALTER COLUMN status SET NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ordens_servico_equipe_uvis_status
        ON ordens_servico_equipe_uvis (status)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_ordens_servico_equipe_uvis_status")
    op.execute("ALTER TABLE ordens_servico_equipe_uvis DROP COLUMN IF EXISTS status")
