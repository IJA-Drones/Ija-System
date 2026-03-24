from sqlalchemy import false, func

from app.models import Solicitacao, Usuario


REGIONAL_USER_TYPE = "regional"
ADMIN_PANEL_VIEW_TYPES = {"admin", "operario", "visualizar", "visualizador", REGIONAL_USER_TYPE}
ADMIN_PANEL_EDIT_TYPES = {"admin", "operario"}


def normalize_role(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_regiao(value: str | None) -> str:
    return (value or "").strip().upper()


def is_regional_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == REGIONAL_USER_TYPE


def get_user_regiao(user) -> str:
    return normalize_regiao(getattr(user, "regiao", None))


def apply_regiao_scope(query, user, column):
    if not is_regional_user(user):
        return query

    user_regiao = get_user_regiao(user)
    if not user_regiao:
        return query.filter(false())

    return query.filter(func.upper(func.coalesce(column, "")) == user_regiao)


def apply_solicitacao_regiao_scope(query, user):
    if not is_regional_user(user):
        return query

    user_regiao = get_user_regiao(user)
    if not user_regiao:
        return query.filter(false())

    return query.filter(
        Solicitacao.usuario.has(func.upper(func.coalesce(Usuario.regiao, "")) == user_regiao)
    )


def can_access_regiao(user, regiao: str | None) -> bool:
    if not is_regional_user(user):
        return True

    user_regiao = get_user_regiao(user)
    return bool(user_regiao) and user_regiao == normalize_regiao(regiao)
