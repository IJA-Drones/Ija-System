from sqlalchemy import false, func

from app.models import Solicitacao, Usuario


REGIONAL_USER_TYPE = "regional"
PREFEITURA_ADMIN_USER_TYPE = "prefeitura_admin"
FINANCEIRO_ADMIN_USER_TYPE = "financeiro_admin"
FINANCEIRO_USER_TYPE = "financeiro"
ADMIN_USER_TYPE = "admin"
DIRECTOR_USER_TYPE = "diretor"
DEV_USER_TYPE = "dev"
GLOBAL_ADMIN_USER_TYPES = {ADMIN_USER_TYPE, DIRECTOR_USER_TYPE, DEV_USER_TYPE}
ADMIN_PANEL_VIEW_TYPES = {
    *GLOBAL_ADMIN_USER_TYPES,
    "operario",
    "visualizar",
    "visualizador",
    REGIONAL_USER_TYPE,
    PREFEITURA_ADMIN_USER_TYPE,
}
ADMIN_PANEL_EDIT_TYPES = {*GLOBAL_ADMIN_USER_TYPES, "operario", PREFEITURA_ADMIN_USER_TYPE}
AGRO_FINANCE_VIEW_TYPES = {
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
}
AGRO_FINANCE_EDIT_TYPES = {
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
}


def normalize_role(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_regiao(value: str | None) -> str:
    return (value or "").strip().upper()


def is_regional_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == REGIONAL_USER_TYPE


def is_prefeitura_admin_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == PREFEITURA_ADMIN_USER_TYPE


def is_financeiro_admin_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == FINANCEIRO_ADMIN_USER_TYPE


def is_financeiro_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == FINANCEIRO_USER_TYPE


def is_agro_finance_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in AGRO_FINANCE_VIEW_TYPES


def is_admin_global_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in GLOBAL_ADMIN_USER_TYPES


def is_director_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == DIRECTOR_USER_TYPE


def is_dev_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == DEV_USER_TYPE


def get_user_regiao(user) -> str:
    return normalize_regiao(getattr(user, "regiao", None))


def get_user_prefeitura_id(user):
    return getattr(user, "prefeitura_id", None)


def apply_prefeitura_scope(query, user, column):
    if user is None or is_admin_global_user(user):
        return query

    prefeitura_id = get_user_prefeitura_id(user)
    if prefeitura_id is None:
        if is_prefeitura_admin_user(user):
            return query.filter(false())
        return query

    return query.filter(column == prefeitura_id)


def apply_solicitacao_prefeitura_scope(query, user):
    return apply_prefeitura_scope(query, user, Solicitacao.prefeitura_id)


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
