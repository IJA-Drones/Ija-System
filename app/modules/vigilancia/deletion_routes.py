"""Revisão e confirmação de exclusão restritas a Dev, Admin e COVISA."""

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.modules.auditoria.recorder import event_values
from app.shared.csrf_security import CSRF_SESSION_KEY
from .access import can_delete_field
from .deletion import DeletionStore
from .field_routes import _access, _scope, _municipality_filter_context
from .field_store import FieldConflict, FieldStoreError
from .planning import text
from .routes import _ensure_preview_csrf_token, _validate_preview_csrf, _RequestError


def register_routes(bp):
    @bp.app_context_processor
    def deletion_controls():
        return {'vigilancia_can_delete': (request.endpoint or '').startswith('main.vigilancia_') and
                can_delete_field(current_user)}

    @bp.route('/vigilancia/excluir', methods=['GET', 'POST'], endpoint='vigilancia_excluir')
    @_access
    def delete():
        if not can_delete_field(current_user):
            abort(403)
        prefeitura = _scope()
        if prefeitura is None:
            abort(400)
        _ensure_preview_csrf_token()
        values = request.form if request.method == 'POST' else request.args
        try:
            mode = text(values, 'demo', 5)
            if mode not in {'true', 'false'}:
                raise FieldConflict('Selecione demonstração ou dados autorizados.')
            demo = mode == 'true'
            kind, code = text(values, 'tipo', 20), text(values, 'codigo')
            origin = text(values, 'origem', 10, optional=True)
            store = DeletionStore()
            if request.method == 'POST':
                _validate_preview_csrf()
                if text(values, 'confirmacao', 3) != 'sim':
                    raise FieldConflict('Confirme a exclusão após revisar os dados.')
                uid = str(current_user.get_id())
                actor = dict(usuario_id=int(uid) if uid.isdecimal() else None,
                    usuario_nome=(getattr(current_user, 'nome_uvis', None) or uid)[:100],
                    usuario_login=getattr(current_user, 'login', None),
                    tipo_usuario=current_user.tipo_usuario, prefeitura_usuario_id=getattr(current_user, 'prefeitura_id', None))
                audit = event_values('EXCLUSAO', 'CONFIRMADO', actor=actor)
                store.delete(prefeitura, demo, kind, code, origin, text(values, 'revisao', 64), audit)
                flash('Exclusão concluída. Os resultados e mapas passam a considerar os registros restantes.', 'success')
                return redirect(url_for('main.vigilancia_campo' if kind == 'visita' else 'main.vigilancia_planejamento',
                    prefeitura_id=prefeitura, demo=mode, _anchor='resultados-campo' if kind == 'visita' else
                    'territorio' if kind == 'quarteirao' else 'levantamentos'), code=303)
            item = store.preview(prefeitura, demo, kind, code, origin)
            return render_template('vigilancia_excluir.html', item=item, prefeitura_id=prefeitura, demo=demo,
                **_municipality_filter_context(prefeitura), preview_csrf_token=session[CSRF_SESSION_KEY])
        except _RequestError as exc:
            abort(exc.status_code, description=str(exc))
        except FieldConflict as exc:
            abort(409, description=str(exc))
        except FieldStoreError as exc:
            abort(503, description=str(exc))
