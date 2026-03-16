from app.models import Usuario


ADMIN_USER_TYPES = {"admin", "operario", "visualizar", "visualizador"}


def authenticate_user(login_value, password):
    user = Usuario.query.filter_by(login=login_value).first()
    if user and user.check_senha(password):
        return user
    return None


def get_authenticated_redirect_endpoint(user):
    if user.tipo_usuario in ADMIN_USER_TYPES:
        return "main.admin_dashboard"
    if user.tipo_usuario == "equipe_uvis":
        return "main.dashboard_equipe_uvis"
    return "main.dashboard"
