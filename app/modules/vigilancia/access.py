"""Coordenação de campo por identidade; permissões de TI seguem nas rotas."""

from app.shared.access import is_admin_global_user, is_covisa_user, is_prefeitura_admin_user


def can_coordinate_field(user):
    if is_admin_global_user(user) or is_prefeitura_admin_user(user):
        return True
    prefeitura = getattr(user, "prefeitura_id", None)
    return (is_covisa_user(user) and isinstance(prefeitura, int)
            and not isinstance(prefeitura, bool) and prefeitura > 0)
