"""Model names used by inventory compatibility, without changing equipment records."""
import re


def canonical_equipment_model(value):
    name = " ".join((value or "").strip().split())
    if name.casefold() in {"teste", "test"}:
        return ""
    # DJI / AGRAS prefixes refer to the same agricultural model.
    match = re.fullmatch(r"(?:(?:DJI\s+)?AGRAS\s+|DJI\s+)?T\s*(\d+[A-Z]?)", name, re.I)
    return f"AGRAS T{match.group(1).upper()}" if match else name


def equipment_model_key(value):
    return canonical_equipment_model(value).casefold()


def compatible_model_names(part):
    names = {}
    values = (part.modelos_compativeis or "").split(",")
    # Existing specific links remain intact; expose their models in the new UI.
    values += [e.modelo for e in part.equipamentos_compativeis_exibicao
               if e.prefeitura_id == part.prefeitura_id]
    for value in values:
        name = canonical_equipment_model(value)
        if name:
            names.setdefault(name.casefold(), name)
    return list(names.values())


def part_matches_equipment(part, equipment):
    key = equipment_model_key(equipment.modelo)
    return bool(key and key in {equipment_model_key(name) for name in compatible_model_names(part)})
