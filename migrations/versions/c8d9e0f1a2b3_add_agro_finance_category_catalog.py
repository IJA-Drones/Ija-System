"""add agro finance category catalog

Revision ID: c8d9e0f1a2b3
Revises: b6c7d8e9f0a1
Create Date: 2026-05-07 13:05:00.000000

"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "c8d9e0f1a2b3"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


ENTRADA_ESTRUTURA = {
    "Entradas - Caixa": (
        "Desconto de Duplicata (+)",
        "Servicos",
        "Venda - Produtos",
        "Venda de Manutencao",
        "Consorcio - Fundo Reserva",
        "Estorno de Tarifa",
        "Socios - Aporte",
        "Vendas de Bens do Imobilizado",
        "Outras Entradas de Caixa",
    ),
    "Emprestimos e Financiamentos": (
        "Emprestimo (Capital de Giro) (+)",
        "Fomento (+)",
        "Outras Entradas Financeiras",
    ),
}


SAIDA_ESTRUTURA = {
    "Fornecedores": (
        "Fornecedores",
        "Materias para Revenda",
    ),
    "Despesas Administrativas": (
        "Energia Eletrica",
        "Agua",
        "Alimentacao",
        "Aluguel de Imovel",
        "Seguro de Imovel",
        "Pesquisa de Restritivos",
        "Material de Escritorio",
        "Sindicatos / Associacoes",
        "Seguranca e Vigilancia",
        "Cartorio",
        "Condominio",
        "Brindes e Premiacao",
        "Estacionamentos",
        "Doacoes",
        "Marcas e Patentes",
        "Material de Limpeza",
        "Motoboy",
        "Frete Nacional",
        "Frete Internacional",
        "Copa e Consumo",
        "Farmacia",
        "Mobilizacao - Obra",
        "Viagens e Representacao",
        "Passagens Aereas",
        "Hospedagem",
        "Marketing",
        "Informatica",
        "Internet",
        "Eqpto. de Informatica",
        "Telefone",
        "Mensalidade Sistema",
    ),
    "Folha de Pagamento": (
        "Salarios",
        "Hora Extra",
        "13 Salario",
        "Ferias",
        "Rescisao",
        "Seguro de Vida",
        "Assistencia Medica",
        "Assistencia Odontologica",
        "Bonus/Gratificacao",
        "Pensao Alimenticia",
        "Refeicao Funcionarios",
        "Reembolso",
        "Medicina do Trabalho",
        "IRRF Salarios",
        "INSS Folha",
        "FGTS",
        "Formacao Profissional",
        "Material de Seguranca (EPI)",
        "Recrutamento e Selecao",
        "Treinamento - Drones",
        "Transporte de Funcionarios",
        "Lavanderia",
        "Acordo Trabalhista",
        "Uniformes",
        "Dissidio",
    ),
    "Comissoes": (
        "Comissao de Captacao de Negocios",
        "Comissao de Vendas",
        "Comissao de Recuperacao de Credito",
        "Comissao de Consorcio (Fundo Reserva)",
        "Outras Comissoes",
    ),
    "Servicos de Terceiros": (
        "CREA",
        "Limpeza",
        "Servicos de Terceiros",
        "Mapeamento",
        "Honorarios Contabil / Consultoria",
        "Patrimonial",
        "Honorarios Juridicos",
        "Consultoria",
    ),
    "Locacao e Equipamentos": (
        "Locacao de Geradores",
        "Locacao de Impressora",
        "Locacao de Equipamentos",
        "Locacao de Computadores",
        "Manutencao de Equipamentos",
        "Combustiveis e Lubrificantes Eq",
    ),
    "Impostos / Retencao": (
        "INSS",
        "IRRF",
        "CSLL",
        "COFINS",
        "PIS/PASEP",
        "ISS",
        "ICMS",
        "Retencao Contrato",
    ),
}


def _table_exists(bind, table_name):
    return sa.inspect(bind).has_table(table_name)


def _seed_pair(bind, categorias, subcategorias, tipo_movimento, prefeitura_id, categoria_nome, subcategoria_nome):
    categoria_nome = (categoria_nome or "").strip()
    subcategoria_nome = (subcategoria_nome or "").strip()
    if not categoria_nome or not subcategoria_nome:
        return

    now = datetime.now()
    categoria_query = sa.select(categorias.c.id).where(
        categorias.c.tipo_movimento == tipo_movimento,
        sa.func.lower(categorias.c.nome) == categoria_nome.lower(),
    )
    if prefeitura_id is None:
        categoria_query = categoria_query.where(categorias.c.prefeitura_id.is_(None))
    else:
        categoria_query = categoria_query.where(categorias.c.prefeitura_id == prefeitura_id)

    categoria_id = bind.execute(categoria_query).scalar()
    if categoria_id is None:
        bind.execute(
            categorias.insert().values(
                prefeitura_id=prefeitura_id,
                tipo_movimento=tipo_movimento,
                nome=categoria_nome,
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            )
        )
        categoria_id = bind.execute(categoria_query).scalar()

    subcategoria_id = bind.execute(
        sa.select(subcategorias.c.id).where(
            subcategorias.c.categoria_id == categoria_id,
            sa.func.lower(subcategorias.c.nome) == subcategoria_nome.lower(),
        )
    ).scalar()
    if subcategoria_id is None:
        bind.execute(
            subcategorias.insert().values(
                categoria_id=categoria_id,
                nome=subcategoria_nome,
                ativo=True,
                criado_em=now,
                atualizado_em=now,
            )
        )


def _seed_defaults(bind, categorias, subcategorias):
    for categoria, itens in ENTRADA_ESTRUTURA.items():
        for subcategoria in itens:
            _seed_pair(bind, categorias, subcategorias, "ENTRADA", None, categoria, subcategoria)

    for categoria, itens in SAIDA_ESTRUTURA.items():
        for subcategoria in itens:
            _seed_pair(bind, categorias, subcategorias, "SAIDA", None, categoria, subcategoria)


def _seed_existing_launches(bind, categorias, subcategorias):
    if _table_exists(bind, "financeiro_agro_entradas"):
        rows = bind.execute(
            sa.text(
                """
                SELECT DISTINCT prefeitura_id, categoria, subcategoria
                FROM financeiro_agro_entradas
                WHERE categoria IS NOT NULL
                  AND TRIM(categoria) <> ''
                  AND subcategoria IS NOT NULL
                  AND TRIM(subcategoria) <> ''
                """
            )
        )
        for row in rows:
            _seed_pair(bind, categorias, subcategorias, "ENTRADA", row.prefeitura_id, row.categoria, row.subcategoria)

    if _table_exists(bind, "financeiro_agro_saidas"):
        rows = bind.execute(
            sa.text(
                """
                SELECT DISTINCT prefeitura_id, categoria, subcategoria
                FROM financeiro_agro_saidas
                WHERE categoria IS NOT NULL
                  AND TRIM(categoria) <> ''
                  AND subcategoria IS NOT NULL
                  AND TRIM(subcategoria) <> ''
                """
            )
        )
        for row in rows:
            _seed_pair(bind, categorias, subcategorias, "SAIDA", row.prefeitura_id, row.categoria, row.subcategoria)


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "financeiro_agro_categorias"):
        op.create_table(
            "financeiro_agro_categorias",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("tipo_movimento", sa.String(length=20), nullable=False),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("prefeitura_id", "tipo_movimento", "nome", name="uq_financeiro_agro_categoria_pref_tipo_nome"),
        )
        op.create_index(op.f("ix_financeiro_agro_categorias_id"), "financeiro_agro_categorias", ["id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_prefeitura_id"), "financeiro_agro_categorias", ["prefeitura_id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_tipo_movimento"), "financeiro_agro_categorias", ["tipo_movimento"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_nome"), "financeiro_agro_categorias", ["nome"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_ativo"), "financeiro_agro_categorias", ["ativo"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_criado_em"), "financeiro_agro_categorias", ["criado_em"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_categorias_atualizado_em"), "financeiro_agro_categorias", ["atualizado_em"], unique=False)
        op.create_index(
            "ix_financeiro_agro_categoria_pref_tipo_ativo",
            "financeiro_agro_categorias",
            ["prefeitura_id", "tipo_movimento", "ativo"],
            unique=False,
        )

    if not _table_exists(bind, "financeiro_agro_subcategorias"):
        op.create_table(
            "financeiro_agro_subcategorias",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("categoria_id", sa.Integer(), nullable=False),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["categoria_id"], ["financeiro_agro_categorias.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("categoria_id", "nome", name="uq_financeiro_agro_subcategoria_categoria_nome"),
        )
        op.create_index(op.f("ix_financeiro_agro_subcategorias_id"), "financeiro_agro_subcategorias", ["id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_subcategorias_categoria_id"), "financeiro_agro_subcategorias", ["categoria_id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_subcategorias_nome"), "financeiro_agro_subcategorias", ["nome"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_subcategorias_ativo"), "financeiro_agro_subcategorias", ["ativo"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_subcategorias_criado_em"), "financeiro_agro_subcategorias", ["criado_em"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_subcategorias_atualizado_em"), "financeiro_agro_subcategorias", ["atualizado_em"], unique=False)
        op.create_index(
            "ix_financeiro_agro_subcategoria_categoria_ativo",
            "financeiro_agro_subcategorias",
            ["categoria_id", "ativo"],
            unique=False,
        )

    categorias = sa.table(
        "financeiro_agro_categorias",
        sa.column("id", sa.Integer),
        sa.column("prefeitura_id", sa.Integer),
        sa.column("tipo_movimento", sa.String),
        sa.column("nome", sa.String),
        sa.column("ativo", sa.Boolean),
        sa.column("criado_em", sa.DateTime),
        sa.column("atualizado_em", sa.DateTime),
    )
    subcategorias = sa.table(
        "financeiro_agro_subcategorias",
        sa.column("id", sa.Integer),
        sa.column("categoria_id", sa.Integer),
        sa.column("nome", sa.String),
        sa.column("ativo", sa.Boolean),
        sa.column("criado_em", sa.DateTime),
        sa.column("atualizado_em", sa.DateTime),
    )
    _seed_defaults(bind, categorias, subcategorias)
    _seed_existing_launches(bind, categorias, subcategorias)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_subcategorias"):
        op.drop_index("ix_financeiro_agro_subcategoria_categoria_ativo", table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_atualizado_em"), table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_criado_em"), table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_ativo"), table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_nome"), table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_categoria_id"), table_name="financeiro_agro_subcategorias")
        op.drop_index(op.f("ix_financeiro_agro_subcategorias_id"), table_name="financeiro_agro_subcategorias")
        op.drop_table("financeiro_agro_subcategorias")

    if _table_exists(bind, "financeiro_agro_categorias"):
        op.drop_index("ix_financeiro_agro_categoria_pref_tipo_ativo", table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_atualizado_em"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_criado_em"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_ativo"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_nome"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_tipo_movimento"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_prefeitura_id"), table_name="financeiro_agro_categorias")
        op.drop_index(op.f("ix_financeiro_agro_categorias_id"), table_name="financeiro_agro_categorias")
        op.drop_table("financeiro_agro_categorias")
