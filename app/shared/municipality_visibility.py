"""Oculta municípios encerrados nas opções da interface, sem alterar cadastros."""

import re
import unicodedata

from sqlalchemy import or_, select


HIDDEN_MUNICIPALITY_IBGES = frozenset({"2610905"})
_HIDDEN_NAME = re.compile(r"\bpesqueira\b")


def municipality_visible(value):
    if isinstance(value, (tuple, list)) and len(value) == 2:
        value = value[1]
    if isinstance(value, dict):
        if str(value.get("ibge", "")).strip() in HIDDEN_MUNICIPALITY_IBGES:
            return False
        labels = (value.get("nome"), value.get("name"), value.get("slug"))
    elif isinstance(value, str):
        if value.strip() in HIDDEN_MUNICIPALITY_IBGES:
            return False
        labels = (value,)
    else:
        labels = (getattr(value, "nome", None), getattr(value, "name", None),
                  getattr(value, "slug", None), getattr(value, "nome_uvis", None))
    for label in labels:
        normalized = unicodedata.normalize("NFKD", str(label or "")).casefold()
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        if _HIDDEN_NAME.search(normalized.replace("_", " ")):
            return False
    return True


def visible_municipalities(values):
    return [value for value in values if municipality_visible(value)]


def municipality_label(value):
    if not municipality_visible(value):
        return "Vínculo preservado"
    return getattr(value, "nome", value) if value is not None else "-"


def visible_prefeitura_links(query, prefeitura_column):
    """Somente consultas de opções: mantém usuários sem vínculo e o escopo vigente."""
    from app.models import Prefeitura
    hidden = select(Prefeitura.id).where(or_(
        Prefeitura.slug.ilike("%pesqueira%"), Prefeitura.nome.ilike("%pesqueira%"),
    ))
    return query.filter(or_(prefeitura_column.is_(None), prefeitura_column.not_in(hidden)))


def register_municipality_filters(bp):
    bp.add_app_template_filter(visible_municipalities, "visible_municipalities")
    bp.add_app_template_filter(municipality_label, "municipality_label")
    bp.add_app_template_global(municipality_visible, "municipality_visible")
