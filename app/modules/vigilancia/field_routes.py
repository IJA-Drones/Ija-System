"""Preparação e confirmação de cargas de campo com escopo municipal obrigatório."""

from functools import wraps
from io import BytesIO
from datetime import datetime, timezone

from flask import Response, abort, current_app, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from werkzeug.wsgi import LimitedStream

from app.models import Prefeitura
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import is_admin_global_user, is_prefeitura_admin_user
from app.shared.csrf_security import CSRF_SESSION_KEY
from .field_store import FieldConflict, FieldStore, FieldStoreError
from .routes import _RequestError, _positive_id, _ensure_preview_csrf_token, _validate_preview_csrf, _uploaded_csv
from .service import CSV_COLUMNS, LAYOUT_VERSION, MAX_FILE_BYTES, PreviewValidationError
from .sample import build_sample_csv


class FieldBodyLimit:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ.get("REQUEST_METHOD") == "POST" and environ.get("PATH_INFO", "").startswith("/vigilancia/importacoes"):
            limit = MAX_FILE_BYTES + 65536
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > limit or (not length and environ.get("wsgi.input_terminated")):
                return Response("Envie um arquivo de até 1 MiB com tamanho informado.", status=413,
                                headers={"Cache-Control": "private, no-store"})(environ, start_response)
            environ["wsgi.input"] = LimitedStream(environ["wsgi.input"], limit, is_max=True)
        return self.app(environ, start_response)


def _access(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False):
            abort(404)
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        legacy = is_admin_global_user(current_user) or is_prefeitura_admin_user(current_user)
        if not can_access_endpoint(current_user, "main.vigilancia_importacoes", "GET", legacy=legacy) or not route_access(current_user, legacy):
            abort(403)
        return view(*args, **kwargs)
    return guarded


def _scope():
    values = request.args.getlist("prefeitura_id") + request.form.getlist("prefeitura_id")
    if is_admin_global_user(current_user):
        if not values and request.method == "GET":
            return None
        parsed = [_positive_id(value) for value in values]
        if not parsed or None in parsed or len(set(parsed)) != 1:
            abort(400, description="Informe uma prefeitura única e válida.")
        prefeitura = parsed[0]
    else:
        prefeitura = _positive_id(getattr(current_user, "prefeitura_id", None))
        if prefeitura is None or any(_positive_id(value) != prefeitura for value in values):
            abort(403, description="A prefeitura não pertence ao seu acesso.")
    try:
        if Prefeitura.query.filter_by(id=prefeitura).first() is None:
            abort(400, description="Prefeitura não cadastrada no sistema.")
    except SQLAlchemyError:
        abort(503, description="Não foi possível conferir o cadastro da prefeitura.")
    return prefeitura


def _store():
    return FieldStore()


def register_routes(bp):
    @bp.record_once
    def install_field_body_limit(state):
        state.app.wsgi_app = FieldBodyLimit(state.app.wsgi_app)

    @bp.after_request
    def field_no_cache(response):
        if (request.endpoint or "").startswith("main.vigilancia_import"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/vigilancia/importacoes", methods=["GET", "POST"], endpoint="vigilancia_importacoes")
    @_access
    def imports():
        prefeitura = _scope()
        _ensure_preview_csrf_token()
        batch, error, code, history = None, None, 200, []
        try:
            if prefeitura:
                store = _store()
                if request.method == "POST":
                    _validate_preview_csrf()
                    if request.form.get("acao") == "confirmar":
                        batch = store.confirm(request.form.get("lote", ""), prefeitura=prefeitura, actor=str(current_user.get_id()))
                        return redirect(url_for("main.vigilancia_importacoes", prefeitura_id=prefeitura, lote=batch["id"]), code=303)
                    if request.form.get("acao") != "preparar":
                        raise _RequestError("Ação inválida.")
                    mode = request.form.get("demo")
                    if mode not in {"true", "false"}:
                        raise _RequestError("Identifique a origem demonstrativa ou autorizada do arquivo.")
                    if mode == "false" and request.form.get("autorizado") != "sim":
                        raise _RequestError("Confirme a autorização para utilizar dados reais.")
                    content = _uploaded_csv()
                    batch = store.prepare(content, prefeitura=prefeitura, actor=str(current_user.get_id()),
                                          source=request.form.get("fonte", ""),
                                          filename=secure_filename(request.files["arquivo"].filename)[:120], demo=mode == "true")
                    return redirect(url_for("main.vigilancia_importacoes", prefeitura_id=prefeitura, lote=batch["id"]), code=303)
                if request.args.get("lote"):
                    batch = store.get(request.args["lote"], prefeitura)
                    if batch is None:
                        abort(404)
                history = store.history(prefeitura)
        except _RequestError as exc:
            error, code = str(exc), exc.status_code
        except FieldConflict as exc:
            error, code = str(exc), 409
        except PreviewValidationError as exc:
            error, code = str(exc), 400
        except FieldStoreError as exc:
            error, code = str(exc), 503
        if error and prefeitura:
            try:
                history = _store().history(prefeitura)
                if request.form.get("acao") == "confirmar":
                    batch = _store().get(request.form.get("lote", ""), prefeitura)
            except (FieldStoreError, OSError):
                pass
        return render_template("vigilancia_validacao.html", field_mode=True, batch=batch, history=history,
                               result=batch["report"] if batch else None, erro=error,
                               prefeitura_id=prefeitura, municipio_editavel=is_admin_global_user(current_user),
                               layout_version=LAYOUT_VERSION, csv_columns=CSV_COLUMNS,
                               max_file_bytes=MAX_FILE_BYTES, preview_csrf_token=session[CSRF_SESSION_KEY],
                               field_datetime=lambda value: datetime.fromtimestamp(value, timezone.utc).strftime("%d/%m/%Y %H:%M UTC")), code

    @bp.get("/vigilancia/importacoes/<batch_id>/origem.csv", endpoint="vigilancia_import_origem")
    @_access
    def original(batch_id):
        prefeitura = _scope()
        if prefeitura is None:
            abort(400)
        try:
            content = _store().original(batch_id, prefeitura)
        except FieldStoreError as exc:
            abort(503, description=str(exc))
        if content is None:
            abort(404)
        return send_file(BytesIO(content), mimetype="text/csv", as_attachment=True,
                         download_name=f"vigilancia-origem-{batch_id}.csv", max_age=0)

    @bp.get("/vigilancia/importacoes/modelo.csv", endpoint="vigilancia_import_modelo")
    @_access
    def sample():
        prefeitura = _scope()
        if prefeitura is None:
            abort(400)
        return send_file(BytesIO(build_sample_csv(prefeitura)), mimetype="text/csv", as_attachment=True,
                         download_name="vigilancia-exemplo-sintetico.csv", max_age=0)
