from app.models import Usuario
from app.shared.access import ADMIN_PANEL_VIEW_TYPES


def authenticate_user(login_value, password):
    user = Usuario.query.filter_by(login=login_value).first()
    if user and user.check_senha(password):
        return user
    return None


def get_authenticated_redirect_endpoint(user):
    if user.tipo_usuario in ADMIN_PANEL_VIEW_TYPES:
        return "main.admin_dashboard"
    if user.tipo_usuario == "equipe_uvis":
        return "main.dashboard_equipe_uvis"
    return "main.dashboard"
