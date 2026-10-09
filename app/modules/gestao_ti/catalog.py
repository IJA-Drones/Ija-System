"""Options for the central editor; these are not active authorization rules."""

import json
from pathlib import Path


CATALOG = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
PROFILE_CODES = frozenset(profile["id"] for profile in CATALOG["profiles"])
AREA_CODES = frozenset(area["id"] for area in CATALOG["catalog"])
PERMISSION_CODES = frozenset(
    f"{area['id']}.{module[0]}.{action}"
    for area in CATALOG["catalog"]
    for module in area["modules"]
    for action in module[4].split()
)
