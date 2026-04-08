import re
from decimal import Decimal, InvalidOperation


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def format_cpf(cpf_digits: str) -> str:
    digits = only_digits(cpf_digits)
    if len(digits) != 11:
        return cpf_digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def format_cnpj(cnpj_digits: str) -> str:
    digits = only_digits(cnpj_digits)
    if len(digits) != 14:
        return cnpj_digits
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def format_documento(documento: str) -> str:
    digits = only_digits(documento)
    if len(digits) == 11:
        return format_cpf(digits)
    if len(digits) == 14:
        return format_cnpj(digits)
    return documento


def format_phone_br(phone: str) -> str:
    digits = only_digits(phone)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:11]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:10]}"
    return phone


def format_cep(cep_digits: str) -> str:
    digits = only_digits(cep_digits)
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return cep_digits


def parse_currency_br(value) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace("R$", "").replace(" ", "")
    normalized = normalized.replace(".", "").replace(",", ".")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def format_currency_br(value) -> str:
    if value in (None, ""):
        return ""

    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return str(value)

    text = f"{amount:,.2f}"
    text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"
