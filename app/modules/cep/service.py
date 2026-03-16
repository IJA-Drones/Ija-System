import re

from app.clients.cep_client import CepLookupError, CepNotFoundError, lookup_cep


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
