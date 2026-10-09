import os
from urllib.parse import urlencode

import requests
from flask import current_app


def geocode_endereco_google(*, logradouro, numero, bairro, cidade, uf, cep=None):
    api_key = (
        current_app.config.get("Maps_KEY_BACK")
        or os.getenv("GOOGLE_MAPS_KEY_BACK")
        or current_app.config.get("KEY_API_GOOGLE_MAPS")
        or os.getenv("KEY_API_GOOGLE_MAPS")
    )
    if not api_key:
        raise RuntimeError("Chave do Google Maps nao encontrada nas configuracoes do app")

    partes = [
        (logradouro or "").strip(),
        (numero or "").strip(),
        (bairro or "").strip(),
        (cidade or "").strip(),
        (uf or "").strip(),
    ]
    if cep:
        partes.append((cep or "").strip())
    partes.append("Brasil")

    address = ", ".join([parte for parte in partes if parte])
    params = {
        "address": address,
        "key": api_key,
        "region": "br",
    }

    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(params)
    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get("status") != "OK":
        return None, None, None

    results = data.get("results") or []
    if not results:
        return None, None, None

    first_result = results[0]
    location = first_result.get("geometry", {}).get("location", {})
    place_id = first_result.get("place_id")

    return location.get("lat"), location.get("lng"), place_id


def reverse_geocode_lat_lng_google(*, lat, lng):
    api_key = (
        current_app.config.get("Maps_KEY_BACK")
        or os.getenv("GOOGLE_MAPS_KEY_BACK")
        or current_app.config.get("KEY_API_GOOGLE_MAPS")
        or os.getenv("KEY_API_GOOGLE_MAPS")
    )
    if not api_key:
        raise RuntimeError("Chave do Google Maps nao encontrada nas configuracoes do app")

    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key,
        "region": "br",
    }

    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(params)
    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get("status") != "OK":
        return None, None

    results = data.get("results") or []
    if not results:
        return None, None

    first_result = results[0]
    return first_result.get("formatted_address"), first_result.get("place_id")


def reverse_geocode_lat_lng_google_details(*, lat, lng):
    api_key = (
        current_app.config.get("Maps_KEY_BACK")
        or os.getenv("GOOGLE_MAPS_KEY_BACK")
        or current_app.config.get("KEY_API_GOOGLE_MAPS")
        or os.getenv("KEY_API_GOOGLE_MAPS")
    )
    if not api_key:
        raise RuntimeError("Chave do Google Maps nao encontrada nas configuracoes do app")

    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key,
        "region": "br",
    }

    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(params)
    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get("status") != "OK":
        return None

    results = data.get("results") or []
    if not results:
        return None

    first_result = results[0]
    components = _components_by_type(first_result.get("address_components") or [])
    route = _component_value(components, "route")
    street_number = _component_value(components, "street_number")
    neighborhood = (
        _component_value(components, "sublocality_level_1")
        or _component_value(components, "sublocality")
        or _component_value(components, "political")
    )
    city = (
        _component_value(components, "administrative_area_level_2")
        or _component_value(components, "locality")
    )
    uf = _component_value(components, "administrative_area_level_1", short=True)
    cep = _component_value(components, "postal_code")

    return {
        "formatted_address": first_result.get("formatted_address"),
        "place_id": first_result.get("place_id"),
        "logradouro": route or "",
        "numero": street_number or "",
        "bairro": neighborhood or "",
        "cidade": city or "",
        "uf": uf or "",
        "cep": cep or "",
        "lat": lat,
        "lng": lng,
    }


def _components_by_type(address_components):
    by_type = {}
    for component in address_components:
        for type_name in component.get("types") or []:
            by_type.setdefault(type_name, component)
    return by_type


def _component_value(components, type_name, *, short=False):
    component = components.get(type_name) or {}
    key = "short_name" if short else "long_name"
    return component.get(key)
