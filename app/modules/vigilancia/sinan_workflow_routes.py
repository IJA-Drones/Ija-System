"""Same-screen import, history, map data and small snapshot CSV exports."""

import secrets
from functools import wraps
from pathlib import Path

from flask import Response, current_app, jsonify, request, session
from flask_login import current_user
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.wsgi import LimitedStream

from app.shared.csrf_security import CSRF_SESSION_KEY
from . import sinan, sinan_import
from .sinan_store import BusyError, Store, StoreError


def token():
    if not isinstance(session.get(CSRF_SESSION_KEY), str) or not session[CSRF_SESSION_KEY]:
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


def _store():
    backend = current_app.config.get("SINAN_STORAGE_BACKEND", "auto")
    if backend not in {"auto", "database", "sqlite"}:
        raise StoreError("Configuração de armazenamento SINAN inválida.")
    if backend == "database" or (backend == "auto" and "sqlalchemy" in current_app.extensions):
        from app.extensions import db
        from .sinan_database import DatabaseStore
        return DatabaseStore(db.engine)
    try:
        return Store(current_app.config.get("SINAN_STORAGE_PATH") or Path(current_app.instance_path) / "sinan" / "sinan.sqlite")
    except OSError as exc:
        raise StoreError("O armazenamento SINAN não está disponível. A consulta pública continua disponível.") from exc


def _owner():
    # Kept private to the importing account, including municipal administrators.
    return f"{getattr(current_user, 'prefeitura_id', None)}:{current_user.get_id()}"


def _scope(values):
    if hasattr(values, "getlist") and any(len(values.getlist(k)) != 1 for k in values):
        raise ValueError("Parâmetros repetidos.")
    return sinan_import.validate_scope(values)


def _compact(job):
    if job:
        job["summary"].pop("groups", None)
    return job


class SinanBodyLimit:
    """Bound multipart input before CSRF or any other middleware parses a form.

    Flask 3.0 has no per-request max_content_length setter. Do not change the
    global configuration: other modules legitimately upload much larger files.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ.get("REQUEST_METHOD") == "POST" and environ.get("PATH_INFO", "").startswith("/api/vigilancia/sinan/"):
            limit = sinan_import.MAX_BYTES + 65536
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > limit or (not length and environ.get("wsgi.input_terminated")):
                return Response('{"error":"Envie um arquivo de até 1 MiB com tamanho informado."}', status=413, content_type="application/json; charset=utf-8", headers={"Cache-Control": "private, no-store"})(environ, start_response)
            environ["wsgi.input"] = LimitedStream(environ["wsgi.input"], limit, is_max=True)
        return self.app(environ, start_response)


def _job(store, job_id):
    job = store.get(job_id, _owner())
    if not job:
        from flask import abort
        abort(404)
    return job


def _guard(view):
    from .sinan_routes import _access_required

    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_app.config.get("SINAN_IMPORT_ENABLED", True):
            return jsonify(error="Importações SINAN desabilitadas neste ambiente."), 404
        try:
            if request.method == "POST":
                expected, supplied = session.get(CSRF_SESSION_KEY), request.headers.get("X-CSRFToken", "")
                if not isinstance(expected, str) or not supplied or not secrets.compare_digest(expected.encode(), supplied.encode()):
                    return jsonify(error="Recarregue a tela SINAN e tente novamente."), 403
            return view(*args, **kwargs)
        except RequestEntityTooLarge:
            return jsonify(error="Envie um arquivo de até 1 MiB."), 413
        except BusyError as exc:
            return jsonify(error=str(exc)), 409
        except StoreError as exc:
            return jsonify(error=str(exc)), 503
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    return _access_required(guarded)


def register_routes(bp):
    @bp.record_once
    def install_body_limit(state):
        state.app.wsgi_app = SinanBodyLimit(state.app.wsgi_app)

    @bp.get("/api/vigilancia/sinan/importacoes", endpoint="vigilancia_sinan_jobs")
    @_guard
    def jobs():
        scope = _scope(request.args)
        result = _store().list(_owner(), **scope)
        result["jobs"] = [_compact(job) for job in result["jobs"]]
        return jsonify(result)

    @bp.post("/api/vigilancia/sinan/importacoes", endpoint="vigilancia_sinan_import")
    @_guard
    def import_api():
        values = request.get_json(silent=True)
        if not isinstance(values, dict) or set(values) - {"source"} != {"disease", "ibge", "year"}:
            raise ValueError("Informe doença, município e ano.")
        source = values.pop("source", "api")
        if source not in {"api", "datasus"}:
            raise ValueError("Origem inválida. Use a API do Ministério da Saúde ou o DATASUS.")
        scope, store = _scope(values), _store()
        job_id, _ = sinan_import.start(store, _owner(), scope, source=source)
        return jsonify(job=_compact(store.get(job_id, _owner()))), 202

    @bp.post("/api/vigilancia/sinan/casos", endpoint="vigilancia_sinan_cases_import")
    @_guard
    def import_cases():
        scope = _scope(request.form)
        if request.form.get("demo") not in {"true", "false"}:
            raise ValueError("Identifique o arquivo como demonstração ou dados autorizados.")
        if request.form.get("demo") == "false" and request.form.get("authorized") != "true":
            raise ValueError("Confirme que o arquivo contém dados autorizados para este acesso.")
        upload = request.files.get("file")
        if not upload or not upload.filename.lower().endswith(".csv"):
            raise ValueError("Selecione um arquivo CSV no modelo disponibilizado.")
        content = upload.stream.read(sinan_import.MAX_BYTES + 1)
        if len(content) > sinan_import.MAX_BYTES:
            return jsonify(error="Envie um arquivo de até 1 MiB."), 413
        store = _store()
        job_id, existing = sinan_import.start(store, _owner(), scope, content=content, demo=request.form["demo"] == "true")
        return jsonify(job=_compact(store.get(job_id, _owner())), existing=existing), 200 if existing else 202

    @bp.get("/api/vigilancia/sinan/importacoes/<job_id>", endpoint="vigilancia_sinan_job")
    @_guard
    def job(job_id):
        return jsonify(job=_compact(_job(_store(), job_id)))

    @bp.post("/api/vigilancia/sinan/importacoes/<job_id>/cancelar", endpoint="vigilancia_sinan_job_cancel")
    @_guard
    def cancel(job_id):
        store = _store()
        _job(store, job_id)
        store.cancel(job_id, _owner())
        return jsonify(job=_compact(store.get(job_id, _owner())))

    @bp.get("/api/vigilancia/sinan/importacoes/<job_id>/mapa", endpoint="vigilancia_sinan_job_map")
    @_guard
    def map_data(job_id):
        store = _store()
        job = _job(store, job_id)
        if job["status"] not in {"completed", "partial"}:
            return jsonify(error="Selecione um lote concluído ou parcial."), 409
        return jsonify(kind=job["kind"], demo=job["demo"], status=job["status"], count=job["count"],
                       municipality=sinan.MUNICIPALITIES_BY_IBGE[job["ibge"]],
                       points=store.cases(job_id, _owner()) if job["kind"] == "csv" else [])

    @bp.get("/api/vigilancia/sinan/importacoes/<job_id>/exportar.csv", endpoint="vigilancia_sinan_export")
    @_guard
    def export(job_id):
        store = _store()
        job = _job(store, job_id)
        if job["status"] not in {"completed", "partial"}:
            return jsonify(error="O lote ainda não está disponível para exportação."), 409
        cases = store.cases(job_id, _owner()) if job["kind"] == "csv" else ()
        # No database cursor/transaction is held while a slow client downloads.
        return Response(sinan_import.export_rows(job, cases), content_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="sinan-{job["disease"]}-{job["ibge"]}-{job["year"]}-{job["status"]}.csv"',
            "X-Content-Type-Options": "nosniff",
        })

    @bp.get("/api/vigilancia/sinan/modelo-casos.csv", endpoint="vigilancia_sinan_cases_sample")
    @_guard
    def sample():
        return Response(sinan_import.sample_csv(_scope(request.args)), content_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": 'attachment; filename="sinan-modelo-DEMONSTRACAO.csv"',
            "X-Content-Type-Options": "nosniff",
        })
