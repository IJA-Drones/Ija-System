"""servidor SMTP configurado pelo sistema

Revision ID: 2283da228381
Revises: 74f7339f497d
"""
from alembic import op
import sqlalchemy as sa

revision = "2283da228381"
down_revision = "74f7339f497d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("configuracao_smtp",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host", sa.String(200), nullable=False),
        sa.Column("porta", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("seguranca", sa.String(10), nullable=False, server_default="starttls"),
        sa.Column("remetente", sa.String(254), nullable=False),
        sa.Column("usuario", sa.String(254)),
        sa.Column("senha_cifrada", sa.Text()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("configuracao_smtp")
