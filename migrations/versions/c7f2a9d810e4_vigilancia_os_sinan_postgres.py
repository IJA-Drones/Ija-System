"""Vínculo entre campo e OS e persistência SINAN no banco do IJA.

Revision ID: c7f2a9d810e4
Revises: b6e9d2a4f017
"""
from alembic import op
import sqlalchemy as sa

revision = "c7f2a9d810e4"
down_revision = "b6e9d2a4f017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vigilancia_campo_os",
        sa.Column("batch_id", sa.String(32), sa.ForeignKey("vigilancia_campo_lotes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("solicitacao_id", sa.Integer(), sa.ForeignKey("solicitacoes.id", ondelete="SET NULL")),
    )
    op.create_index("ix_vigilancia_campo_os_solicitacao_id", "vigilancia_campo_os", ["solicitacao_id"])
    op.create_table("vigilancia_sinan_lotes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("disease", sa.String(20), nullable=False),
        sa.Column("ibge", sa.String(7), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.Column("updated", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("cancel", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.CheckConstraint("status IN ('running','completed','partial','failed','cancelled')", name="ck_sinan_lote_status"),
        sa.CheckConstraint("kind IN ('api','csv')", name="ck_sinan_lote_kind"),
    )
    op.create_index("ix_sinan_owner_scope", "vigilancia_sinan_lotes", ["owner", "disease", "ibge", "year", "created"])
    op.create_index("uq_sinan_worker", "vigilancia_sinan_lotes", ["status"], unique=True,
        postgresql_where=sa.text("status = 'running'"), sqlite_where=sa.text("status = 'running'"))
    op.create_table("vigilancia_sinan_casos",
        sa.Column("job_id", sa.String(32), sa.ForeignKey("vigilancia_sinan_lotes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("reference", sa.String(80), primary_key=True),
        sa.Column("week", sa.String(6)),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("vigilancia_sinan_casos")
    op.drop_table("vigilancia_sinan_lotes")
    op.drop_table("vigilancia_campo_os")
