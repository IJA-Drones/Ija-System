"""Seleção pública de municípios por IBGE, sem consultar ou alterar o banco."""

import re

from werkzeug.exceptions import BadRequest

from app.modules.vigilancia.sinan import MUNICIPALITIES


def public_health_municipality(config, args):
    options = [
        {**item, "name": item["name"].removesuffix(" — capital")}
        for item in MUNICIPALITIES
    ]
    by_code = {item["ibge"]: item for item in options}
    default_code = str(config.get("INFODENGUE_GEOCODE") or "3550308").strip()
    default_city = str(config.get("INFODENGUE_CITY") or "").strip()
    # Preserva municípios que já eram configurados fora do catálogo regional.
    if default_code not in by_code and re.fullmatch(r"[0-9]{7}", default_code) and default_city:
        municipality = {
            "ibge": default_code, "name": default_city, "region": "configured",
            "uf": {"26": "PE", "35": "SP"}.get(default_code[:2], ""),
        }
        options.append(municipality)
        by_code[default_code] = municipality

    if len(args.getlist("municipio")) > 1:
        raise BadRequest("Selecione um único município para consultar o boletim.")
    requested = args.get("municipio", "").strip()
    if requested and requested not in by_code:
        raise BadRequest("Selecione um município disponível no filtro do boletim.")
    selected = by_code[requested or (default_code if default_code in by_code else "3550308")]
    source_config = {
        "INFODENGUE_GEOCODE": selected["ibge"],
        "INFODENGUE_CITY": selected["name"],
        "INFODENGUE_DISEASE": config.get("INFODENGUE_DISEASE") or "dengue",
        "INFODENGUE_LOOKBACK_WEEKS": config.get("INFODENGUE_LOOKBACK_WEEKS") or 8,
    }
    return selected, options, source_config
