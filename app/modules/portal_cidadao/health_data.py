"""Indicadores semanais do município de São Paulo publicados pelo InfoDengue.

Contrato da fonte: https://info.dengue.mat.br/services/api/doc
"""

import math
import time
from datetime import date, datetime, timezone

import requests


INFO_DENGUE_API_URL = "https://info.dengue.mat.br/api/alertcity"
INFO_DENGUE_SOURCE_URL = "https://info.dengue.mat.br/services/api"
HEALTH_REPORT_URL = (
    "https://prefeitura.sp.gov.br/web/saude/w/"
    "vigilancia_em_saude/boletim_covisa/arboviroses"
)
CACHE_TTL_SECONDS = 30 * 60
RETRY_TTL_SECONDS = 5 * 60
ALERT_LEVELS = {
    1: ("Baixo", "low"),
    2: ("Atenção", "attention"),
    3: ("Alerta", "alert"),
    4: ("Alto", "high"),
}

_cache = {"expires_at": 0.0, "summary": None, "stale": False}


def get_portal_dengue_summary(logger=None):
    now = time.monotonic()
    if now >= _cache["expires_at"]:
        try:
            summary = _fetch_latest_summary()
        except (requests.RequestException, ValueError, TypeError, OverflowError, OSError) as exc:
            if logger:
                logger.warning("Falha ao consultar indicadores do InfoDengue: %s", exc)
            _cache["stale"] = True
            _cache["expires_at"] = now + RETRY_TTL_SECONDS
        else:
            _cache["summary"] = summary
            _cache["stale"] = False
            _cache["expires_at"] = now + CACHE_TTL_SECONDS

    return {
        "available": _cache["summary"] is not None,
        "stale": _cache["stale"] and _cache["summary"] is not None,
        "source_url": INFO_DENGUE_SOURCE_URL,
        "report_url": HEALTH_REPORT_URL,
        **(_cache["summary"] or {}),
    }


def clear_dengue_summary_cache():
    _cache.update(expires_at=0.0, summary=None, stale=False)


def _fetch_latest_summary():
    year = date.today().year
    response = requests.get(
        INFO_DENGUE_API_URL,
        params={
            "geocode": 3550308,
            "disease": "dengue",
            "format": "json",
            "ew_start": 1,
            "ew_end": 53,
            "ey_start": year - 1,
            "ey_end": year,
        },
        timeout=6,
        headers={"User-Agent": "IJA-Portal-Cidadao/1.0"},
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("InfoDengue sem registros semanais disponíveis.")

    # A API não garante a ordem dos registros. Não confundir zero com ausência.
    row = max(rows, key=lambda item: int(item["SE"]) if isinstance(item, dict) and item.get("SE") else 0)
    if not isinstance(row, dict) or not row.get("SE"):
        raise ValueError("Semana epidemiológica ausente.")
    epidemiological_year, week = divmod(int(row["SE"]), 100)
    if not 1 <= week <= 53 or not year - 1 <= epidemiological_year <= year:
        raise ValueError("Semana epidemiológica inválida.")

    start = row.get("data_iniSE")
    if isinstance(start, (int, float)):
        week_start = datetime.fromtimestamp(start / 1000, tz=timezone.utc).date()
    else:
        week_start = date.fromisoformat(str(start)[:10])
    level_label, level_class = ALERT_LEVELS.get(row.get("nivel"), ("Não informado", "unknown"))
    probability = _number(row.get("p_rt1"))
    probability_label = (
        _format_number(probability * 100, 1) + "%"
        if probability is not None and 0 <= probability <= 1 else "—"
    )
    return {
        "week_label": f"SE {week:02d}/{epidemiological_year}",
        "week_start_label": week_start.strftime("%d/%m/%Y"),
        "week_start_iso": week_start.isoformat(),
        "level_label": level_label,
        "level_class": level_class,
        "reported_cases": _format_number(row.get("casos")),
        "estimated_cases": _format_number(row.get("casos_est"), 1),
        "incidence": _format_number(row.get("p_inc100k"), 2),
        "probability": probability_label,
    }


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _format_number(value, decimals=0):
    number = _number(value)
    if number is None:
        return "—"
    return f"{number:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))
