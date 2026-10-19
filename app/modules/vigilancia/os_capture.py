"""Reaproveita uma OS autorizada; nunca deduz inspeção ou positividade."""

from flask import abort
from flask_login import current_user

from app.shared.retorno_ciclo import get_accessible_solicitacao_for_retorno_ciclo
from .field_capture import FieldInputError
from .routes import _positive_id


def selected_os(values, prefeitura):
    supplied = values.getlist("os_id")
    if not supplied or supplied == [""]:
        return None
    if len(supplied) != 1 or _positive_id(supplied[0]) is None:
        raise FieldInputError("Informe um único número válido de OS.")
    if prefeitura is None:
        raise FieldInputError("Selecione a prefeitura da OS.")
    record = get_accessible_solicitacao_for_retorno_ciclo(current_user, int(supplied[0]))
    if record is None or record.prefeitura_id != prefeitura:
        abort(404, description="OS indisponível para esta conta e prefeitura.")
    return record


def context(record):
    order = record.ordem_servico
    uvis_order = record.ordem_servico_equipe_uvis
    responsible = (getattr(order, "nome_rf_ace_responsavel_os", None)
                   or getattr(uvis_order, "respondido_por", None)
                   or getattr(order, "respondido_por", None) or "")
    return {
        "id": record.id, "protocolo": record.protocolo,
        "endereco": ", ".join(str(value) for value in (record.logradouro, record.numero, record.complemento, record.bairro, record.cidade, record.uf) if value),
        "equipe": getattr(record.equipe, "nome_equipe", None) or record.equipe_uvis_nome or "Não informada",
        "responsavel": responsible,
        "data_aplicacao": getattr(order, "data_aplicacao", None),
        "larva_visualizada": getattr(order, "larva_visualizada", None) or getattr(uvis_order, "larva_visualizada", None),
        "criadouro": getattr(order, "criadouro_os_tipo_volume", None) or record.foco,
    }


def prefill(record):
    return {"bairro": record.bairro or "", "latitude": record.latitude or "",
            "longitude": record.longitude or "", "responsavel_inspecao": context(record)["responsavel"]}


def declaration(values, record):
    responsible = values.getlist("responsavel_inspecao")
    name = responsible[0].strip() if len(responsible) == 1 else ""
    if not name or len(name) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise FieldInputError("Informe o responsável pela inspeção, com até 200 caracteres.")
    sample = values.getlist("amostra_liraa")
    if values.get("origem") == "LIRAA" and sample != ["sim"]:
        raise FieldInputError("Confirme que o imóvel pertence à amostra do levantamento LIRAa informado.")
    return {"id": record.id, "responsavel": name,
            "amostra_declarada": values.get("origem") == "LIRAA"}
