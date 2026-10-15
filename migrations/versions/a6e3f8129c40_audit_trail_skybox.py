"""Detailed audit events and durable Skybox archive queue."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = 'a6e3f8129c40'
down_revision = 'd94f2a7610be'
branch_labels = None
depends_on = None


def upgrade():
    installation = op.create_table('auditoria_instalacao',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('identificador', sa.String(36), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_auditoria_instalacao_singleton'))
    op.bulk_insert(installation, [{'id': 1, 'identificador': str(uuid4())}])
    op.create_table('auditoria_arquivos',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('caminho', sa.String(500), nullable=False, unique=True),
        sa.Column('conteudo', sa.Text(), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('prefeitura_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('enviado_em', sa.DateTime(), nullable=True),
        sa.Column('tentativas', sa.Integer(), nullable=False),
        sa.Column('proxima_tentativa', sa.DateTime(), nullable=False),
        sa.Column('lease_token', sa.String(36), nullable=True),
        sa.Column('lease_ate', sa.DateTime(), nullable=True),
        sa.Column('ultimo_erro', sa.String(200), nullable=True))
    op.create_index('ix_auditoria_arquivos_proxima_tentativa', 'auditoria_arquivos', ['proxima_tentativa'])
    with op.batch_alter_table('auditoria_usuarios') as batch:
        for name, kind in [('evento_id', sa.String(36)), ('requisicao_id', sa.String(36)),
                           ('prefeitura_id', sa.Integer()), ('prefeitura_usuario_id', sa.Integer()),
                           ('objeto_tipo', sa.String(100)), ('objeto_id', sa.String(100)),
                           ('resultado', sa.String(30)), ('detalhes', sa.JSON()),
                           ('arquivo_id', sa.String(36)), ('arquivado_em', sa.DateTime())]:
            batch.add_column(sa.Column(name, kind, nullable=True))
        batch.create_unique_constraint('uq_auditoria_usuarios_evento_id', ['evento_id'])
        batch.create_foreign_key('fk_auditoria_usuarios_arquivo', 'auditoria_arquivos', ['arquivo_id'], ['id'])
        for name in ('requisicao_id', 'prefeitura_id', 'objeto_tipo', 'resultado', 'arquivo_id', 'arquivado_em'):
            batch.create_index(f'ix_auditoria_usuarios_{name}', [name])


def downgrade():
    with op.batch_alter_table('auditoria_usuarios') as batch:
        batch.drop_constraint('fk_auditoria_usuarios_arquivo', type_='foreignkey')
        batch.drop_constraint('uq_auditoria_usuarios_evento_id', type_='unique')
        for name in ('requisicao_id', 'prefeitura_id', 'objeto_tipo', 'resultado', 'arquivo_id', 'arquivado_em'):
            batch.drop_index(f'ix_auditoria_usuarios_{name}')
        for name in ('evento_id', 'requisicao_id', 'prefeitura_id', 'prefeitura_usuario_id',
                     'objeto_tipo', 'objeto_id', 'resultado', 'detalhes', 'arquivo_id', 'arquivado_em'):
            batch.drop_column(name)
    op.drop_table('auditoria_arquivos')
    op.drop_table('auditoria_instalacao')
