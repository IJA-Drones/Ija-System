"""Bind chat continuity and export previews to the current server-owned access."""
import hashlib
import json
import secrets

from flask import session

from app.modules.gestao_ti.permissions import active_configuration
from app.shared.access import (
    central_ti_team_ids, get_user_prefeitura_id, get_user_regiao, normalize_role,
)


def access_fingerprint(user):
    permissions = active_configuration(user)
    role = normalize_role(getattr(user, 'tipo_usuario', None))
    agro_pilot = getattr(user, 'piloto_agro', None) if role == 'piloto_agro' else None
    teams = central_ti_team_ids(user)
    scope = {
        'user': str(user.get_id()),
        'role': role,
        'prefeitura': get_user_prefeitura_id(user),
        'region': get_user_regiao(user),
        'uvis': getattr(user, 'equipe_uvis_uvis_usuario_id', None),
        'sector': getattr(user, 'codigo_setor', None),
        'pilot': getattr(user, 'piloto_id', None),
        'teams': sorted(teams) if teams is not None else None,
        'agro_pilot': getattr(user, 'piloto_agro_id', None),
        'agro_team': getattr(agro_pilot, 'equipe_agro_id', None),
        'agro_active': bool(getattr(agro_pilot, 'ativo', False)),
        'agro_employee': bool(getattr(user, 'trabalha_agro', False)),
        'employee': bool(getattr(user, 'trabalha_oceano_azul', False)),
        'permissions': sorted(permissions) if permissions is not None else None,
    }
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


def chat_key(user):
    if not session.get('azul_chat_id'):
        session['azul_chat_id'] = secrets.token_urlsafe(24)
    return f'{user.get_id()}:{session["azul_chat_id"]}:{access_fingerprint(user)}'
