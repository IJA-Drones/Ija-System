"""recriando base perdida

Revision ID: 1600d07df8f3
Revises: 
Create Date: 2026-03-02 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1600d07df8f3'
down_revision = None # Como a anterior sumiu, definimos esta como a base
branch_labels = None
depends_on = None

def upgrade():
    # --- TABELA PILOTOS ---
    op.create_table('pilotos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome_piloto', sa.String(length=100), nullable=False),
        sa.Column('regiao', sa.String(length=20), nullable=True),
        sa.Column('telefone', sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # --- TABELA EQUIPES ---
    op.create_table('equipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome_equipe', sa.String(length=100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('regiao', sa.String(length=20), nullable=True),
        sa.Column('ativa', sa.Boolean(), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # --- TABELA USUARIOS ---
    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome_uvis', sa.String(length=100), nullable=False),
        sa.Column('regiao', sa.String(length=50), nullable=True),
        sa.Column('codigo_setor', sa.String(length=10), nullable=True),
        sa.Column('login', sa.String(length=50), nullable=False),
        sa.Column('senha_hash', sa.String(length=200), nullable=False),
        sa.Column('tipo_usuario', sa.String(length=20), nullable=True),
        sa.Column('piloto_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['piloto_id'], ['pilotos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('login')
    )

    # --- TABELA EQUIPAMENTOS (Polimorfismo Base) ---
    op.create_table('equipamentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo_equipamento', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('modelo', sa.String(length=100), nullable=False),
        sa.Column('renomacao', sa.String(length=100), nullable=False),
        sa.Column('categoria', sa.String(length=100), nullable=True),
        sa.Column('ano_fabricacao', sa.Integer(), nullable=True),
        sa.Column('numero_serie', sa.String(length=100), nullable=True),
        sa.Column('ultima_manutencao', sa.Date(), nullable=True),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.Column('equipe_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['equipe_id'], ['equipes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('numero_serie')
    )

    # --- TABELA SOLICITACOES ---
    op.create_table('solicitacoes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_agendamento', sa.Date(), nullable=False),
        sa.Column('hora_agendamento', sa.Time(), nullable=False),
        sa.Column('foco', sa.String(length=50), nullable=False),
        sa.Column('tipo_visita', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('piloto_id', sa.Integer(), nullable=True),
        sa.Column('equipe_id', sa.Integer(), nullable=True),
        sa.Column('cep', sa.String(length=9), nullable=False),
        sa.Column('logradouro', sa.String(length=150), nullable=False),
        sa.Column('bairro', sa.String(length=100), nullable=False),
        sa.Column('cidade', sa.String(length=100), nullable=False),
        sa.Column('uf', sa.String(length=2), nullable=False),
        sa.ForeignKeyConstraint(['equipe_id'], ['equipes.id'], ),
        sa.ForeignKeyConstraint(['piloto_id'], ['pilotos.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # --- TABELA ORDENS DE SERVICO ---
    op.create_table('ordens_servico',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('solicitacao_id', sa.Integer(), nullable=False),
        sa.Column('equipe_id', sa.Integer(), nullable=False),
        sa.Column('identificador_os', sa.String(length=100), nullable=True),
        sa.Column('data_aplicacao', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['equipe_id'], ['equipes.id'], ),
        sa.ForeignKeyConstraint(['solicitacao_id'], ['solicitacoes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('solicitacao_id')
    )

    # --- TABELAS FILHAS DE EQUIPAMENTOS ---
    op.create_table('drones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('registro_anatel', sa.String(length=50), nullable=False),
        sa.Column('registro_anac', sa.String(length=50), nullable=False),
        sa.Column('pmd_kg', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['id'], ['equipamentos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('registro_anac')
    )

    op.create_table('baterias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ciclo', sa.Integer(), nullable=True),
        sa.Column('drone_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['drone_id'], ['drones.id'], ),
        sa.ForeignKeyConstraint(['id'], ['equipamentos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('veiculos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('frota', sa.String(length=20), nullable=False),
        sa.Column('operacao', sa.String(length=30), nullable=False),
        sa.Column('placa', sa.String(length=10), nullable=False),
        sa.Column('km_atual', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['id'], ['equipamentos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('placa')
    )

def downgrade():
    op.drop_table('veiculos')
    op.drop_table('baterias')
    op.drop_table('drones')
    op.drop_table('ordens_servico')
    op.drop_table('solicitacoes')
    op.drop_table('equipamentos')
    op.drop_table('usuarios')
    op.drop_table('equipes')
    op.drop_table('pilotos')