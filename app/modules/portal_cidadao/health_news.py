import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from re import sub
from urllib.parse import urlparse

import requests


HEALTH_NEWS_CACHE_TTL_SECONDS = 30 * 60
HEALTH_NEWS_LIMIT = 6
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


def clear_health_news_cache():
    _cache["items"] = None
    _cache["expires_at"] = 0.0


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


def _normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def _is_official_url(url):
    hostname = (urlparse(url).hostname or "").lower()
    return hostname.endswith(".gov.br") or hostname in {"www.saude.sp.gov.br", "saude.sp.gov.br"}
