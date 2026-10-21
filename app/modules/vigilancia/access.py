"""Coordenação de campo por identidade; permissões de TI seguem nas rotas."""

from app.shared.access import is_admin_global_user, is_covisa_user, is_prefeitura_admin_user
from app.modules.gestao_ti.permissions import has_permission


def can_coordinate_field(user):
    if is_admin_global_user(user) or is_prefeitura_admin_user(user):
        return True
    prefeitura = getattr(user, "prefeitura_id", None)
    return (is_covisa_user(user) and isinstance(prefeitura, int)
            and not isinstance(prefeitura, bool) and prefeitura > 0)


def can_delete_field(user):
    """Dev tem exclusão permanente; Admin e COVISA seguem a Central de TI."""
    role = (getattr(user, 'tipo_usuario', '') or '').strip().lower()
    return bool(getattr(user, 'is_authenticated', False) and
                (role in {'dev', 'admin'} or is_covisa_user(user)) and
                can_coordinate_field(user) and
                has_permission(user, 'prefeitura.vigilancia.excluir', legacy=True))
