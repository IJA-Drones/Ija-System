"""Add optional fiscal registration to financial company profiles."""
from alembic import op
import sqlalchemy as sa

revision = "a30f10c26e01"
down_revision = "b84f20d19a6e"
branch_labels = None
depends_on = None

FIELDS = {'inscricao_municipal': 30, 'inscricao_estadual': 30, 'regime_tributario': 1, 'cnae_principal': 7, 'email_fiscal': 254, 'telefone_fiscal': 11, 'cep': 8, 'logradouro': 180, 'numero': 20, 'complemento': 120, 'bairro': 100, 'municipio': 100, 'uf': 2, 'codigo_municipio_ibge': 7}


def upgrade():
    with op.batch_alter_table("financeiro_empresa_perfis") as batch:
        for name, size in FIELDS.items():
            batch.add_column(sa.Column(name, sa.String(size), nullable=True))


def downgrade():
    with op.batch_alter_table("financeiro_empresa_perfis") as batch:
        for name in reversed(FIELDS):
            batch.drop_column(name)
