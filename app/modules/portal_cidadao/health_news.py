import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from re import sub
from urllib.parse import urlparse

import requests


HEALTH_NEWS_CACHE_TTL_SECONDS = 30 * 60
HEALTH_NEWS_LIMIT = 6
INFODENGUE_API_URL = "https://info.dengue.mat.br/api/alertcity"
INFODENGUE_DEFAULT_GEOCODE = "3550308"
INFODENGUE_DEFAULT_CITY = "São Paulo"
INFODENGUE_DEFAULT_DISEASE = "dengue"
INFODENGUE_LOOKBACK_WEEKS = 8
INFODENGUE_DISEASE_LABELS = {
    "dengue": "Dengue",
    "chikungunya": "Chikungunya",
    "zika": "Zika",
}
HEALTH_NEWS_KEYWORDS = (
    "dengue",
    "arbovirose",
    "arboviroses",
    "aedes",
    "zika",
    "chikungunya",
    "febre amarela",
    "oropouche",
    "vigilancia",
    "vigilância",
    "saude",
    "saúde",
)
OFFICIAL_FEEDS = (
    {
        "name": "Secretaria de Estado da Saúde de SP",
        "url": "https://www.saude.sp.gov.br/ses/noticias.rss",
    },
)
OFFICIAL_FALLBACK_LINKS = (
    {
        "title": "Boletim epidemiológico de arboviroses",
        "summary": "Atualização da COVISA/SMS-SP com dados de dengue, zika e chikungunya no Município de São Paulo.",
        "url": "https://prefeitura.sp.gov.br/web/saude/w/vigilancia_em_saude/boletim_covisa/arboviroses",
        "source": "COVISA/SMS-SP",
        "published_label": "Fonte oficial",
    },
    {
        "title": "Dengue: sintomas, prevenção e orientações",
        "summary": "Página do Ministério da Saúde com informações de referência sobre dengue e cuidados recomendados.",
        "url": "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/d/dengue",
        "source": "Ministério da Saúde",
        "published_label": "Fonte oficial",
    },
    {
        "title": "Plano Municipal de Enfrentamento da Dengue",
        "summary": "Diretrizes municipais para prevenção, promoção da saúde e controle das arboviroses na cidade.",
        "url": "https://prefeitura.sp.gov.br/web/saude/w/vigilancia_em_saude/dengue/362103",
        "source": "SMS-SP/COVISA",
        "published_label": "Fonte oficial",
    },
)

_cache = {"expires_at": 0.0, "items": None}
_infodengue_cache = {"expires_at": 0.0, "item": None}
_infodengue_report_cache = {}


@dataclass(frozen=True)
class HealthNewsItem:
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime | None = None
    published_label: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_label": self.published_label or _format_date(self.published_at),
        }


@dataclass(frozen=True)
class InfoDengueAlert:
    city: str
    disease: str
    epidemiological_week: int | None
    week_label: str
    alert_level: int | None
    alert_label: str
    cases: int | None
    estimated_cases: float | None
    incidence: float | None
    probability_rt_above_1: float | None
    started_at_label: str
    source_url: str

    def to_dict(self):
        return {
            "city": self.city,
            "disease": self.disease.capitalize(),
            "epidemiological_week": self.epidemiological_week,
            "week_label": self.week_label,
            "alert_level": self.alert_level,
            "alert_label": self.alert_label,
            "cases": _format_number(self.cases),
            "estimated_cases": _format_number(self.estimated_cases, decimals=1),
            "incidence": _format_number(self.incidence, decimals=2),
            "probability_rt_above_1": _format_percent(self.probability_rt_above_1),
            "started_at_label": self.started_at_label,
            "source_url": self.source_url,
        }


def get_portal_health_news(limit=HEALTH_NEWS_LIMIT, logger=None):
    now = time.time()
    cached = _cache.get("items")
    if cached is not None and now < _cache.get("expires_at", 0):
        return cached[:limit]

    items = []
    for feed in OFFICIAL_FEEDS:
        try:
            items.extend(_fetch_rss_feed(feed["url"], feed["name"]))
        except Exception as exc:
            if logger:
                logger.warning("Falha ao buscar noticias oficiais para o portal: %s", exc)

    normalized = _dedupe_news(items)
    if normalized:
        result = [item.to_dict() for item in normalized[:limit]]
    else:
        result = list(OFFICIAL_FALLBACK_LINKS)[:limit]

    _cache["items"] = result
    _cache["expires_at"] = now + HEALTH_NEWS_CACHE_TTL_SECONDS
    return result


def get_infodengue_alert(config=None, logger=None):
    now = time.time()
    cached = _infodengue_cache.get("item")
    if cached is not None and now < _infodengue_cache.get("expires_at", 0):
        return cached

    config = config or {}
    geocode = str(config.get("INFODENGUE_GEOCODE") or INFODENGUE_DEFAULT_GEOCODE)
    city = str(config.get("INFODENGUE_CITY") or INFODENGUE_DEFAULT_CITY)
    disease = str(config.get("INFODENGUE_DISEASE") or INFODENGUE_DEFAULT_DISEASE).lower()
    lookback_weeks = int(config.get("INFODENGUE_LOOKBACK_WEEKS") or INFODENGUE_LOOKBACK_WEEKS)
    today = date.today()
    iso = today.isocalendar()
    ew_end = int(iso.week)
    ew_start = max(1, ew_end - max(1, lookback_weeks) + 1)
    year = int(iso.year)

    params = {
        "geocode": geocode,
        "disease": disease,
        "format": "json",
        "ew_start": ew_start,
        "ew_end": ew_end,
        "ey_start": year,
        "ey_end": year,
    }
    source_url = _build_infodengue_source_url(params)

    try:
        response = requests.get(INFODENGUE_API_URL, params=params, timeout=8, headers={"User-Agent": "IJA-Portal-Cidadao/1.0"})
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        if logger:
            logger.warning("Falha ao buscar dados do InfoDengue para o portal: %s", exc)
        _infodengue_cache["item"] = None
        _infodengue_cache["expires_at"] = now + HEALTH_NEWS_CACHE_TTL_SECONDS
        return None

    alert = _build_infodengue_alert(rows, city=city, disease=disease, source_url=source_url)
    _infodengue_cache["item"] = alert.to_dict() if alert else None
    _infodengue_cache["expires_at"] = now + HEALTH_NEWS_CACHE_TTL_SECONDS
    return _infodengue_cache["item"]


def get_infodengue_report(config=None, disease=None, year=None, logger=None):
    config = config or {}
    today = date.today()
    selected_disease = _normalize_disease(disease or config.get("INFODENGUE_DISEASE") or INFODENGUE_DEFAULT_DISEASE)
    selected_year = _normalize_year(year, fallback=today.isocalendar().year)
    cache_key = (selected_disease, selected_year)
    now = time.time()

    cached = _infodengue_report_cache.get(cache_key)
    if cached is not None and now < cached.get("expires_at", 0):
        return cached.get("item")

    geocode = str(config.get("INFODENGUE_GEOCODE") or INFODENGUE_DEFAULT_GEOCODE)
    city = str(config.get("INFODENGUE_CITY") or INFODENGUE_DEFAULT_CITY)
    current_iso = today.isocalendar()
    ew_end = int(current_iso.week) if selected_year == int(current_iso.year) else 53
    params = {
        "geocode": geocode,
        "disease": selected_disease,
        "format": "json",
        "ew_start": 1,
        "ew_end": ew_end,
        "ey_start": selected_year,
        "ey_end": selected_year,
    }
    source_url = _build_infodengue_source_url(params)

    try:
        response = requests.get(INFODENGUE_API_URL, params=params, timeout=8, headers={"User-Agent": "IJA-Portal-Cidadao/1.0"})
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        if logger:
            logger.warning("Falha ao buscar relatorio InfoDengue para o portal: %s", exc)
        report = None
    else:
        report = _build_infodengue_report(
            rows,
            city=city,
            disease=selected_disease,
            year=selected_year,
            source_url=source_url,
        )

    _infodengue_report_cache[cache_key] = {
        "item": report,
        "expires_at": now + HEALTH_NEWS_CACHE_TTL_SECONDS,
    }
    return report


def clear_health_news_cache():
    _cache["items"] = None
    _cache["expires_at"] = 0.0
    _infodengue_cache["item"] = None
    _infodengue_cache["expires_at"] = 0.0
    _infodengue_report_cache.clear()


def _build_infodengue_alert(rows, city, disease, source_url):
    if not isinstance(rows, list):
        return None
    valid_rows = [row for row in rows if isinstance(row, dict) and not _row_has_api_error(row)]
    if not valid_rows:
        return None

    latest = max(valid_rows, key=lambda row: int(_coerce_number(row.get("SE") or row.get("se") or 0) or 0))
    epidemiological_week = int(_coerce_number(latest.get("SE") or latest.get("se") or 0) or 0) or None
    cases = _coerce_number(latest.get("casos"))
    estimated_cases = _coerce_number(latest.get("casos_est"))
    incidence = _coerce_number(latest.get("p_inc100k") if "p_inc100k" in latest else latest.get("inc"))
    probability_rt_above_1 = _coerce_number(latest.get("p_rt1") if "p_rt1" in latest else latest.get("prt1"))
    alert_level = int(_coerce_number(latest.get("nivel")) or 0) if latest.get("nivel") is not None else None

    return InfoDengueAlert(
        city=city,
        disease=disease,
        epidemiological_week=epidemiological_week,
        week_label=_format_epi_week(epidemiological_week),
        alert_level=alert_level,
        alert_label=_alert_level_label(alert_level),
        cases=int(cases) if cases is not None else None,
        estimated_cases=estimated_cases,
        incidence=incidence,
        probability_rt_above_1=probability_rt_above_1,
        started_at_label=_format_api_date(latest.get("data_iniSE") if "data_iniSE" in latest else latest.get("data")),
        source_url=source_url,
    )


def _build_infodengue_report(rows, city, disease, year, source_url):
    if not isinstance(rows, list):
        return None

    normalized_rows = [
        row
        for row in (_normalize_infodengue_row(row) for row in rows if isinstance(row, dict) and not _row_has_api_error(row))
        if row is not None
    ]
    if not normalized_rows:
        return None

    normalized_rows.sort(key=lambda row: row["epidemiological_week"])
    max_cases_reference = max(
        (row["estimated_cases_number"] or row["cases_number"] or 0 for row in normalized_rows),
        default=0,
    )
    for row in normalized_rows:
        reference = row["estimated_cases_number"] or row["cases_number"] or 0
        row["bar_percent"] = min(100, max(4, round((reference / max_cases_reference) * 100))) if max_cases_reference else 4

    latest = normalized_rows[-1]
    peak = max(normalized_rows, key=lambda row: row["estimated_cases_number"] or row["cases_number"] or 0)
    total_cases = sum(row["cases_number"] or 0 for row in normalized_rows)
    total_estimated_cases = sum(row["estimated_cases_number"] or row["cases_number"] or 0 for row in normalized_rows)

    return {
        "city": city,
        "disease": disease,
        "disease_label": INFODENGUE_DISEASE_LABELS.get(disease, disease.capitalize()),
        "year": year,
        "source_url": source_url,
        "updated_label": latest["started_at_label"],
        "summary": {
            "latest_week_label": latest["week_label"],
            "latest_alert_level": latest["alert_level"],
            "latest_alert_label": latest["alert_label"],
            "total_cases": _format_number(total_cases),
            "total_estimated_cases": _format_number(total_estimated_cases, decimals=1),
            "latest_incidence": latest["incidence"],
            "latest_probability_rt_above_1": latest["probability_rt_above_1"],
            "peak_week_label": peak["week_label"],
            "peak_estimated_cases": peak["estimated_cases"],
        },
        "series": normalized_rows,
    }


def _normalize_infodengue_row(row):
    epidemiological_week = int(_coerce_number(row.get("SE") or row.get("se") or 0) or 0)
    if not epidemiological_week:
        return None

    cases = _coerce_number(row.get("casos"))
    estimated_cases = _coerce_number(row.get("casos_est"))
    incidence = _coerce_number(row.get("p_inc100k") if "p_inc100k" in row else row.get("inc"))
    probability_rt_above_1 = _coerce_number(row.get("p_rt1") if "p_rt1" in row else row.get("prt1"))
    alert_level = int(_coerce_number(row.get("nivel")) or 0) if row.get("nivel") is not None else None

    return {
        "epidemiological_week": epidemiological_week,
        "week_label": _format_epi_week(epidemiological_week),
        "week_short_label": _format_epi_week_short(epidemiological_week),
        "started_at_label": _format_api_date(row.get("data_iniSE") if "data_iniSE" in row else row.get("data")),
        "cases": _format_number(cases),
        "cases_number": int(cases) if cases is not None else None,
        "estimated_cases": _format_number(estimated_cases, decimals=1),
        "estimated_cases_number": estimated_cases,
        "incidence": _format_number(incidence, decimals=2),
        "incidence_number": incidence,
        "probability_rt_above_1": _format_percent(probability_rt_above_1),
        "probability_rt_above_1_number": probability_rt_above_1,
        "alert_level": alert_level,
        "alert_label": _alert_level_label(alert_level),
    }


def _fetch_rss_feed(url, source):
    response = requests.get(url, timeout=6, headers={"User-Agent": "IJA-Portal-Cidadao/1.0"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items = []

    for node in root.findall(".//item"):
        title = _node_text(node, "title")
        link = _node_text(node, "link")
        summary = _clean_html(_node_text(node, "description"))
        published_at = _parse_rss_date(_node_text(node, "pubDate"))
        if not title or not link or not _is_official_url(link):
            continue
        if not _matches_health_topic(title, summary):
            continue
        items.append(
            HealthNewsItem(
                title=title,
                summary=summary,
                url=link,
                source=source,
                published_at=published_at,
            )
        )

    return sorted(items, key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def _row_has_api_error(row):
    return any(str(key).startswith("[EE]") for key in row.keys())


def _dedupe_news(items):
    seen = set()
    unique = []
    for item in items:
        key = _normalize_url(item.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return sorted(unique, key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def _node_text(node, tag):
    found = node.find(tag)
    return (found.text or "").strip() if found is not None else ""


def _clean_html(value):
    text = unescape(value or "")
    text = sub(r"<[^>]+>", " ", text)
    text = sub(r"\s+", " ", text).strip()
    return text[:220]


def _matches_health_topic(title, summary):
    haystack = f"{title} {summary}".casefold()
    return any(keyword.casefold() in haystack for keyword in HEALTH_NEWS_KEYWORDS)


def _parse_rss_date(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_date(value):
    if not value:
        return "Fonte oficial"
    return value.astimezone(timezone.utc).strftime("%d/%m/%Y")


def _format_api_date(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%d/%m/%Y")
        except (OSError, ValueError):
            return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text[:10]


def _format_epi_week(value):
    if not value:
        return "Semana epidemiológica"
    text = str(value)
    if len(text) == 6:
        return f"SE {text[-2:]}/{text[:4]}"
    return f"SE {text}"


def _format_epi_week_short(value):
    if not value:
        return "SE"
    text = str(value)
    if len(text) == 6:
        return f"SE {int(text[-2:])}"
    return f"SE {text}"


def _alert_level_label(level):
    labels = {
        1: "Baixo",
        2: "Atenção",
        3: "Alto",
        4: "Muito alto",
    }
    return labels.get(level, "Em acompanhamento")


def _format_number(value, decimals=0):
    if value is None:
        return "Não informado"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "Não informado"
    if decimals <= 0:
        return f"{int(round(numeric)):,}".replace(",", ".")
    return f"{numeric:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_percent(value):
    if value is None:
        return "Não informado"
    try:
        numeric = float(value) * 100
    except (TypeError, ValueError):
        return "Não informado"
    return f"{numeric:.1f}%".replace(".", ",")


def _coerce_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_disease(value):
    text = str(value or "").strip().lower()
    return text if text in INFODENGUE_DISEASE_LABELS else INFODENGUE_DEFAULT_DISEASE


def _normalize_year(value, fallback):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    current_year = int(date.today().isocalendar().year)
    if 2010 <= numeric <= current_year:
        return numeric
    return int(fallback)


def _build_infodengue_source_url(params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{INFODENGUE_API_URL}?{query}"


def _normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def _is_official_url(url):
    hostname = (urlparse(url).hostname or "").lower()
    return hostname.endswith(".gov.br") or hostname in {"www.saude.sp.gov.br", "saude.sp.gov.br"}
