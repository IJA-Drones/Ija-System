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

    if len(args.getlist("regiao")) > 1 or args.get("regiao", "todos") not in {"todos", "condomar"}:
        raise BadRequest("Selecione uma região disponível no filtro.")
    if len(args.getlist("municipio")) > 1:
        raise BadRequest("Selecione um único município para consultar o boletim.")
    requested = args.get("municipio", "").strip()
    if requested and requested not in by_code:
        raise BadRequest("Selecione um município disponível no filtro do boletim.")
    if args.get("regiao") == "condomar":
        options = [item for item in options if item["region"] == "condomar"]
    available = {item["ibge"] for item in options}
    # Ao mudar de região, a cidade anterior pode sair da lista. Selecionar
    # uma cidade da nova lista sem transformar a troca de região em erro 400.
    selected_code = next((code for code in (requested, default_code, options[0]["ibge"]) if code in available))
    selected = by_code[selected_code]
    source_config = {
        "INFODENGUE_GEOCODE": selected["ibge"],
        "INFODENGUE_CITY": selected["name"],
        "INFODENGUE_DISEASE": config.get("INFODENGUE_DISEASE") or "dengue",
        "INFODENGUE_LOOKBACK_WEEKS": config.get("INFODENGUE_LOOKBACK_WEEKS") or 8,
    }
    return selected, options, source_config
