"""Password rules for new credentials; existing hashes remain valid."""

from flask import current_app, has_app_context


class PasswordPolicyError(ValueError):
    pass


COMMON_PASSWORDS = frozenset({
    "password123456!",
    "senha123456789!",
    "admin123456789!",
    "qwerty123456789!",
    "123456789abcdef!",
    "oceanoazul12345!",
    "ijasystem123456!",
})


def security_enabled():
    return has_app_context() and current_app.config.get("SECURITY_CONTROLS_ENABLED", False)


def password_policy():
    return {
        "min_length": int(current_app.config.get("PASSWORD_MIN_LENGTH", 15)),
        "max_length": 128,
        "uppercase": current_app.config.get("PASSWORD_REQUIRE_UPPERCASE", True),
        "lowercase": current_app.config.get("PASSWORD_REQUIRE_LOWERCASE", True),
        "digit": current_app.config.get("PASSWORD_REQUIRE_DIGIT", True),
        "symbol": current_app.config.get("PASSWORD_REQUIRE_SYMBOL", True),
    }


def password_input(value):
    """Preserve spaces with the policy enabled; retain legacy trimming otherwise."""
    value = value or ""
    return value if security_enabled() else value.strip()


def validate_password(password):
    """Return a user-facing error, or None. Never apply this during login."""
    if not security_enabled():
        return None

    policy = password_policy()
    errors = []
    if len(password) < policy["min_length"]:
        errors.append(f"pelo menos {policy['min_length']} caracteres")
    if len(password) > policy["max_length"]:
        return f"A senha deve ter no máximo {policy['max_length']} caracteres."
    if password.casefold() in COMMON_PASSWORDS:
        return "Essa senha é muito previsível. Escolha outra."
    if policy["uppercase"] and not any(char.isupper() for char in password):
        errors.append("uma letra maiúscula")
    if policy["lowercase"] and not any(char.islower() for char in password):
        errors.append("uma letra minúscula")
    if policy["digit"] and not any(char.isdecimal() for char in password):
        errors.append("um número")
    if policy["symbol"] and not any(not char.isalnum() and not char.isspace() for char in password):
        errors.append("um símbolo (ex.: !, @, #)")
    if errors:
        return "A senha deve conter " + ", ".join(errors) + "."
    return None
