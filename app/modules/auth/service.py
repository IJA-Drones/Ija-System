from app.models import Usuario
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, is_agro_finance_user


def _authenticate_any_user(login_value, password):
    user = Usuario.query.filter_by(login=login_value).first()
    if user and user.check_senha(password):
        if user.tipo_usuario == "piloto_agro":
            piloto_agro = getattr(user, "piloto_agro", None)
            if piloto_agro is None or not piloto_agro.ativo:
                return None
        return user
    return None


def authenticate_user(login_value, password):
    user = _authenticate_any_user(login_value, password)
    if not user or user.tipo_usuario == "piloto_agro":
        return None
    return user


def authenticate_uvis_operacional(login_value, password):
    user = _authenticate_any_user(login_value, password)
    if not user:
        return None

    if user.tipo_usuario == "uvis":
        return user

    if user.tipo_usuario == "equipe_uvis" and getattr(user, "equipe_uvis_uvis_usuario_id", None):
        return user

    return None


def authenticate_piloto_agro(login_value, password):
    user = _authenticate_any_user(login_value, password)
    if not user or user.tipo_usuario != "piloto_agro":
        return None, "invalid"

    piloto_agro = getattr(user, "piloto_agro", None)
    if piloto_agro is None:
        return None, "missing"

    if not piloto_agro.ativo:
        return None, "inactive"

    return user, None


def get_authenticated_redirect_endpoint(user):
    if is_agro_finance_user(user):
        return "main.admin_agro"
    if user.tipo_usuario in ADMIN_PANEL_VIEW_TYPES:
        return "main.admin_dashboard"
    if user.tipo_usuario == "piloto":
        return "main.piloto_os"
    if user.tipo_usuario == "piloto_agro":
        return "main.agro_piloto_dashboard"
    if user.tipo_usuario == "equipe_uvis":
        return "main.dashboard_equipe_uvis"
    return "main.dashboard"
