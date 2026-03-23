import requests
import unicodedata
from urllib.parse import quote


class CepNotFoundError(Exception):
    pass


class CepLookupError(Exception):
    pass


def _request_json(url: str, timeout: int = 3):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, timeout=timeout, headers=headers, verify=False)
    response.raise_for_status()
    return response.json()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.upper().split())


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


def lookup_cep_by_address(*, logradouro: str, bairro: str, cidade: str, uf: str, logger=None):
    uf_value = (uf or "").strip().upper()
    cidade_value = (cidade or "").strip()
    logradouro_value = (logradouro or "").strip()
    bairro_value = (bairro or "").strip()

    try:
        data = _request_json(
            "https://viacep.com.br/ws/"
            f"{quote(uf_value)}/{quote(cidade_value)}/{quote(logradouro_value)}/json/"
        )

        if not isinstance(data, list) or not data:
            raise CepNotFoundError("CEP nao encontrado para o endereco informado.")

        candidatos = data
        bairro_normalizado = _normalize_text(bairro_value)
        if bairro_normalizado:
            candidatos_bairro = [
                item for item in data
                if _normalize_text(item.get("bairro", "")) == bairro_normalizado
            ]
            if candidatos_bairro:
                candidatos = candidatos_bairro

        escolhido = candidatos[0]
        return {
            "cep": escolhido.get("cep", ""),
            "logradouro": escolhido.get("logradouro", ""),
            "complemento": escolhido.get("complemento", ""),
            "bairro": escolhido.get("bairro", ""),
            "cidade": escolhido.get("localidade", ""),
            "uf": escolhido.get("uf", ""),
            "matches": len(candidatos),
        }
    except CepNotFoundError:
        raise
    except Exception as exc:
        if logger:
            logger.exception("Falha ViaCEP busca por endereco: %s", exc)
        raise CepLookupError("Falha ao consultar o servico de CEP pelo endereco.") from exc
