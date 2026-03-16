import requests


class CepNotFoundError(Exception):
    pass


class CepLookupError(Exception):
    pass


def _request_json(url: str, timeout: int = 3):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, timeout=timeout, headers=headers, verify=False)
    response.raise_for_status()
    return response.json()


def lookup_cep(cep_digits: str, logger=None):
    try:
        data = _request_json(f"https://viacep.com.br/ws/{cep_digits}/json/")
        if data.get("erro"):
            raise CepNotFoundError("CEP nao encontrado.")

        return {
            "cep": data.get("cep", ""),
            "logradouro": data.get("logradouro", ""),
            "complemento": data.get("complemento", ""),
            "bairro": data.get("bairro", ""),
            "cidade": data.get("localidade", ""),
            "uf": data.get("uf", ""),
        }
    except CepNotFoundError:
        raise
    except Exception as exc:
        if logger:
            logger.exception("Falha ViaCEP: %s", exc)

    try:
        data = _request_json(f"https://brasilapi.com.br/api/cep/v1/{cep_digits}")
        return {
            "cep": data.get("cep", ""),
            "logradouro": data.get("street", ""),
            "complemento": "",
            "bairro": data.get("neighborhood", ""),
            "cidade": data.get("city", ""),
            "uf": data.get("state", ""),
        }
    except Exception as exc:
        if logger:
            logger.exception("Falha BrasilAPI: %s", exc)
        raise CepLookupError("Falha ao consultar o servico de CEP.") from exc
