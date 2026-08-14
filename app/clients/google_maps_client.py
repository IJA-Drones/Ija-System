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
