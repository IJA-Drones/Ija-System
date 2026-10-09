import requests
import unicodedata
from flask import current_app
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
    correios_payload = _lookup_cep_correios(cep_digits, logger=logger)
    if correios_payload:
        return correios_payload

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


def _lookup_cep_correios(cep_digits: str, logger=None):
    token = _setting("CORREIOS_CEP_TOKEN") or _setting("CORREIOS_API_TOKEN")
    if not token:
        return None

    base_url = (_setting("CORREIOS_CEP_BASE_URL") or "https://api.correios.com.br/cep").rstrip("/")
    urls = [
        f"{base_url}/v2/enderecos/{cep_digits}",
        f"{base_url}/v2/endereços/{cep_digits}",
    ]
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    last_exc = None
    for url in urls:
        try:
            response = requests.get(url, timeout=5, headers=headers)
            if response.status_code == 404:
                raise CepNotFoundError("CEP nao encontrado.")
            if response.status_code in (401, 403):
                if logger:
                    logger.warning("Credencial da API Busca CEP dos Correios recusada (%s).", response.status_code)
                return None
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                data = data[0] if data else {}
            if not data:
                return None
            return _normalize_correios_address(data)
        except CepNotFoundError:
            raise
        except Exception as exc:
            last_exc = exc
            continue

    if logger and last_exc:
        logger.exception("Falha Correios Busca CEP: %s", last_exc)
    return None


def _normalize_correios_address(data):
    cep = str(data.get("cep") or "").strip()
    cep_digits = "".join(ch for ch in cep if ch.isdigit())
    formatted_cep = f"{cep_digits[:5]}-{cep_digits[5:]}" if len(cep_digits) == 8 else cep
    return {
        "cep": formatted_cep,
        "logradouro": data.get("logradouro") or data.get("endereco") or "",
        "complemento": data.get("complemento") or "",
        "bairro": data.get("bairro") or "",
        "cidade": data.get("localidade") or data.get("municipio") or "",
        "uf": data.get("uf") or "",
    }


def _setting(name):
    try:
        return current_app.config.get(name)
    except RuntimeError:
        return None
