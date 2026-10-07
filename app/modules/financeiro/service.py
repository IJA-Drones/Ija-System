"""Company catalog for the finance hub, initially with one demo entry.

The hub and workspace consume a list of companies. Registration and persisted
company permissions will be added after the finance area is validated.
"""

from app.modules.agro.service import can_access_agro_panel
from app.shared.access import can_access_financeiro_panel
from app.shared.formatters import format_documento


def build_financeiro_empresas(user):
    can_open_ija = can_access_financeiro_panel(user) and can_access_agro_panel(user)
    cnpj = "11111111000111"
    return [{
        "slug": "ija",
        "nome": "IJA",
        "sigla": "IJA",
        "razao_social": "IJA",
        "cnpj": cnpj,
        "cnpj_formatado": format_documento(cnpj),
        "operacao": "Agro",
        "disponivel": can_open_ija,
        "demonstracao": True,
    }]
