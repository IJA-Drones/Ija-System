"""Provider-independent company fiscal registration (not emission readiness)."""
import re

FISCAL_FIELDS = {
    "inscricao_municipal": (30, "Inscrição municipal"),
    "inscricao_estadual": (30, "Inscrição estadual"),
    "regime_tributario": (1, "Regime tributário (CRT)"),
    "cnae_principal": (7, "CNAE principal"),
    "email_fiscal": (254, "E-mail fiscal"),
    "telefone_fiscal": (11, "Telefone"),
    "cep": (8, "CEP"),
    "logradouro": (180, "Logradouro"),
    "numero": (20, "Número"),
    "complemento": (120, "Complemento"),
    "bairro": (100, "Bairro"),
    "municipio": (100, "Município"),
    "uf": (2, "UF"),
    "codigo_municipio_ibge": (7, "Código IBGE do município"),
}
REGIMES = {"1": "Simples Nacional", "2": "Simples Nacional — excesso de sublimite", "3": "Regime normal", "4": "MEI"}
UF_CODES = dict(zip(
    "RO AC AM RR PA AP TO MA PI CE RN PB PE AL SE BA MG ES RJ SP PR SC RS MS MT GO DF".split(),
    "11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53".split(),
))


def validate_fiscal_form(form):
    """Validate supplied fields; omitted fields remain untouched for partial updates."""
    values = {}
    for field, (limit, label) in FISCAL_FIELDS.items():
        if field not in form:
            continue
        value = form.get(field, "").strip()
        if field in {"cep", "cnae_principal", "telefone_fiscal"}:
            value = re.sub(r"[.()/\s-]", "", value)
        if field == "uf":
            value = value.upper()
        if len(value) > limit:
            raise ValueError(f"{label}: use até {limit} caracteres.")
        if value:
            digits = {"cep": (8,), "cnae_principal": (7,), "telefone_fiscal": (10, 11), "codigo_municipio_ibge": (7,)}
            if field in digits and (not re.fullmatch(r"[0-9]+", value) or len(value) not in digits[field]):
                raise ValueError(f"{label}: formato inválido.")
            if field == "regime_tributario" and value not in REGIMES:
                raise ValueError("Selecione um regime tributário válido.")
            if field == "uf" and value not in UF_CODES:
                raise ValueError("Selecione uma UF válida.")
            if field == "email_fiscal" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError("Informe um e-mail fiscal válido.")
        values[field] = value or None
    return values


def validate_municipio(values, perfil):
    uf = values.get("uf", perfil.uf)
    code = values.get("codigo_municipio_ibge", perfil.codigo_municipio_ibge)
    if uf and code and not code.startswith(UF_CODES[uf]):
        raise ValueError("O código IBGE do município não corresponde à UF selecionada.")
