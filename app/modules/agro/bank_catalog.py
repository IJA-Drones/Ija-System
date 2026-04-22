import json
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent / "data" / "bancos_bcb.json"


@lru_cache(maxsize=1)
def get_banco_agro_catalog():
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    items = []
    seen_labels = set()
    for item in payload.get("items", []):
        label = (item.get("label") or "").strip()
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        items.append(
            {
                "codigo": (item.get("codigo") or "").strip(),
                "nome": (item.get("nome") or "").strip(),
                "label": label,
            }
        )

    verified_at = (payload.get("verified_at") or "").strip()
    verified_at_display = verified_at
    if len(verified_at) == 10 and verified_at.count("-") == 2:
        year, month, day = verified_at.split("-")
        verified_at_display = f"{day}/{month}/{year}"

    return {
        "source_name": (payload.get("source_name") or "").strip(),
        "source_url": (payload.get("source_url") or "").strip(),
        "verified_at": verified_at,
        "verified_at_display": verified_at_display,
        "items": items,
    }


def get_banco_agro_options(*, current_label=None):
    catalog = get_banco_agro_catalog()
    options = [dict(item) for item in catalog["items"]]

    legacy_label = (current_label or "").strip()
    if legacy_label and not any(item["label"] == legacy_label for item in options):
        options.insert(
            0,
            {
                "codigo": "",
                "nome": legacy_label,
                "label": legacy_label,
                "legacy": True,
            },
        )

    return options
