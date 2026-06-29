"""add usuario presencas

Revision ID: f6a1b2c3d4e5
Revises: e9c3a1b7d4f2
Create Date: 2026-06-29 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f6a1b2c3d4e5"
down_revision = "e9c3a1b7d4f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usuario_presencas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("primeiro_acesso_em", sa.DateTime(), nullable=False),
        sa.Column("ultimo_acesso_em", sa.DateTime(), nullable=False),
        sa.Column("login_em", sa.DateTime(), nullable=True),
        sa.Column("logout_em", sa.DateTime(), nullable=True),
        sa.Column("ultimo_metodo", sa.String(length=10), nullable=True),
        sa.Column("ultimo_endpoint", sa.String(length=120), nullable=True),
        sa.Column("ultimo_path", sa.String(length=255), nullable=False),
        sa.Column("ultimo_query_string", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("referrer", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id"),
    )
    op.create_index(op.f("ix_usuario_presencas_ip"), "usuario_presencas", ["ip"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_login_em"), "usuario_presencas", ["login_em"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_logout_em"), "usuario_presencas", ["logout_em"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_primeiro_acesso_em"), "usuario_presencas", ["primeiro_acesso_em"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_ultimo_acesso_em"), "usuario_presencas", ["ultimo_acesso_em"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_ultimo_endpoint"), "usuario_presencas", ["ultimo_endpoint"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_ultimo_path"), "usuario_presencas", ["ultimo_path"], unique=False)
    op.create_index(op.f("ix_usuario_presencas_usuario_id"), "usuario_presencas", ["usuario_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_usuario_presencas_usuario_id"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_ultimo_path"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_ultimo_endpoint"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_ultimo_acesso_em"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_primeiro_acesso_em"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_logout_em"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_login_em"), table_name="usuario_presencas")
    op.drop_index(op.f("ix_usuario_presencas_ip"), table_name="usuario_presencas")
    op.drop_table("usuario_presencas")
