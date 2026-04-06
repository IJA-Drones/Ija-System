from sqlalchemy import or_

from app.extensions import db
from app.models import Notificacao, Usuario
from app.shared.access import PREFEITURA_ADMIN_USER_TYPE, REGIONAL_USER_TYPE, normalize_regiao


ADMIN_USER_TYPES = ("admin", "operario", REGIONAL_USER_TYPE, PREFEITURA_ADMIN_USER_TYPE)


def admin_user_types():
    return ADMIN_USER_TYPES


def is_admin_managed_user(usuario) -> bool:
    return getattr(usuario, "tipo_usuario", None) in ADMIN_USER_TYPES


def login_em_uso(login: str, exclude_user_id=None):
    if not login:
        return None

    query = Usuario.query.filter(Usuario.login == login)
    if exclude_user_id is not None:
        query = query.filter(Usuario.id != exclude_user_id)
    return query.first()


def build_admin_users_query(q: str, tipo: str):
    query = Usuario.query.filter(Usuario.tipo_usuario.in_(ADMIN_USER_TYPES))

    if tipo in ADMIN_USER_TYPES:
        query = query.filter(Usuario.tipo_usuario == tipo)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
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
