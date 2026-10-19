"""Preparação e confirmação de cargas de campo com escopo municipal obrigatório."""

from functools import wraps
from io import BytesIO
from datetime import datetime, timezone
import uuid

from flask import Response, abort, current_app, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from werkzeug.wsgi import LimitedStream

from app.models import Prefeitura
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import is_admin_global_user
from app.shared.csrf_security import CSRF_SESSION_KEY
from .field_store import FieldConflict, FieldStore, FieldStoreError
from .routes import _RequestError, _positive_id, _ensure_preview_csrf_token, _validate_preview_csrf, _uploaded_csv
from .service import CSV_COLUMNS, LAYOUT_VERSION, MAX_FILE_BYTES, PreviewValidationError
from .sample import build_sample_csv
from .domain import DEPOSIT_TYPES
from .field_capture import FieldInputError, capture_csv, parse_filters, consolidate, export_csv
from . import os_capture
from .access import can_coordinate_field


class FieldBodyLimit:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if environ.get("REQUEST_METHOD") == "POST" and (path.startswith("/vigilancia/importacoes") or path in {"/vigilancia/campo", "/vigilancia/planejamento", "/vigilancia/agente", "/vigilancia/risco"}):
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
        legacy = can_coordinate_field(current_user)
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
        if (request.endpoint or "").startswith(("main.vigilancia_import", "main.vigilancia_campo", "main.vigilancia_planejamento")):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    def data_mode(values):
        supplied = values.getlist("demo")
        if len(supplied) > 1 or (not supplied and request.method == "POST") or (supplied and supplied[0] not in {"true", "false"}):
            raise FieldInputError("Selecione dados demonstrativos ou autorizados.")
        return not supplied or supplied[0] == "true"

    @bp.route("/vigilancia/campo", methods=["GET", "POST"], endpoint="vigilancia_campo")
    @_access
    def field_capture():
        prefeitura = _scope()
        _ensure_preview_csrf_token()
        filters = {key: "" for key in ("origem", "levantamento", "estrato", "inicio", "fim")}
        report = None
        error, code, demo, page_number = None, 200, True, 1
        form = request.form.to_dict() if request.method == "POST" else {}
        selected, os_context, plan_reference = None, None, None
        try:
            demo = data_mode(request.form if request.method == "POST" else request.args)
            from .planning import PlanningStore, text
            values = request.form if request.method == "POST" else request.args
            plan_code, block_code = text(values, "plano", optional=True), text(values, "quarteirao", optional=True)
            if plan_code or block_code:
                if not plan_code or not block_code or prefeitura is None:
                    raise FieldInputError("Informe levantamento e quarteirão da mesma prefeitura.")
                plan_reference = {"plano": plan_code, "quarteirao": block_code}
                planned = PlanningStore().visit_context(prefeitura, demo, plan_reference)
                if request.method == "GET":
                    form.update(planned)
            selected = os_capture.selected_os(request.form if request.method == "POST" else request.args, prefeitura)
            if selected:
                if demo:
                    raise FieldInputError("Para vincular uma OS, selecione dados autorizados da vigilância.")
                os_context = os_capture.context(selected)
                if request.method == "GET":
                    form.update(os_capture.prefill(selected))
                    if plan_reference:
                        form.update(planned)
            filters = parse_filters(request.args)
            raw_page = request.args.get("pagina", "1")
            if len(raw_page) > 2 or not raw_page.isascii() or not raw_page.isdecimal() or not 1 <= int(raw_page) <= 50:
                raise FieldInputError("Página inválida.")
            page_number = int(raw_page)
            if request.method == "POST":
                if prefeitura is None:
                    raise FieldInputError("Selecione uma prefeitura cadastrada.")
                _validate_preview_csrf()
                if not demo and request.form.get("autorizado") != "sim":
                    raise FieldInputError("Confirme a autorização para registrar dados reais.")
                content = capture_csv(request.form, prefeitura=prefeitura)
                declaration = os_capture.declaration(request.form, selected) if selected else None
                batch = _store().prepare(content, prefeitura=prefeitura, actor=str(current_user.get_id()),
                                         source=f"Registro de campo · OS #{selected.id}" if selected else "Registro direto de campo",
                                         filename="registro-campo.csv", demo=demo, os_declaration=declaration,
                                         plan_reference=plan_reference)
                return redirect(url_for("main.vigilancia_importacoes", prefeitura_id=prefeitura, lote=batch["id"]), code=303)
            if prefeitura:
                report = consolidate(_store().records(prefeitura, demo=demo), prefeitura=prefeitura, filters=filters)
        except _RequestError as exc:
            error, code = str(exc), exc.status_code
        except (FieldInputError, PreviewValidationError) as exc:
            error, code = str(exc), 400
        except FieldConflict as exc:
            error, code = str(exc), 409
        except FieldStoreError as exc:
            error, code = str(exc), 503
        query = {"prefeitura_id": prefeitura, "demo": "true" if demo else "false", **filters}
        rows = report["registros"] if report else []
        last_page = max(1, (len(rows) + 99) // 100)
        page_number = min(page_number, last_page)
        legacy = can_coordinate_field(current_user)
        return render_template("vigilancia_campo.html", prefeitura_id=prefeitura,
                               municipio_editavel=is_admin_global_user(current_user), demo=demo,
                               form=form, filters=filters, report=report, rows=rows[(page_number-1)*100:page_number*100],
                               page_number=page_number, last_page=last_page, erro=error, query=query,
                               deposit_types=DEPOSIT_TYPES, preview_csrf_token=session[CSRF_SESSION_KEY],
                               can_write=can_access_endpoint(current_user, "main.vigilancia_campo", "POST", legacy=legacy),
                               can_export=can_access_endpoint(current_user, "main.vigilancia_campo_export", "GET", legacy=legacy),
                               os_context=os_context,
                               plan_reference=plan_reference,
                               new_inspection="VIS-" + uuid.uuid4().hex[:16]), code

    @bp.get("/vigilancia/campo/exportar.csv", endpoint="vigilancia_campo_export")
    @_access
    def field_export():
        prefeitura = _scope()
        if prefeitura is None:
            abort(400)
        try:
            demo = data_mode(request.args)
            filters = parse_filters(request.args)
            report = consolidate(_store().records(prefeitura, demo=demo), prefeitura=prefeitura, filters=filters)
        except (FieldInputError, PreviewValidationError) as exc:
            abort(400, description=str(exc))
        except FieldStoreError as exc:
            abort(503, description=str(exc))
        return send_file(BytesIO(export_csv(report["registros"])), mimetype="text/csv",
                         as_attachment=True, download_name=f"campo-{'demonstracao' if demo else 'autorizado'}-{prefeitura}.csv", max_age=0)

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
                        pending = store.get(request.form.get("lote", ""), prefeitura)
                        if pending and pending["report"].get("vinculo_os"):
                            from werkzeug.datastructures import MultiDict
                            os_capture.selected_os(MultiDict({"os_id": str(pending["report"]["vinculo_os"]["id"])}), prefeitura)
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
