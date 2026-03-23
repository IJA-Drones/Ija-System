import re

from app.clients.cep_client import (
    CepLookupError,
    CepNotFoundError,
    lookup_cep,
    lookup_cep_by_address,
)


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def build_cep_response(cep: str, logger=None, debug: bool = False):
    cep_digits = only_digits(cep)

    if len(cep_digits) != 8:
        return {"ok": False, "error": "CEP invalido. Use 8 digitos."}, 400

    try:
        payload = lookup_cep(cep_digits, logger=logger)
        return {
            "ok": True,
            "cep": payload.get("cep", ""),
            "logradouro": payload.get("logradouro", ""),
            "complemento": payload.get("complemento", ""),
            "bairro": payload.get("bairro", ""),
            "cidade": payload.get("cidade", ""),
            "uf": payload.get("uf", ""),
        }, 200
    except CepNotFoundError:
        return {"ok": False, "error": "CEP nao encontrado."}, 404
    except CepLookupError as exc:
        if debug:
            return {"ok": False, "error": f"Falha CEP (debug): {repr(exc)}"}, 502
        return {"ok": False, "error": "Falha ao consultar o servico de CEP."}, 502


def build_cep_by_address_response(payload: dict, logger=None, debug: bool = False):
    logradouro = (payload.get("logradouro") or "").strip()
    bairro = (payload.get("bairro") or "").strip()
    cidade = (payload.get("cidade") or "").strip()
    uf = (payload.get("uf") or "").strip().upper()

    if not logradouro or not bairro or not cidade or len(uf) != 2:
        return {
            "ok": False,
            "error": "Informe logradouro, bairro, cidade e UF para buscar o CEP.",
        }, 400

    try:
        resultado = lookup_cep_by_address(
            logradouro=logradouro,
            bairro=bairro,
            cidade=cidade,
            uf=uf,
            logger=logger,
        )
        return {
            "ok": True,
            "cep": resultado.get("cep", ""),
            "logradouro": resultado.get("logradouro", ""),
            "complemento": resultado.get("complemento", ""),
            "bairro": resultado.get("bairro", ""),
            "cidade": resultado.get("cidade", ""),
            "uf": resultado.get("uf", ""),
            "matches": resultado.get("matches", 1),
        }, 200
    except CepNotFoundError:
        return {"ok": False, "error": "CEP nao encontrado para o endereco informado."}, 404
    except CepLookupError as exc:
        if debug:
            return {"ok": False, "error": f"Falha CEP endereco (debug): {repr(exc)}"}, 502
        return {"ok": False, "error": "Falha ao consultar o servico de CEP pelo endereco."}, 502
