"""Audience restriction for the preventive maintenance area."""
from app.shared.access import normalize_role


def can_use_preventivas(user):
    return bool(
        getattr(user, 'is_authenticated', False)
        and normalize_role(getattr(user, 'tipo_usuario', None)) in {'dev', 'manutencao'}
    )
