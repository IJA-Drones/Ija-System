"""Keep driver identity and actual shift closing time for GPS reconciliation.

Legacy shifts deliberately keep an unknown end time; creation/fuel timestamps
cannot establish when a vehicle was returned.
"""
from alembic import op
import sqlalchemy as sa

revision = "a3e5c7d901b2"
down_revision = "f8d2a6c4e901"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("logs_veiculo") as batch:
        batch.add_column(sa.Column("encerrado_em", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("condutor_nome", sa.String(120), nullable=True))
    with op.batch_alter_table("rastreamento_posicoes") as batch:
        batch.add_column(sa.Column("telemetria", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("rastreamento_posicoes") as batch:
        batch.drop_column("telemetria")
    with op.batch_alter_table("logs_veiculo") as batch:
        batch.drop_column("condutor_nome")
        batch.drop_column("encerrado_em")
