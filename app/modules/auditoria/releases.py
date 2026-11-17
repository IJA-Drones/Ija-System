"""Record the first observation of a release without claiming a deploy completion."""
import os
import re
import threading
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.models import AuditoriaUsuario


def release_sha(app):
    value = app.config.get('APP_RELEASE_SHA') or os.getenv('RENDER_GIT_COMMIT', '')
    return value.lower() if isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{40,64}', value) else None


def register_release_observation(app):
    lock = threading.Lock()
    state = {'recorded': False}

    @app.before_request
    def observe_release():
        sha = release_sha(app)
        if not sha or state['recorded']:
            return
        with lock:
            if state['recorded']:
                return
            event_id = str(uuid5(NAMESPACE_URL, 'oceano-azul:release:' + sha))
            table = AuditoriaUsuario.__table__
            try:
                with db.engine.begin() as conn:
                    exists = conn.execute(select(table.c.id).where(table.c.evento_id == event_id)).first()
                    if not exists:
                        conn.execute(table.insert().values(
                            evento_id=event_id, criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
                            usuario_nome='Sistema', metodo='SYSTEM', path='/processo-interno',
                            tipo_evento='DEPLOY_OBSERVADO', resultado='OBSERVADO', status_code=0,
                            objeto_tipo='release', objeto_id=sha, detalhes={'release_sha': sha},
                        ))
                state['recorded'] = True
            except IntegrityError:
                # Another worker observed this same immutable revision first.
                state['recorded'] = True
            except SQLAlchemyError:
                # A missing migration or temporary DB outage must not break requests.
                app.logger.warning('Não foi possível registrar a versão observada; será tentado novamente.')
