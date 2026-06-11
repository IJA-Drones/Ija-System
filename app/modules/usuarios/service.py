from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models import Notificacao, Usuario
from app.shared.access import (
    DEV_USER_TYPE,
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
    PREFEITURA_ADMIN_USER_TYPE,
    REGIONAL_USER_TYPE,
    is_admin_global_user,
    is_dev_user,
    normalize_regiao,
)
from app.shared.query_filters import id_search_clause


ADMIN_USER_TYPES = (
    DEV_USER_TYPE,
    "admin",
    "operario",
    REGIONAL_USER_TYPE,
    PREFEITURA_ADMIN_USER_TYPE,
    FINANCEIRO_ADMIN_USER_TYPE,
    FINANCEIRO_USER_TYPE,
    "covisa",
)
LEGACY_COVISA_USER_TYPE = "visualizar"
LEGACY_COVISA_REGIAO = "COVISA"


def normalize_admin_user_type(tipo_usuario: str | None) -> str:
    tipo_normalizado = (tipo_usuario or "").strip().lower()
    if tipo_normalizado == "covisa":
        return LEGACY_COVISA_USER_TYPE
    return tipo_normalizado


def is_legacy_covisa_user(usuario) -> bool:
    return (
        getattr(usuario, "tipo_usuario", None) == LEGACY_COVISA_USER_TYPE
        and normalize_regiao(getattr(usuario, "regiao", None)) == LEGACY_COVISA_REGIAO
    )


def normalize_admin_user_regiao(tipo_usuario: str, regiao: str | None):
    if (tipo_usuario or "").strip().lower() == "covisa":
        return LEGACY_COVISA_REGIAO
    return normalize_regiao(regiao) or None


def admin_user_types():
    return ADMIN_USER_TYPES


def is_admin_managed_user(usuario) -> bool:
    return getattr(usuario, "tipo_usuario", None) in ADMIN_USER_TYPES or is_legacy_covisa_user(usuario)


def can_assign_dev_role(actor) -> bool:
    if is_dev_user(actor):
        return True
    return is_admin_global_user(actor) and not Usuario.query.filter_by(tipo_usuario=DEV_USER_TYPE).first()


def can_manage_admin_user(actor, usuario) -> bool:
    return getattr(usuario, "tipo_usuario", None) != DEV_USER_TYPE or is_dev_user(actor)


def get_admin_user_type_form_value(usuario) -> str:
    if is_legacy_covisa_user(usuario):
        return "covisa"
    return (getattr(usuario, "tipo_usuario", None) or "").strip().lower()


def login_em_uso(login: str, exclude_user_id=None):
    if not login:
        return None

    query = Usuario.query.filter(Usuario.login == login)
    if exclude_user_id is not None:
        query = query.filter(Usuario.id != exclude_user_id)
    return query.first()


def build_admin_users_query(q: str, tipo: str):
    query = Usuario.query.filter(
        or_(
            Usuario.tipo_usuario.in_(
                (
                    DEV_USER_TYPE,
                    "admin",
                    "operario",
                    REGIONAL_USER_TYPE,
                    PREFEITURA_ADMIN_USER_TYPE,
                    FINANCEIRO_ADMIN_USER_TYPE,
                    FINANCEIRO_USER_TYPE,
                )
            ),
            and_(
                Usuario.tipo_usuario == LEGACY_COVISA_USER_TYPE,
                func.upper(func.coalesce(Usuario.regiao, "")) == LEGACY_COVISA_REGIAO,
            ),
        )
    )

    if tipo in ADMIN_USER_TYPES:
        if tipo == "covisa":
            query = query.filter(
                Usuario.tipo_usuario == LEGACY_COVISA_USER_TYPE,
                func.upper(func.coalesce(Usuario.regiao, "")) == LEGACY_COVISA_REGIAO,
            )
        else:
            query = query.filter(Usuario.tipo_usuario == tipo)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                id_search_clause(Usuario.id, q),
                Usuario.nome_uvis.ilike(like),
                Usuario.login.ilike(like),
            )
        )

    return query.order_by(Usuario.tipo_usuario.asc(), Usuario.nome_uvis.asc())


def validate_new_admin_user(
    nome: str,
    login: str,
    tipo_usuario: str,
    regiao: str,
    prefeitura_id,
    senha: str,
    senha2: str,
):
    errors = {}

    if not nome:
        errors["nome"] = "Informe o nome."
    if not login:
        errors["login"] = "Informe o login."
    if tipo_usuario not in ADMIN_USER_TYPES:
        errors["tipo_usuario"] = "Selecione um tipo valido."
    if tipo_usuario == REGIONAL_USER_TYPE and not normalize_regiao(regiao):
        errors["regiao"] = "Informe a regiao do usuario regional."
    if tipo_usuario == PREFEITURA_ADMIN_USER_TYPE and not prefeitura_id:
        errors["prefeitura_id"] = "Selecione a prefeitura desse usuario."
    if not senha:
        errors["senha"] = "Informe uma senha."
    if not senha2:
        errors["senha2"] = "Confirme a senha."
    if senha and senha2 and senha != senha2:
        errors["senha2"] = "As senhas nao conferem."
    if login and login_em_uso(login):
        errors["login"] = "Esse login ja esta em uso."

    return errors


def validate_edit_admin_user(
    nome_uvis: str,
    login: str,
    tipo_usuario: str,
    regiao: str,
    prefeitura_id,
    senha: str,
    senha2: str,
    usuario_id: int,
):
    errors = {}

    if not nome_uvis:
        errors["nome_uvis"] = "Informe o nome."
    if not login:
        errors["login"] = "Informe o login."
    if tipo_usuario not in ADMIN_USER_TYPES:
        errors["tipo_usuario"] = "Tipo invalido."
    if tipo_usuario == REGIONAL_USER_TYPE and not normalize_regiao(regiao):
        errors["regiao"] = "Informe a regiao do usuario regional."
    if tipo_usuario == PREFEITURA_ADMIN_USER_TYPE and not prefeitura_id:
        errors["prefeitura_id"] = "Selecione a prefeitura desse usuario."

    if senha or senha2:
        if len(senha) < 4:
            errors["senha"] = "Senha muito curta (min. 4)."
        if senha != senha2:
            errors["senha2"] = "As senhas nao conferem."

    if login and login_em_uso(login, exclude_user_id=usuario_id):
        errors["login"] = "Esse login ja esta em uso."

    return errors


def validate_password_reset(senha: str, senha2: str, **_kwargs):
    if not senha or not senha2:
        return "Informe e confirme a senha."

    if senha != senha2:
        return "As senhas nao conferem."

    return None


def delete_admin_user(usuario):
    Notificacao.query.filter(Notificacao.usuario_id == usuario.id).delete(synchronize_session=False)
    db.session.delete(usuario)
