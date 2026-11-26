"""Agenda e registros de manutenção preventiva por equipamento."""
from alembic import op
import sqlalchemy as sa
revision='c3f81b7e9240'
down_revision='b7d3e91a6204'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('preventiva_planos',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('equipamento_id',sa.Integer(),sa.ForeignKey('equipamentos.id',ondelete='RESTRICT'),nullable=False,unique=True),
        sa.Column('prefeitura_id',sa.Integer(),sa.ForeignKey('prefeituras.id'),nullable=False),
        sa.Column('intervalo_dias',sa.Integer(),nullable=False),
        sa.Column('ultima_realizada_em',sa.Date()),
        sa.Column('versao',sa.Integer(),nullable=False),
        sa.Column('atualizado_em',sa.DateTime(),nullable=False),
        sa.CheckConstraint('intervalo_dias IN (60, 90)',name='ck_preventiva_intervalo'))
    op.create_table('preventiva_registros',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('plano_id',sa.Integer(),sa.ForeignKey('preventiva_planos.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('usuario_id',sa.Integer(),sa.ForeignKey('usuarios.id',ondelete='SET NULL')),
        sa.Column('usuario_nome',sa.String(200),nullable=False),
        sa.Column('criado_em',sa.DateTime(),nullable=False),
        sa.Column('tipo',sa.String(20),nullable=False),
        sa.Column('realizada_em',sa.Date()),
        sa.Column('descricao',sa.Text(),nullable=False),
        sa.Column('dados',sa.JSON(),nullable=False),
        sa.Column('manutencao_id',sa.Integer(),sa.ForeignKey('manutencoes_equipamentos.id',ondelete='RESTRICT')))
    op.create_index('ix_preventiva_registros_plano_id','preventiva_registros',['plano_id'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM preventiva_planos LIMIT 1')).first():
        raise RuntimeError('Preserve os planos e históricos antes de reverter esta migração.')
    op.drop_table('preventiva_registros')
    op.drop_table('preventiva_planos')
