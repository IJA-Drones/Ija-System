"""PENDING: add isolated proposed configurations for the TI central.

No existing user, permission, or business record is updated.
Kept outside versions/ so the deployment's automatic upgrade cannot apply it.
Move to versions/ only when the user is ready to migrate the authorized database.
The isolated Neon preparation can install these tables without advancing the
general migration history. A later regular upgrade validates and reuses them.
"""

from alembic import op
import sqlalchemy as sa


revision = "c1a0f8b6d2e4"
down_revision = "f2c531cc9f71"
branch_labels = None
depends_on = None


EXPECTED_COLUMNS = {
    "central_ti_perfis_configuracoes": {"perfil_codigo", "versao", "atualizado_em", "atualizado_por_id"},
    "central_ti_selecoes": {"perfil_codigo", "codigo"},
    "central_ti_auditoria": {"id", "lote", "perfil_codigo", "usuario_id", "usuario_login", "versao_anterior", "versao_nova", "antes", "depois", "criado_em"},
}


def validate_existing_schema(connection):
    inspector = sa.inspect(connection)
    for table, expected in EXPECTED_COLUMNS.items():
        if {column["name"] for column in inspector.get_columns(table)} != expected:
            raise RuntimeError(f"Estrutura inesperada em {table}; nenhuma alteração foi aplicada.")
    requirements = {
        "central_ti_perfis_configuracoes": ({"perfil_codigo"}, "ck_central_ti_perfil_versao", "atualizado_por_id", "usuarios"),
        "central_ti_selecoes": ({"perfil_codigo", "codigo"}, None, "perfil_codigo", "central_ti_perfis_configuracoes"),
        "central_ti_auditoria": ({"id"}, "ck_central_ti_auditoria_versao", "usuario_id", "usuarios"),
    }
    for table, (primary_key, check, foreign_key, referenced_table) in requirements.items():
        if set(inspector.get_pk_constraint(table)["constrained_columns"]) != primary_key:
            raise RuntimeError(f"Chave primária inesperada em {table}.")
        if check and check not in {constraint["name"] for constraint in inspector.get_check_constraints(table)}:
            raise RuntimeError(f"Restrição ausente em {table}.")
        if not any(fk["constrained_columns"] == [foreign_key] and fk["referred_table"] == referenced_table
                   for fk in inspector.get_foreign_keys(table)):
            raise RuntimeError(f"Vínculo ausente em {table}.")
    indexes = {index["name"] for index in inspector.get_indexes("central_ti_auditoria")}
    if not {"ix_central_ti_auditoria_lote", "ix_central_ti_auditoria_perfil_codigo"} <= indexes:
        raise RuntimeError("Índices de auditoria ausentes.")


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names()) & set(EXPECTED_COLUMNS)
    if existing:
        if existing != set(EXPECTED_COLUMNS):
            raise RuntimeError("Estrutura parcial da Central de TI; revise antes de migrar.")
        validate_existing_schema(op.get_bind())
        return
    op.create_table(
        "central_ti_perfis_configuracoes",
        sa.Column("perfil_codigo", sa.String(20), primary_key=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("versao >= 1", name="ck_central_ti_perfil_versao"),
    )
    op.create_table(
        "central_ti_selecoes",
        sa.Column("perfil_codigo", sa.String(20), sa.ForeignKey("central_ti_perfis_configuracoes.perfil_codigo", ondelete="CASCADE"), primary_key=True),
        sa.Column("codigo", sa.String(120), primary_key=True),
    )
    op.create_table(
        "central_ti_auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote", sa.String(36), nullable=False),
        sa.Column("perfil_codigo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usuario_login", sa.String(50), nullable=False),
        sa.Column("versao_anterior", sa.Integer(), nullable=False),
        sa.Column("versao_nova", sa.Integer(), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=False),
        sa.Column("depois", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("versao_anterior >= 0 AND versao_nova > versao_anterior", name="ck_central_ti_auditoria_versao"),
    )
    op.create_index("ix_central_ti_auditoria_lote", "central_ti_auditoria", ["lote"])
    op.create_index("ix_central_ti_auditoria_perfil_codigo", "central_ti_auditoria", ["perfil_codigo"])


def downgrade():
    # Only remove these configuration tables, never existing users/business data.
    op.drop_table("central_ti_auditoria")
    op.drop_table("central_ti_selecoes")
    op.drop_table("central_ti_perfis_configuracoes")
