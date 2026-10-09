"""Prévia CSV autenticada, sem carga no banco nem chamadas externas."""

import secrets
from functools import wraps
from io import BytesIO

from flask import abort, current_app, jsonify, render_template, request, send_file, session
from flask_login import current_user

from app.shared.access import is_admin_global_user, is_prefeitura_admin_user
from app.shared.csrf_security import CSRF_SESSION_KEY

from .sample import build_sample_csv
from .service import (
    CSV_COLUMNS, LAYOUT_VERSION, MAX_FILE_BYTES, MAX_PREFEITURA_ID,
    PreviewValidationError, preview_csv,
)


PREVIEW_ENDPOINTS = {
    "vigilancia_validacao",
    "vigilancia_validacao_api",
    "vigilancia_modelo_csv",
}


class _RequestError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _is_api():
    return (request.endpoint or "").rsplit(".", 1)[-1] == "vigilancia_validacao_api"


def _access_failure(message, status_code):
    if _is_api():
        return jsonify(error=message), status_code
    abort(status_code, description=message)


def _preview_access_required(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_app.config.get("VIGILANCIA_PREVIEW_ENABLED", False):
            return _access_failure("Funcionalidade indisponível.", 404)
        if not current_user.is_authenticated:
            if _is_api():
                return jsonify(error="Autenticação necessária."), 401
            return current_app.login_manager.unauthorized()
        if not (is_admin_global_user(current_user) or is_prefeitura_admin_user(current_user)):
            return _access_failure("Acesso restrito à administração responsável.", 403)
        return view(*args, **kwargs)

    return guarded


def _positive_id(value):
    text = str(value or "").strip()
    if not text or len(text) > 10 or not text.isascii() or not text.isdecimal():
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if 0 < parsed <= MAX_PREFEITURA_ID else None


def _prefeitura_scope(*, required):
    # Validate every supplied value, including repeated/form+query parameters.
    # A municipal administrator can never replace their session's municipality.
    supplied = request.args.getlist("prefeitura_id") + request.form.getlist("prefeitura_id")
    if is_prefeitura_admin_user(current_user):
        own_id = _positive_id(getattr(current_user, "prefeitura_id", None))
        if own_id is None:
            raise _RequestError("Usuário sem prefeitura vinculada.", 403)
        if any(_positive_id(value) != own_id for value in supplied):
            raise _RequestError("A prefeitura informada não pertence ao seu acesso.", 403)
        return own_id

    if not supplied and not required:
        return None
    parsed_ids = [_positive_id(value) for value in supplied]
    if not parsed_ids or None in parsed_ids or len(set(parsed_ids)) != 1:
        raise _RequestError("Informe um ID de prefeitura único entre 1 e 2147483647.")
    return parsed_ids[0]


def _ensure_preview_csrf_token():
    # Reuse the shared session key so global CSRF accepts the same form token.
    # Generate it on GET even when global CSRF is off; never rotate another flow.
    token = session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _validate_preview_csrf():
    expected = session.get(CSRF_SESSION_KEY)
    supplied = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("_csrf_token")
    )
    if (
        not isinstance(expected, str) or not expected
        or not isinstance(supplied, str)
        or not secrets.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))
    ):
        raise _RequestError("Recarregue a página de validação e tente novamente.", 403)


def _uploaded_csv():
    upload = request.files.get("arquivo")
    if upload is None or not upload.filename:
        raise _RequestError("Selecione um arquivo CSV para validar.")
    if not upload.filename.lower().endswith(".csv"):
        raise _RequestError("Envie um arquivo com extensão .csv.")
    content = upload.stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise _RequestError("O arquivo CSV ultrapassa o limite permitido.", 413)
    return content


def _render_preview(*, prefeitura_id, result=None, erro=None, status_code=200):
    return render_template(
        "vigilancia_validacao.html",
        result=result,
        erro=erro,
        prefeitura_id=prefeitura_id,
        municipio_editavel=is_admin_global_user(current_user),
        layout_version=LAYOUT_VERSION,
        csv_columns=CSV_COLUMNS,
        max_file_bytes=MAX_FILE_BYTES,
        preview_csrf_token=session.get(CSRF_SESSION_KEY, ""),
    ), status_code


def register_routes(bp):
    @bp.after_request
    def vigilancia_preview_no_cache(response):
        if (request.endpoint or "").rsplit(".", 1)[-1] in PREVIEW_ENDPOINTS:
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/vigilancia/validacao", methods=["GET", "POST"], endpoint="vigilancia_validacao")
    @_preview_access_required
    def vigilancia_validacao():
        try:
            prefeitura_id = _prefeitura_scope(required=request.method == "POST")
        except _RequestError as exc:
            return _access_failure(str(exc), exc.status_code)

        if request.method == "GET":
            _ensure_preview_csrf_token()
            return _render_preview(prefeitura_id=prefeitura_id)

        try:
            _validate_preview_csrf()
            result = preview_csv(_uploaded_csv(), prefeitura_id=prefeitura_id)
        except _RequestError as exc:
            return _render_preview(prefeitura_id=prefeitura_id, erro=str(exc), status_code=exc.status_code)
        except PreviewValidationError as exc:
            return _render_preview(prefeitura_id=prefeitura_id, erro=str(exc), status_code=400)
        return _render_preview(prefeitura_id=prefeitura_id, result=result)

    @bp.route("/api/vigilancia/validacao", methods=["POST"], endpoint="vigilancia_validacao_api")
    @_preview_access_required
    def vigilancia_validacao_api():
        try:
            prefeitura_id = _prefeitura_scope(required=True)
            _validate_preview_csrf()
            result = preview_csv(_uploaded_csv(), prefeitura_id=prefeitura_id)
        except _RequestError as exc:
            return jsonify(error=str(exc)), exc.status_code
        except PreviewValidationError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result)

    @bp.route("/vigilancia/modelo.csv", methods=["GET"], endpoint="vigilancia_modelo_csv")
    @_preview_access_required
    def vigilancia_modelo_csv():
        try:
            prefeitura_id = _prefeitura_scope(required=True)
        except _RequestError as exc:
            return _access_failure(str(exc), exc.status_code)
        return send_file(
            BytesIO(build_sample_csv(prefeitura_id)),
            mimetype="text/csv",
            as_attachment=True,
            download_name="vigilancia-exemplo-sintetico.csv",
            max_age=0,
        )
