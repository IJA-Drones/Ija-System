"""Read-only RedGPS client. Never include response bodies or credentials in errors."""
import time
from urllib.parse import urlsplit

import certifi
import requests


class RedGPSError(Exception):
    pass


class RedGPSClient:
    def __init__(self, config):
        self.base_url = config.get("REDGPS_BASE_URL", "").rstrip("/")
        self.key = config.get("REDGPS_API_KEY", "")
        self.username = config.get("REDGPS_USERNAME", "")
        self.password = config.get("REDGPS_PASSWORD", "")
        self.token = None
        self.expires_at = 0

    def _post(self, endpoint, fields):
        if urlsplit(self.base_url).scheme != "https" or not all((self.key, self.username, self.password)):
            raise RedGPSError("configuracao_incompleta")
        try:
            response = requests.post(
                f"{self.base_url}/{endpoint}", data={"apikey": self.key, **fields},
                timeout=(5, 15), verify=certifi.where(), allow_redirects=False,
            )
            if response.status_code != 200:
                raise RedGPSError(f"http_{response.status_code}")
            result = response.json()
        except (requests.RequestException, ValueError):
            raise RedGPSError("falha_conexao_ou_resposta") from None
        if not isinstance(result, dict):
            raise RedGPSError("resposta_invalida")
        return result

    def _authenticate(self):
        result = self._post("gettoken", {"token": "", "username": self.username, "password": self.password})
        token = result.get("data")
        if str(result.get("status")) != "200" or not isinstance(token, str) or not token:
            raise RedGPSError("autenticacao_recusada")
        self.token = token
        self.expires_at = time.monotonic() + 5 * 3600 + 50 * 60

    def read(self, endpoint):
        # Prevent accidental writes through the generic helper.
        if endpoint not in {"getdata", "vehicleGetAll"}:
            raise ValueError("Endpoint de leitura não permitido")
        for attempt in range(2):
            if not self.token or time.monotonic() >= self.expires_at:
                self._authenticate()
            fields = {"token": self.token}
            if endpoint == "getdata":
                fields.update(UseUTCDate="1", sensores="1")
            try:
                result = self._post(endpoint, fields)
            except RedGPSError as error:
                if str(error) == "http_401" and attempt == 0:
                    self.token = None
                    continue
                raise
            status = str(result.get("status"))
            if status == "30400" and attempt == 0:
                self.token = None
                continue
            if status == "40100":
                return []
            if status != "200":
                raise RedGPSError("consulta_recusada")
            rows = result.get("data")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise RedGPSError("resposta_invalida")
            return rows
        raise RedGPSError("token_recusado")
