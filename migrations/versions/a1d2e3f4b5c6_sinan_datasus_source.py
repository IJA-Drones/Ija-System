"""sinan: origem datasus (DBC oficial)

Revision ID: a1d2e3f4b5c6
Revises: b84f20d19a6e
"""
from alembic import op

revision = "a1d2e3f4b5c6"
down_revision = "b84f20d19a6e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vigilancia_sinan_lotes") as batch:
        batch.drop_constraint("ck_sinan_lote_kind", type_="check")
        batch.create_check_constraint("ck_sinan_lote_kind", "kind IN ('api','csv','datasus')")


def downgrade():
    with op.batch_alter_table("vigilancia_sinan_lotes") as batch:
        batch.drop_constraint("ck_sinan_lote_kind", type_="check")
        batch.create_check_constraint("ck_sinan_lote_kind", "kind IN ('api','csv')")
