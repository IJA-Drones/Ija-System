"""Categories supported by the public report form, not internal work orders."""

from app.shared.solicitacao_focos import build_focus_catalog


def build_public_focus_catalog():
    catalog = build_focus_catalog()
    catalog["tipo_visita_opcoes"] = [
        option for option in catalog["tipo_visita_opcoes"]
        if option in {"Aedes", "Culex", "Outro"}
    ]
    return catalog
