"""add_auditoria_usuarios

Revision ID: 4f8c2e1a9b7d
Revises: 72a0e35b108f
Create Date: 2026-04-01 15:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f8c2e1a9b7d"
down_revision = "72a0e35b108f"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "auditoria_usuarios" not in inspector.get_table_names():
        op.create_table(
            "auditoria_usuarios",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=True),
            sa.Column("usuario_nome", sa.String(length=100), nullable=False),
            sa.Column("usuario_login", sa.String(length=50), nullable=True),
            sa.Column("tipo_usuario", sa.String(length=20), nullable=True),
            sa.Column("metodo", sa.String(length=10), nullable=False),
            sa.Column("tipo_evento", sa.String(length=20), nullable=False),
            sa.Column("endpoint", sa.String(length=120), nullable=True),
            sa.Column("path", sa.String(length=255), nullable=False),
            sa.Column("query_string", sa.Text(), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("referrer", sa.String(length=255), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("auditoria_usuarios")
    }
    required_indexes = [
        ("ix_auditoria_usuarios_criado_em", ["criado_em"]),
        ("ix_auditoria_usuarios_endpoint", ["endpoint"]),
        ("ix_auditoria_usuarios_ip", ["ip"]),
        ("ix_auditoria_usuarios_metodo", ["metodo"]),
        ("ix_auditoria_usuarios_path", ["path"]),
        ("ix_auditoria_usuarios_status_code", ["status_code"]),
        ("ix_auditoria_usuarios_tipo_evento", ["tipo_evento"]),
        ("ix_auditoria_usuarios_tipo_usuario", ["tipo_usuario"]),
        ("ix_auditoria_usuarios_usuario_id", ["usuario_id"]),
        ("ix_auditoria_usuarios_usuario_login", ["usuario_login"]),
        ("ix_auditoria_usuarios_usuario_nome", ["usuario_nome"]),
    ]
    for index_name, columns in required_indexes:
        if index_name not in existing_indexes:
            op.create_index(index_name, "auditoria_usuarios", columns, unique=False)


def downgrade():
    op.drop_index(op.f("ix_auditoria_usuarios_usuario_nome"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_usuario_login"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_usuario_id"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_tipo_usuario"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_tipo_evento"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_status_code"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_path"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_metodo"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_ip"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_endpoint"), table_name="auditoria_usuarios")
    op.drop_index(op.f("ix_auditoria_usuarios_criado_em"), table_name="auditoria_usuarios")
    op.drop_table("auditoria_usuarios")
