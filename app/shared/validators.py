import re

from app.shared.formatters import format_cnpj, format_cpf, only_digits


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def validate_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10) % 11
    digito_1 = 0 if digito_1 == 10 else digito_1
    if digito_1 != int(cpf[9]):
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10) % 11
    digito_2 = 0 if digito_2 == 10 else digito_2
    return digito_2 == int(cpf[10])


def validate_cnpj(cnpj: str) -> bool:
    cnpj = only_digits(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    soma = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    digito_1 = 11 - (soma % 11)
    digito_1 = 0 if digito_1 >= 10 else digito_1
    if digito_1 != int(cnpj[12]):
        return False

    soma = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    digito_2 = 11 - (soma % 11)
    digito_2 = 0 if digito_2 >= 10 else digito_2
    return digito_2 == int(cnpj[13])


def validate_documento(documento: str):
    digits = only_digits(documento)

    if len(digits) == 11:
        if not validate_cpf(digits):
            return False, "CPF", digits, None, "CPF invalido (digitos verificadores nao conferem)."
        return True, "CPF", digits, format_cpf(digits), None

    if len(digits) == 14:
        if not validate_cnpj(digits):
            return False, "CNPJ", digits, None, "CNPJ invalido (digitos verificadores nao conferem)."
        return True, "CNPJ", digits, format_cnpj(digits), None

    return False, None, digits, None, "Documento deve ter 11 (CPF) ou 14 (CNPJ) digitos."
