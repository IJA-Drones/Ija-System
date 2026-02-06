"""add index

Revision ID: 7b93d7f7f030
Revises: 8401125b2639
Create Date: 2025-12-30 12:05:13.996438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b93d7f7f030'
down_revision = '8401125b2639'
branch_labels = None
depends_on = None


def _create_index_if_not_exists(name: str, table: str, cols: list[str], unique: bool = False):
    uq = "UNIQUE " if unique else ""
    cols_sql = ", ".join([f'"{c}"' for c in cols])
    op.execute(sa.text(f'CREATE {uq}INDEX IF NOT EXISTS "{name}" ON "{table}" ({cols_sql});'))


def _drop_index_if_exists(name: str):
    op.execute(sa.text(f'DROP INDEX IF EXISTS "{name}";'))


def upgrade():
    # === CLIENTES ===
    # Evita erro se a constraint não existir com esse nome no banco
    clientes_doc_key = op.f('clientes_documento_key')
    op.execute(sa.text(f'ALTER TABLE "clientes" DROP CONSTRAINT IF EXISTS "{clientes_doc_key}";'))

    _create_index_if_not_exists(op.f('ix_clientes_documento'), 'clientes', ['documento'], unique=True)
    _create_index_if_not_exists(op.f('ix_clientes_email'), 'clientes', ['email'], unique=False)

    # === NOTIFICACOES ===
    _create_index_if_not_exists(op.f('ix_notificacoes_apagada_em'), 'notificacoes', ['apagada_em'], unique=False)
    _create_index_if_not_exists(op.f('ix_notificacoes_criada_em'), 'notificacoes', ['criada_em'], unique=False)
    _create_index_if_not_exists(op.f('ix_notificacoes_lida_em'), 'notificacoes', ['lida_em'], unique=False)
    _create_index_if_not_exists(op.f('ix_notificacoes_usuario_id'), 'notificacoes', ['usuario_id'], unique=False)

    # === SOLICITACOES ===
    _create_index_if_not_exists('ix_solicitacao_data_status', 'solicitacoes', ['data_criacao', 'status'], unique=False)
    _create_index_if_not_exists('ix_solicitacao_usuario_data', 'solicitacoes', ['usuario_id', 'data_criacao'], unique=False)

    _create_index_if_not_exists(op.f('ix_solicitacoes_altura_voo'), 'solicitacoes', ['altura_voo'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_bairro'), 'solicitacoes', ['bairro'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_cidade'), 'solicitacoes', ['cidade'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_data_agendamento'), 'solicitacoes', ['data_agendamento'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_foco'), 'solicitacoes', ['foco'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_protocolo'), 'solicitacoes', ['protocolo'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_tipo_visita'), 'solicitacoes', ['tipo_visita'], unique=False)
    _create_index_if_not_exists(op.f('ix_solicitacoes_uf'), 'solicitacoes', ['uf'], unique=False)

    # === USUARIOS ===
    usuarios_login_key = op.f('usuarios_login_key')
    op.execute(sa.text(f'ALTER TABLE "usuarios" DROP CONSTRAINT IF EXISTS "{usuarios_login_key}";'))

    _create_index_if_not_exists(op.f('ix_usuarios_login'), 'usuarios', ['login'], unique=True)
    _create_index_if_not_exists(op.f('ix_usuarios_nome_uvis'), 'usuarios', ['nome_uvis'], unique=False)
    _create_index_if_not_exists(op.f('ix_usuarios_regiao'), 'usuarios', ['regiao'], unique=False)
    _create_index_if_not_exists(op.f('ix_usuarios_tipo_usuario'), 'usuarios', ['tipo_usuario'], unique=False)


def downgrade():
    # === USUARIOS ===
    _drop_index_if_exists(op.f('ix_usuarios_tipo_usuario'))
    _drop_index_if_exists(op.f('ix_usuarios_regiao'))
    _drop_index_if_exists(op.f('ix_usuarios_nome_uvis'))
    _drop_index_if_exists(op.f('ix_usuarios_login'))

    usuarios_login_key = op.f('usuarios_login_key')
    op.execute(sa.text(f"""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'usuarios' AND c.conname = '{usuarios_login_key}'
      ) THEN
        EXECUTE 'ALTER TABLE "usuarios" ADD CONSTRAINT "{usuarios_login_key}" UNIQUE ("login")';
      END IF;
    END $$;
    """))

    # === SOLICITACOES ===
    _drop_index_if_exists(op.f('ix_solicitacoes_uf'))
    _drop_index_if_exists(op.f('ix_solicitacoes_tipo_visita'))
    _drop_index_if_exists(op.f('ix_solicitacoes_protocolo'))
    _drop_index_if_exists(op.f('ix_solicitacoes_foco'))
    _drop_index_if_exists(op.f('ix_solicitacoes_data_agendamento'))
    _drop_index_if_exists(op.f('ix_solicitacoes_cidade'))
    _drop_index_if_exists(op.f('ix_solicitacoes_bairro'))
    _drop_index_if_exists(op.f('ix_solicitacoes_altura_voo'))
    _drop_index_if_exists('ix_solicitacao_usuario_data')
    _drop_index_if_exists('ix_solicitacao_data_status')

    # === NOTIFICACOES ===
    _drop_index_if_exists(op.f('ix_notificacoes_usuario_id'))
    _drop_index_if_exists(op.f('ix_notificacoes_lida_em'))
    _drop_index_if_exists(op.f('ix_notificacoes_criada_em'))
    _drop_index_if_exists(op.f('ix_notificacoes_apagada_em'))

    # === CLIENTES ===
    _drop_index_if_exists(op.f('ix_clientes_email'))
    _drop_index_if_exists(op.f('ix_clientes_documento'))

    clientes_doc_key = op.f('clientes_documento_key')
    op.execute(sa.text(f"""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'clientes' AND c.conname = '{clientes_doc_key}'
      ) THEN
        EXECUTE 'ALTER TABLE "clientes" ADD CONSTRAINT "{clientes_doc_key}" UNIQUE ("documento")';
      END IF;
    END $$;
    """))
