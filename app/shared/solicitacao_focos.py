from __future__ import annotations

import unicodedata


TIPO_VISITA_OPCOES = ["Aedes", "Culex", "Outro"]
TIPO_IMOVEL_OPCOES = ["Imovel Geral", "PE Cadastrado"]
TIPO_VISITA_OUTRO_LABEL = "Outro"

Aedes_FOCOS_POR_IMOVEL = {
    "Imovel Geral": [
        "Acumulador",
        "Edificação Abandonada com Inservíveis",
        "Terreno com Inservíveis",
        "Obra",
        "Caixa d'agua",
        "Piscina",
        "Laje com Acúmulo de Água",
        "Telhado com Acumulo de Agua",
    ],
    "PE Cadastrado": [
        "Autódromo/Kartódromo",
        "Borracharia/Recauchutadora",
        "Oficina Mecânica/Funilaria/Pintura",
        "Ferro Velho/Sucata/Desmanche",
        "Pátio de Veículos Abandonados/Apreendidos",
        "Pátio de Caminhões/Ônibus",
        "Pátio de Manobra Rodoviária/Ferroviária",
        "Pátio de Fábricas/Indústrias",
        "Pátio com Container/Caçamba/Entulho",
        "Pátio de Escola de Samba/Espaço Cultural",
        "Depósito de Material de Construção",
        "Depósito de Maquinário",
        "Marina/Pátio de Embarcação",
        "Reciclagem/Ecoponto/Cooperativa",
        "Floricultura/Jardinagem/Viveiro de Plantas",
        "Cemitério",
    ],
}

# O PDF confirma a divisao principal de Aedes; para Culex mantivemos as
# categorias especificas que ja existiam no sistema e seguem o fluxo atual.
CULEX_FOCOS = [
    "Area alagada",
    "Corrego",
    "Piscinao",
]

LEGACY_FOCOS = [
    "caixa d'agua",
    "Casa abandonada com inservíveis",
    "Galpão com inservíveis",
    "Imovel com inservíveis",
    "Laje/telhado com Acúmulo de água",
    "P.E Cadastrado",
    "Pátio com Veículos",
    "Piscina",
    "Piscinao",
    "Reciclagem",
    "Terreno com inservíveis",
]


def _normalize(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def same_normalized(left: str | None, right: str | None) -> bool:
    return _normalize(left) == _normalize(right)


def _unique(items):
    ordered = []
    seen = set()
    for item in items:
        if not item:
            continue
        key = _normalize(item)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


FORM_FOCOS_OUTRO = _unique(
    [
        *Aedes_FOCOS_POR_IMOVEL["Imovel Geral"],
        *Aedes_FOCOS_POR_IMOVEL["PE Cadastrado"],
        *CULEX_FOCOS,
    ]
)

FILTER_FOCO_OPCOES = _unique(
    [
        *FORM_FOCOS_OUTRO,
        *LEGACY_FOCOS,
    ]
)


def canonical_tipo_visita(value: str | None) -> str | None:
    lookup = {
        "aedes": "Aedes",
        "culex": "Culex",
        "outro": "Outro",
        "outros": "Outro",
    }
    return lookup.get(_normalize(value))


def canonical_tipo_imovel(value: str | None) -> str | None:
    lookup = {
        "imovel geral": "Imovel Geral",
        "pe cadastrado": "PE Cadastrado",
        "p.e cadastrado": "PE Cadastrado",
    }
    return lookup.get(_normalize(value))


def _match_option(value: str | None, options: list[str]) -> str | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    for option in options:
        if _normalize(option) == normalized:
            return option
    return None


def get_foco_opcoes(tipo_visita: str | None, tipo_imovel: str | None = None) -> list[str]:
    visit = canonical_tipo_visita(tipo_visita)
    if visit == "Aedes":
        imovel = canonical_tipo_imovel(tipo_imovel)
        if not imovel:
            return []
        return list(Aedes_FOCOS_POR_IMOVEL[imovel])
    if visit == "Culex":
        return list(CULEX_FOCOS)
    return list(FORM_FOCOS_OUTRO)


def get_tipo_visita_opcoes(allow_other: bool = True) -> list[str]:
    if allow_other:
        return list(TIPO_VISITA_OPCOES)
    return [opcao for opcao in TIPO_VISITA_OPCOES if not same_normalized(opcao, TIPO_VISITA_OUTRO_LABEL)]


def validate_foco_selection(
    tipo_visita: str | None,
    tipo_imovel: str | None,
    foco: str | None,
    *,
    allow_custom_tipo_visita: bool = False,
    tipo_visita_outro: str | None = None,
):
    visit = canonical_tipo_visita(tipo_visita)
    if not visit:
        raise ValueError("Selecione um tipo de visita valido.")

    tipo_visita_final = visit

    if same_normalized(visit, TIPO_VISITA_OUTRO_LABEL):
        if not allow_custom_tipo_visita:
            raise ValueError("Selecione um tipo de visita valido.")

        tipo_visita_customizado = (tipo_visita_outro or "").strip()
        if not tipo_visita_customizado:
            raise ValueError("Informe qual e o tipo de visita ao selecionar Outro.")

        tipo_visita_final = tipo_visita_customizado

    if visit == "Aedes":
        imovel = canonical_tipo_imovel(tipo_imovel)
        if not imovel:
            raise ValueError("Selecione o tipo de imovel para atendimentos Aedes.")
    else:
        imovel = None

    foco_opcoes = get_foco_opcoes(visit, imovel)
    foco_canonico = _match_option(foco, foco_opcoes)
    if not foco_canonico:
        raise ValueError("Selecione um foco da acao valido para o tipo de visita informado.")

    return tipo_visita_final, imovel, foco_canonico


def build_focus_catalog():
    return {
        "tipo_visita_opcoes": list(TIPO_VISITA_OPCOES),
        "tipo_imovel_opcoes": list(TIPO_IMOVEL_OPCOES),
        "aedes": {key: list(values) for key, values in Aedes_FOCOS_POR_IMOVEL.items()},
        "culex": list(CULEX_FOCOS),
        "outro": list(FORM_FOCOS_OUTRO),
        "tipo_visita_outro_label": TIPO_VISITA_OUTRO_LABEL,
        "filtro_foco_opcoes": list(FILTER_FOCO_OPCOES),
    }
