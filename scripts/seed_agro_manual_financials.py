from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.extensions import db
from app.models import ClienteAgro, FinanceiroAgroEntrada, FinanceiroAgroSaida

SEED_TAG = "SEED-AGRO"


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _decimal(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


ENTRADAS = [
    {
        "documento_referencia": f"{SEED_TAG}-ENT-001",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Servicos",
        "descricao": "Recebimento de servico de pulverizacao da Fazenda Santa Luzia.",
        "forma_recebimento": "PIX",
        "valor": "4850.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-01",
        "data_emissao": "2026-04-01",
        "data_vencimento": "2026-04-02",
        "data_recebimento": "2026-04-02",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-002",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Venda - Produtos",
        "descricao": "Venda de insumos aplicados em operacao complementar.",
        "forma_recebimento": "TED",
        "valor": "3270.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-02",
        "data_emissao": "2026-04-02",
        "data_vencimento": "2026-04-03",
        "data_recebimento": "2026-04-03",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-003",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Venda de Manutencao",
        "descricao": "Cobranca de manutencao preventiva do pulverizador.",
        "forma_recebimento": "Boleto",
        "valor": "1890.00",
        "status": FinanceiroAgroEntrada.STATUS_PENDENTE,
        "data_lancamento": "2026-04-03",
        "data_emissao": "2026-04-03",
        "data_vencimento": "2026-04-06",
        "data_recebimento": None,
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-004",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Desconto de Duplicata (+)",
        "descricao": "Antecipacao de duplicata para reforco de caixa da operacao.",
        "forma_recebimento": "Transferencia",
        "valor": "4200.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-04",
        "data_emissao": "2026-04-04",
        "data_vencimento": "2026-04-04",
        "data_recebimento": "2026-04-04",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-005",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Socios - Aporte",
        "descricao": "Aporte dos socios para compra de materiais operacionais.",
        "forma_recebimento": "Deposito",
        "valor": "6500.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-05",
        "data_emissao": "2026-04-05",
        "data_vencimento": "2026-04-05",
        "data_recebimento": "2026-04-05",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-006",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Estorno de Tarifa",
        "descricao": "Estorno bancario de tarifa cobrada indevidamente.",
        "forma_recebimento": "Credito em conta",
        "valor": "145.90",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-06",
        "data_emissao": "2026-04-06",
        "data_vencimento": "2026-04-06",
        "data_recebimento": "2026-04-06",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-007",
        "categoria": "Emprestimos e Financiamentos",
        "subcategoria": "Emprestimo (Capital de Giro) (+)",
        "descricao": "Credito de capital de giro para equalizar o caixa do inicio do mes.",
        "forma_recebimento": "Transferencia",
        "valor": "12000.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-07",
        "data_emissao": "2026-04-07",
        "data_vencimento": "2026-04-07",
        "data_recebimento": "2026-04-07",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-008",
        "categoria": "Emprestimos e Financiamentos",
        "subcategoria": "Fomento (+)",
        "descricao": "Receita de fomento vinculada a operacao de mapeamento.",
        "forma_recebimento": "PIX",
        "valor": "2800.00",
        "status": FinanceiroAgroEntrada.STATUS_PENDENTE,
        "data_lancamento": "2026-04-08",
        "data_emissao": "2026-04-08",
        "data_vencimento": "2026-04-10",
        "data_recebimento": None,
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-009",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Consorcio - Fundo Reserva",
        "descricao": "Receita de fundo reserva apropriada no caixa do Agro.",
        "forma_recebimento": "Transferencia",
        "valor": "980.00",
        "status": FinanceiroAgroEntrada.STATUS_RECEBIDO,
        "data_lancamento": "2026-04-09",
        "data_emissao": "2026-04-09",
        "data_vencimento": "2026-04-09",
        "data_recebimento": "2026-04-09",
    },
    {
        "documento_referencia": f"{SEED_TAG}-ENT-010",
        "categoria": "Entradas - Caixa",
        "subcategoria": "Vendas de Bens do Imobilizado",
        "descricao": "Venda de item antigo de apoio operacional.",
        "forma_recebimento": "TED",
        "valor": "3750.00",
        "status": FinanceiroAgroEntrada.STATUS_PENDENTE,
        "data_lancamento": "2026-04-10",
        "data_emissao": "2026-04-10",
        "data_vencimento": "2026-04-12",
        "data_recebimento": None,
    },
]


SAIDAS = [
    {
        "documento_referencia": f"{SEED_TAG}-SAI-001",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Despesas Administrativas",
        "subcategoria": "Energia Eletrica",
        "descricao": "Pagamento da energia eletrica do galpao operacional.",
        "favorecido": "Energisa Regional",
        "forma_pagamento": "PIX",
        "valor": "420.55",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-01",
        "data_emissao": "2026-04-01",
        "data_vencimento": "2026-04-02",
        "data_pagamento": "2026-04-02",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-002",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Despesas Administrativas",
        "subcategoria": "Agua",
        "descricao": "Conta de agua do escritorio de apoio do Agro.",
        "favorecido": "SAAE Municipal",
        "forma_pagamento": "Debito",
        "valor": "118.34",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-02",
        "data_emissao": "2026-04-02",
        "data_vencimento": "2026-04-03",
        "data_pagamento": "2026-04-03",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-003",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Despesas Administrativas",
        "subcategoria": "Internet",
        "descricao": "Internet dedicada para planejamento de voos e envio de mapas.",
        "favorecido": "Fibra Agro Net",
        "forma_pagamento": "Boleto",
        "valor": "249.90",
        "status": FinanceiroAgroSaida.STATUS_PENDENTE,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-03",
        "data_emissao": "2026-04-03",
        "data_vencimento": "2026-04-06",
        "data_pagamento": None,
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-004",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Folha de Pagamento",
        "subcategoria": "Salarios",
        "descricao": "Pagamento de salarios da equipe operacional do Agro.",
        "favorecido": "Equipe Operacional Agro",
        "forma_pagamento": "Transferencia",
        "valor": "6850.00",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-04",
        "data_emissao": "2026-04-04",
        "data_vencimento": "2026-04-05",
        "data_pagamento": "2026-04-05",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-005",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Servicos de Terceiros",
        "subcategoria": "Consultoria",
        "descricao": "Consultoria tecnica para parametrizacao de mapas e rotas.",
        "favorecido": "GeoCampo Consultoria",
        "forma_pagamento": "TED",
        "valor": "1750.00",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-05",
        "data_emissao": "2026-04-05",
        "data_vencimento": "2026-04-06",
        "data_pagamento": "2026-04-06",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-006",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Locacao e Equipamentos",
        "subcategoria": "Manutencao de Equipamentos",
        "descricao": "Troca de pecas e calibracao dos equipamentos de aplicacao.",
        "favorecido": "Oficina DroneMax",
        "forma_pagamento": "PIX",
        "valor": "980.00",
        "status": FinanceiroAgroSaida.STATUS_PENDENTE,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-06",
        "data_emissao": "2026-04-06",
        "data_vencimento": "2026-04-08",
        "data_pagamento": None,
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-007",
        "tipo_saida": FinanceiroAgroSaida.TIPO_IMPOSTO,
        "categoria": "Impostos / Retencao",
        "subcategoria": "ISS",
        "descricao": "Recolhimento de ISS.",
        "favorecido": "Prefeitura Municipal",
        "forma_pagamento": "DAR",
        "valor": "365.40",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": "ISS sobre nota fiscal de servico de pulverizacao do periodo.",
        "data_lancamento": "2026-04-07",
        "data_emissao": "2026-04-07",
        "data_vencimento": "2026-04-08",
        "data_pagamento": "2026-04-08",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-008",
        "tipo_saida": FinanceiroAgroSaida.TIPO_IMPOSTO,
        "categoria": "Impostos / Retencao",
        "subcategoria": "ICMS",
        "descricao": "Recolhimento de ICMS.",
        "favorecido": "SEFAZ Estadual",
        "forma_pagamento": "DAR",
        "valor": "512.70",
        "status": FinanceiroAgroSaida.STATUS_PENDENTE,
        "detalhamento_imposto": "ICMS referente a venda de produtos lancada no financeiro do Agro.",
        "data_lancamento": "2026-04-08",
        "data_emissao": "2026-04-08",
        "data_vencimento": "2026-04-11",
        "data_pagamento": None,
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-009",
        "tipo_saida": FinanceiroAgroSaida.TIPO_RETENCAO,
        "categoria": "Impostos / Retencao",
        "subcategoria": "Retencao Contrato",
        "descricao": "Retencao financeira vinculada ao contrato do Agro.",
        "favorecido": "Tomador do Servico",
        "forma_pagamento": "Compensacao",
        "valor": "430.00",
        "status": FinanceiroAgroSaida.STATUS_PAGO,
        "detalhamento_imposto": "Retencao contratual aplicada sobre medicao do servico executado.",
        "data_lancamento": "2026-04-09",
        "data_emissao": "2026-04-09",
        "data_vencimento": "2026-04-09",
        "data_pagamento": "2026-04-09",
    },
    {
        "documento_referencia": f"{SEED_TAG}-SAI-010",
        "tipo_saida": FinanceiroAgroSaida.TIPO_DESPESA,
        "categoria": "Comissoes",
        "subcategoria": "Comissao de Vendas",
        "descricao": "Comissao comercial sobre fechamento de nova frente de servico.",
        "favorecido": "Representante Comercial Agro",
        "forma_pagamento": "Transferencia",
        "valor": "890.00",
        "status": FinanceiroAgroSaida.STATUS_PENDENTE,
        "detalhamento_imposto": None,
        "data_lancamento": "2026-04-10",
        "data_emissao": "2026-04-10",
        "data_vencimento": "2026-04-12",
        "data_pagamento": None,
    },
]


def _get_clientes():
    clientes = ClienteAgro.query.order_by(ClienteAgro.id.asc()).all()
    if not clientes:
        raise RuntimeError("Nenhum cliente Agro encontrado para vincular os lancamentos de teste.")
    return clientes


def _seed_entradas(clientes):
    FinanceiroAgroEntrada.query.filter(FinanceiroAgroEntrada.documento_referencia.like(f"{SEED_TAG}-ENT-%")).delete(
        synchronize_session=False
    )

    criadas = []
    for index, item in enumerate(ENTRADAS):
        cliente = clientes[index % len(clientes)]
        data_vencimento = _date(item["data_vencimento"])
        data_recebimento = _date(item["data_recebimento"]) if item["data_recebimento"] else None
        competencia = data_recebimento or data_vencimento
        entrada = FinanceiroAgroEntrada(
            prefeitura_id=getattr(cliente, "prefeitura_id", None),
            cliente_agro_id=cliente.id,
            categoria=item["categoria"],
            subcategoria=item["subcategoria"],
            descricao=item["descricao"],
            documento_referencia=item["documento_referencia"],
            cliente_nome=cliente.nome,
            forma_recebimento=item["forma_recebimento"],
            status=item["status"],
            observacoes="Carga automatica de teste para validar Fluxo de Caixa e DRE do Agro.",
            competencia_mes=competencia.month,
            competencia_ano=competencia.year,
            data_lancamento=_date(item["data_lancamento"]),
            data_emissao=_date(item["data_emissao"]),
            data_vencimento=data_vencimento,
            data_recebimento=data_recebimento,
            valor=_decimal(item["valor"]),
        )
        db.session.add(entrada)
        criadas.append(entrada)
    return criadas


def _seed_saidas(clientes):
    FinanceiroAgroSaida.query.filter(FinanceiroAgroSaida.documento_referencia.like(f"{SEED_TAG}-SAI-%")).delete(
        synchronize_session=False
    )

    criadas = []
    for index, item in enumerate(SAIDAS):
        cliente = clientes[index % len(clientes)]
        data_vencimento = _date(item["data_vencimento"])
        data_pagamento = _date(item["data_pagamento"]) if item["data_pagamento"] else None
        competencia = data_pagamento or data_vencimento
        saida = FinanceiroAgroSaida(
            prefeitura_id=getattr(cliente, "prefeitura_id", None),
            cliente_agro_id=cliente.id,
            tipo_saida=item["tipo_saida"],
            categoria=item["categoria"],
            subcategoria=item["subcategoria"],
            descricao=item["descricao"],
            documento_referencia=item["documento_referencia"],
            detalhamento_imposto=item["detalhamento_imposto"],
            favorecido=item["favorecido"],
            forma_pagamento=item["forma_pagamento"],
            status=item["status"],
            observacoes="Carga automatica de teste para validar Fluxo de Caixa e DRE do Agro.",
            competencia_mes=competencia.month,
            competencia_ano=competencia.year,
            data_lancamento=_date(item["data_lancamento"]),
            data_emissao=_date(item["data_emissao"]),
            data_vencimento=data_vencimento,
            data_pagamento=data_pagamento,
            valor=_decimal(item["valor"]),
        )
        db.session.add(saida)
        criadas.append(saida)
    return criadas


def main():
    app = create_app()
    with app.app_context():
        clientes = _get_clientes()
        entradas = _seed_entradas(clientes)
        saidas = _seed_saidas(clientes)
        db.session.commit()

        total_entradas = sum(item.valor for item in entradas)
        total_saidas = sum(item.valor for item in saidas)
        print(f"{len(entradas)} entradas manuais criadas.")
        print(f"{len(saidas)} saidas manuais criadas.")
        print(f"Total de entradas: R$ {total_entradas:.2f}")
        print(f"Total de saidas: R$ {total_saidas:.2f}")
        print("Documentos seed:")
        for item in entradas:
            print(f"  - {item.documento_referencia} | {item.categoria} > {item.subcategoria} | {item.cliente_nome}")
        for item in saidas:
            print(f"  - {item.documento_referencia} | {item.categoria} > {item.subcategoria} | {item.favorecido}")


if __name__ == "__main__":
    main()
