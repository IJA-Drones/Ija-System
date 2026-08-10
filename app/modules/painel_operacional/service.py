import math
import os
from datetime import datetime
from time import time
from urllib.parse import urlencode

import requests
from flask import current_app

from app.extensions import db
from app.models import Baterias, Drones, Equipe, Solicitacao, Usuario, Veiculos
from app.shared.access import (
    DEV_USER_TYPE,
    DIRECTOR_USER_TYPE,
    apply_prefeitura_scope,
    apply_regiao_scope,
    apply_solicitacao_prefeitura_scope,
)


OPERATIONAL_PANEL_TYPES = {DIRECTOR_USER_TYPE, DEV_USER_TYPE}
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
WEATHER_CACHE_TTL_SECONDS = 600
WEATHER_CACHE = {}
WEATHER_CODES = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com deposição",
    51: "Garoa fraca",
    53: "Garoa moderada",
    55: "Garoa intensa",
    61: "Chuva fraca",
    63: "Chuva moderada",
    65: "Chuva forte",
    80: "Pancadas fracas",
    81: "Pancadas moderadas",
    82: "Pancadas fortes",
    95: "Trovoada",
    96: "Trovoada com granizo",
    99: "Trovoada forte com granizo",
}


def _weather_cache_key(lat: float, lng: float):
    return (round(float(lat), 4), round(float(lng), 4))


def _get_cached_weather(lat: float, lng: float, allow_stale=False):
    cached = WEATHER_CACHE.get(_weather_cache_key(lat, lng))
    if not cached:
        return None
    age_seconds = time() - cached["saved_at"]
    if not allow_stale and age_seconds > WEATHER_CACHE_TTL_SECONDS:
        return None
    weather = dict(cached["weather"])
    weather["cache_age_seconds"] = int(age_seconds)
    return weather


def _store_weather_cache(lat: float, lng: float, weather: dict):
    WEATHER_CACHE[_weather_cache_key(lat, lng)] = {
        "saved_at": time(),
        "weather": dict(weather),
    }


def _weather_unavailable(message="Clima temporariamente indisponível."):
    return {
        "time": None,
        "temperature": None,
        "apparent_temperature": None,
        "humidity": None,
        "precipitation": None,
        "rain": None,
        "weather_code": None,
        "description": message,
        "cloud_cover": None,
        "wind_speed": None,
        "wind_direction": None,
        "wind_gusts": None,
        "source_status": "unavailable",
        "cache_age_seconds": None,
        "units": {
            "temperature": "C",
            "wind_speed": "km/h",
            "precipitation": "mm",
        },
    }


def can_access_operational_panel(user) -> bool:
    return getattr(user, "tipo_usuario", None) in OPERATIONAL_PANEL_TYPES


def get_operational_panel_maps_key():
    return current_app.config.get("Maps_KEY_FRONT") or current_app.config.get("KEY_API_GOOGLE_MAPS") or os.getenv("KEY_API_GOOGLE_MAPS") or ""


def _get_google_back_key():
    return current_app.config.get("Maps_KEY_BACK") or os.getenv("GOOGLE_MAPS_KEY_BACK") or current_app.config.get("KEY_API_GOOGLE_MAPS") or os.getenv("KEY_API_GOOGLE_MAPS")


def _geocode_address(address: str):
    api_key = _get_google_back_key()
    if not api_key:
        raise RuntimeError("Chave do Google Maps não configurada para geocodificação.")

    params = {
        "address": f"{address}, Brasil",
        "key": api_key,
        "region": "br",
    }
    response = requests.get(f"{GOOGLE_GEOCODE_URL}?{urlencode(params)}", timeout=10)
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "OK" or not data.get("results"):
        return None

    result = data["results"][0]
    location = result.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        return None

    return {
        "lat": float(lat),
        "lng": float(lng),
        "place_id": result.get("place_id"),
        "formatted_address": result.get("formatted_address") or address,
        "types": result.get("types") or [],
    }


def _fetch_weather(lat: float, lng: float):
    cached = _get_cached_weather(lat, lng)
    if cached:
        cached["source_status"] = "cached"
        return cached

    params = {
        "latitude": lat,
        "longitude": lng,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ]
        ),
        "timezone": "America/Sao_Paulo",
        "forecast_days": 1,
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        current_app.logger.warning("Falha ao consultar Open-Meteo para o Painel Operacional.", exc_info=True)
        stale = _get_cached_weather(lat, lng, allow_stale=True)
        if stale:
            stale["source_status"] = "stale"
            stale["description"] = f"{stale.get('description') or 'Clima'} (última leitura disponível)"
            return stale
        return _weather_unavailable()

    data = response.json()
    current = data.get("current") or {}
    units = data.get("current_units") or {}
    code = current.get("weather_code")
    return {
        "time": current.get("time"),
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "weather_code": code,
        "description": WEATHER_CODES.get(code, "Condição não identificada"),
        "cloud_cover": current.get("cloud_cover"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
        "source_status": "live",
        "cache_age_seconds": 0,
        "units": {
            "temperature": units.get("temperature_2m", "C"),
            "wind_speed": units.get("wind_speed_10m", "km/h"),
            "precipitation": units.get("precipitation", "mm"),
        },
    }
    _store_weather_cache(lat, lng, weather)
    return weather


def _risk_level(weather: dict):
    source_status = weather.get("source_status") or "live"
    if source_status == "unavailable":
        return {
            "level": "warning",
            "label": "Atenção",
            "reasons": [
                "Clima externo indisponível no momento. Confira vento, chuva e temperatura antes de liberar o voo.",
            ],
        }

    wind_speed = float(weather.get("wind_speed") or 0)
    wind_gusts = float(weather.get("wind_gusts") or 0)
    rain = float(weather.get("rain") or 0)
    precipitation = float(weather.get("precipitation") or 0)
    temperature = float(weather.get("temperature") or 0)
    weather_code = int(weather.get("weather_code") or 0)

    reasons = []
    level = "ok"

    if wind_gusts >= 35 or wind_speed >= 28:
        level = "critical"
        reasons.append("Vento/rajada acima do limite operacional recomendado.")
    elif wind_gusts >= 25 or wind_speed >= 18:
        level = "warning"
        reasons.append("Vento pede conferência do plano de voo e autonomia.")

    if rain > 0 or precipitation > 0 or weather_code in {61, 63, 65, 80, 81, 82, 95, 96, 99}:
        level = "critical" if level == "critical" or precipitation >= 2 else "warning"
        reasons.append("Há indício de chuva ou instabilidade no ponto.")

    if temperature >= 35:
        level = "critical" if level == "critical" else "warning"
        reasons.append("Temperatura elevada pode afetar baterias e equipe.")

    if not reasons:
        reasons.append("Condições sem alerta automático para vento, chuva ou temperatura.")

    if source_status == "stale":
        level = "warning" if level == "ok" else level
        reasons.append("Clima externo temporariamente indisponível; exibindo última leitura disponível.")
    elif source_status == "cached":
        reasons.append("Clima reaproveitado de consulta recente para evitar excesso de chamadas externas.")

    labels = {
        "ok": "Favorável",
        "warning": "Atenção",
        "critical": "Crítico",
    }
    return {
        "level": level,
        "label": labels[level],
        "reasons": reasons,
    }


def _distance_km(lat1, lng1, lat2, lng2):
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _parse_coordinate(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_nearby_solicitacoes(user, lat: float, lng: float, radius_km=1.5):
    query = (
        Solicitacao.query
        .options(db.selectinload(Solicitacao.usuario), db.selectinload(Solicitacao.equipe))
        .filter(Solicitacao.latitude.isnot(None), Solicitacao.longitude.isnot(None))
    )
    query = apply_solicitacao_prefeitura_scope(query, user)
    query = query.join(Usuario)
    query = apply_regiao_scope(query, user, Usuario.regiao)
    query = query.order_by(Solicitacao.data_criacao.desc()).limit(300)

    nearby = []
    for item in query.all():
        item_lat = _parse_coordinate(item.latitude)
        item_lng = _parse_coordinate(item.longitude)
        if item_lat is None or item_lng is None:
            continue
        distance = _distance_km(lat, lng, item_lat, item_lng)
        if distance > radius_km:
            continue
        nearby.append(
            {
                "id": item.id,
                "distance_km": round(distance, 2),
                "status": item.status or "",
                "foco": item.foco or "",
                "tipo_operacao": item.tipo_operacao or "",
                "data_agendamento": item.data_agendamento.strftime("%d/%m/%Y") if item.data_agendamento else "",
                "uvis": item.usuario.nome_uvis if item.usuario else "",
                "equipe": item.equipe.nome_equipe if item.equipe else "",
                "endereco": _format_solicitacao_address(item),
            }
        )

    return sorted(nearby, key=lambda row: row["distance_km"])[:8]


def _format_solicitacao_address(item):
    parts = [
        f"{item.logradouro or ''}, {item.numero or 'S/N'}".strip(),
        item.bairro or "",
        f"{item.cidade or ''}/{item.uf or ''}".strip("/"),
    ]
    return " - ".join([part for part in parts if part])


def _build_assets_summary(user):
    drones_query = apply_prefeitura_scope(Drones.query, user, Drones.prefeitura_id)
    baterias_query = apply_prefeitura_scope(Baterias.query, user, Baterias.prefeitura_id)
    veiculos_query = apply_prefeitura_scope(Veiculos.query, user, Veiculos.prefeitura_id)
    equipes_query = apply_prefeitura_scope(Equipe.query, user, Equipe.prefeitura_id)

    active_statuses = {"ativo", "ativa"}
    drones = drones_query.all()
    baterias = baterias_query.all()
    veiculos = veiculos_query.all()
    equipes_ativas = equipes_query.filter(Equipe.ativa.is_(True)).count()

    drones_ativos = [item for item in drones if (item.status or "").strip().lower() in active_statuses]
    drones_manutencao = [item for item in drones if "manuten" in (item.status or "").strip().lower()]
    baterias_alerta = [item for item in baterias if int(item.ciclo or 0) >= 200]
    veiculos_revisao = [
        item
        for item in veiculos
        if item.km_restante_revisao is not None and item.km_restante_revisao <= 500
    ]

    return {
        "drones_ativos": len(drones_ativos),
        "drones_manutencao": len(drones_manutencao),
        "baterias_alerta": len(baterias_alerta),
        "veiculos_revisao": len(veiculos_revisao),
        "equipes_ativas": equipes_ativas,
    }


def _build_checklist(risk):
    base = [
        "Confirmar autorização do local, equipe e responsável em campo.",
        "Validar baterias, hélices, firmware, memória e link controle/drone.",
        "Checar área de decolagem/pouso, pessoas, fios, árvores e obstáculos.",
        "Registrar coordenadas, referência visual e rota de acesso.",
    ]
    if risk["level"] != "ok":
        base.insert(0, "Reavaliar janela de voo antes de liberar a equipe.")
    return base


def build_operational_context(user, address: str):
    address = (address or "").strip()
    if len(address) < 6:
        raise ValueError("Informe um endereço mais completo para consultar.")

    geocode = _geocode_address(address)
    if not geocode:
        raise ValueError("Não foi possível localizar esse endereço.")

    weather = _fetch_weather(geocode["lat"], geocode["lng"])
    risk = _risk_level(weather)
    nearby = _build_nearby_solicitacoes(user, geocode["lat"], geocode["lng"])
    assets = _build_assets_summary(user)

    return {
        "ok": True,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "address": address,
        "location": geocode,
        "weather": weather,
        "risk": risk,
        "nearby_solicitacoes": nearby,
        "assets": assets,
        "checklist": _build_checklist(risk),
        "links": {
            "google_maps": f"https://www.google.com/maps/search/?api=1&query={geocode['lat']},{geocode['lng']}",
            "route": f"https://www.google.com/maps/dir/?api=1&destination={geocode['lat']},{geocode['lng']}",
            "windy": f"https://www.windy.com/{geocode['lat']}/{geocode['lng']}?{geocode['lat']},{geocode['lng']},14",
        },
    }
