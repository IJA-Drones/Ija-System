from app.modules.gestao_ti.permissions import capability
from sqlalchemy import false, func

from app.models import Solicitacao, Usuario


REGIONAL_USER_TYPE = "regional"
COVISA_LEGACY_USER_TYPE = "visualizar"
COVISA_USER_TYPE = "covisa"
COVISA_REGIAO = "COVISA"
PREFEITURA_ADMIN_USER_TYPE = "prefeitura_admin"
FINANCEIRO_ADMIN_USER_TYPE = "financeiro_admin"
FINANCEIRO_USER_TYPE = "financeiro"
ADMIN_USER_TYPE = "admin"
DIRECTOR_USER_TYPE = "diretor"
DEV_USER_TYPE = "dev"
VEICULOS_SUPERVISOR_USER_TYPES = {"sup_veiculos", "sup_veiculo"}
GLOBAL_ADMIN_USER_TYPES = {ADMIN_USER_TYPE, DIRECTOR_USER_TYPE, DEV_USER_TYPE}
ADMIN_PANEL_VIEW_TYPES = {
    *GLOBAL_ADMIN_USER_TYPES,
    "operario",
    "visualizar",
    "visualizador",
    COVISA_USER_TYPE,
    REGIONAL_USER_TYPE,
    PREFEITURA_ADMIN_USER_TYPE,
    *VEICULOS_SUPERVISOR_USER_TYPES,
}
ADMIN_PANEL_EDIT_TYPES = {
    *GLOBAL_ADMIN_USER_TYPES,
    "operario",
    PREFEITURA_ADMIN_USER_TYPE,
    *VEICULOS_SUPERVISOR_USER_TYPES,
}
AGRO_FINANCE_VIEW_TYPES = {
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
}
AGRO_FINANCE_EDIT_TYPES = {
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
}
FINANCEIRO_PANEL_VIEW_TYPES = AGRO_FINANCE_VIEW_TYPES | {DEV_USER_TYPE}


def normalize_role(value: str | None) -> str:
    return (value or "").strip().lower()


def is_veiculos_supervisor(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in VEICULOS_SUPERVISOR_USER_TYPES


def normalize_regiao(value: str | None) -> str:
    return (value or "").strip().upper()


def is_regional_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == REGIONAL_USER_TYPE


def is_covisa_user(user) -> bool:
    user_type = normalize_role(getattr(user, "tipo_usuario", None))
    if user_type == COVISA_USER_TYPE:
        return True
    return user_type == COVISA_LEGACY_USER_TYPE and get_user_regiao(user) == COVISA_REGIAO


def is_prefeitura_admin_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == PREFEITURA_ADMIN_USER_TYPE


def is_financeiro_admin_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == FINANCEIRO_ADMIN_USER_TYPE


def is_financeiro_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == FINANCEIRO_USER_TYPE


def is_agro_finance_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in AGRO_FINANCE_VIEW_TYPES


@capability(['area:financeiro'])
def can_access_financeiro_panel(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in FINANCEIRO_PANEL_VIEW_TYPES


@capability(['financeiro.configuracoes.configurar'])
def can_manage_financeiro_settings(user) -> bool:
    return is_financeiro_admin_user(user) or is_dev_user(user)


def is_admin_global_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in GLOBAL_ADMIN_USER_TYPES


def is_director_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == DIRECTOR_USER_TYPE


def is_dev_user(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) == DEV_USER_TYPE


@capability(['sistema.usuarios.gerenciar'])
def can_manage_user_work_flags(user) -> bool:
    return normalize_role(getattr(user, "tipo_usuario", None)) in {DIRECTOR_USER_TYPE, DEV_USER_TYPE}


def get_user_regiao(user) -> str:
    return normalize_regiao(getattr(user, "regiao", None))


def get_user_prefeitura_id(user):
    value = getattr(user, "prefeitura_id", None)
    if value is not None:
        return value
    # A pilot's tenant may be stored on the linked pilot record.
    from app.modules.gestao_ti.permissions import active_configuration
    if active_configuration(user) is not None:
        return getattr(getattr(user, "piloto", None), "prefeitura_id", None)
    return None


def central_ti_team_ids(user):
    """None means no team restriction; an empty tuple means no linked team."""
    from app.modules.gestao_ti.permissions import active_configuration
    if active_configuration(user) is None:
        return None
    role = normalize_role(getattr(user, "tipo_usuario", None))
    if role not in {"piloto", "equipe_oceano"}:
        return None
    from flask import g, has_request_context
    key = getattr(user, "id", None)
    cache = g.setdefault("_central_ti_team_ids", {}) if has_request_context() else {}
    if key in cache:
        return cache[key]
    from app.models import Equipe, EquipePiloto
    query = Equipe.query.filter(Equipe.ativa.is_(True))
    if role == "piloto":
        pilot_id = getattr(user, "piloto_id", None)
        if not pilot_id:
            return ()
        query = query.filter(Equipe.membros.any(EquipePiloto.piloto_id == pilot_id))
    else:
        try:
            query = query.filter(Equipe.id == int(getattr(user, "codigo_setor", "")))
        except (ValueError, TypeError):
            return ()
    tenant = get_user_prefeitura_id(user)
    if tenant is not None:
        query = query.filter(Equipe.prefeitura_id == tenant)
    cache[key] = tuple(row[0] for row in query.with_entities(Equipe.id).all())
    return cache[key]


def apply_prefeitura_scope(query, user, column):
    role = normalize_role(getattr(user, "tipo_usuario", None)) if user is not None else None
    if user is None or role in GLOBAL_ADMIN_USER_TYPES:
        return query

    from app.modules.gestao_ti.permissions import active_configuration
    configured = active_configuration(user) is not None
    teams = central_ti_team_ids(user)
    if teams is not None:
        model = getattr(column, "class_", None)
        if model is not None and model.__name__ == "Equipe":
            query = query.filter(model.id.in_(teams))
        elif model is Usuario:
            from app.extensions import db
            query = query.filter(Usuario.id.in_(
                db.select(Solicitacao.usuario_id).where(Solicitacao.equipe_id.in_(teams))
            ))
        elif model is not None and hasattr(model, "equipe_id"):
            query = query.filter(model.equipe_id.in_(teams))
    if configured and role == "piloto_agro":
        pilot = getattr(user, "piloto_agro", None)
        team = getattr(pilot, "equipe_agro_id", None) if getattr(pilot, "ativo", False) else None
        model = getattr(column, "class_", None)
        if model is not None and hasattr(model, "equipe_agro_id"):
            query = query.filter(model.equipe_agro_id == team) if team else query.filter(false())
        elif model is not None and model.__name__ == "EquipeAgro":
            query = query.filter(model.id == team) if team else query.filter(false())
    prefeitura_id = get_user_prefeitura_id(user)
    if prefeitura_id is None:
        # Finance's existing IJA scope is independent of a municipal tenant.
        # A newly enabled municipal module must never fall through to all data.
        model = getattr(column, "class_", None)
        municipal = model is not None and model.__name__ in {
            "Solicitacao", "Denuncia", "Equipe", "Pilotos", "Drones", "Baterias", "Veiculos", "Clientes", "Usuario",
        }
        legacy_unscoped = role in ADMIN_PANEL_VIEW_TYPES and not (is_veiculos_supervisor(user) or is_prefeitura_admin_user(user))
        if configured and municipal and not legacy_unscoped and not teams:
            return query.filter(false())
        if is_veiculos_supervisor(user):
            return query.filter(false())
        if is_prefeitura_admin_user(user):
            return query.filter(false())
        return query

    return query.filter(column == prefeitura_id)


def apply_solicitacao_prefeitura_scope(query, user):
    query = apply_prefeitura_scope(query, user, Solicitacao.prefeitura_id)
    from app.modules.gestao_ti.permissions import active_configuration
    if active_configuration(user) is not None:
        role = normalize_role(getattr(user, "tipo_usuario", None))
        if role == "uvis":
            query = query.filter(Solicitacao.usuario_id == user.id)
        elif role == "equipe_uvis":
            query = query.filter(Solicitacao.usuario_id == getattr(user, "equipe_uvis_uvis_usuario_id", None))
    return query


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
