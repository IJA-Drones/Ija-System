"""Request bodies for the unified maintenance worksheet in disposable tests."""
from werkzeug.datastructures import MultiDict


def worksheet_data(order, parts=(), *, complete=False, **changes):
    data = MultiDict(dict(manutencao_id=str(order.id), versao=str(order.versao), acao="concluir" if complete else "rascunho",
        recebido_em="2026-11-26T10:30", condicao_chegada="com_avaria", avarias_identificadas="Falha relatada pela operação",
        diagnostico_tecnico="Falha confirmada durante análise técnica", tipo_manutencao="corretiva",
        responsavel_manutencao="Técnica de teste", servicos_realizados="Substituição e ajuste do conjunto",
        drone_testado="1", observacoes_teste="Teste funcional aprovado", condicao_final="apto"))
    for item in parts:
        part, quantity, *notes = item
        data.add("reparo_id", str(part.id))
        data.add("reparo_quantidade", str(quantity))
        data.add("reparo_observacoes", notes[0] if notes else "Substituição de teste")
    for key, value in changes.items():
        data[key] = value
    return data
