"""Painel e exportação de indicadores, sem gravação ou importação automática."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Response, abort, current_app, render_template, request
from flask_login import current_user

from app.modules.gestao_ti.permissions import can_access_endpoint
from .access import can_coordinate_field
from .field_capture import FieldInputError
from .field_routes import _access, _scope, _municipality_filter_context
from .field_store import FieldStoreError
from .results import ResultsStore, filters_from, indicators_csv, municipality_ibge, schematic, sinan_filters, sinan_snapshot
from .service import PreviewValidationError
from .sinan_store import StoreError
from . import sinan
from .territory import pernambuco_context


def _mode():
    if any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise FieldInputError("Informe um único valor para cada filtro.")
    mode = request.args.get("demo", "true")
    if mode not in {"true", "false"}:
        raise FieldInputError("Selecione demonstração ou dados autorizados.")
    return mode == "true"


def _sinan(prefeitura, demo, selection):
    legacy = can_coordinate_field(current_user)
    data = dict(jobs=[], snapshot=None, municipality=None, warning=None, enabled=False)
    if not current_app.config.get("SINAN_ENABLED", True) or not current_app.config.get("SINAN_IMPORT_ENABLED", True):
        data["warning"] = "O SINAN está desabilitado neste ambiente."
        return data
    if not can_access_endpoint(current_user, "main.vigilancia_sinan_job_map", "GET", legacy=legacy):
        data["warning"] = "Seu acesso não permite consultar os lotes SINAN."
        return data
    ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
    if not ibge:
        data["warning"] = "A relação entre esta prefeitura e seu código IBGE precisa ser configurada para comparar os dados SINAN."
        return data
    data.update(municipality=sinan.MUNICIPALITIES_BY_IBGE[ibge], enabled=True)
    from .sinan_workflow_routes import _store, _owner
    try:
        store, owner = _store(), _owner()
        data["jobs"] = store.published(owner, ibge=ibge, year=selection["year"], disease=selection["disease"], demo=demo)
        selected = request.args.get("lote_sinan", "")
        if selected:
            job = next((job for job in data["jobs"] if job["id"] == selected), None)
            if not job:
                raise FieldInputError("Selecione um lote SINAN publicado do seu acesso, município, ano e origem dos dados.")
            data["snapshot"] = sinan_snapshot(store, owner, job, selection)
    except StoreError:
        data["warning"] = "Os lotes SINAN estão indisponíveis. Os resultados de campo continuam disponíveis."
    return data


def register_routes(bp):
    @bp.after_request
    def results_no_cache(response):
        if (request.endpoint or "").startswith("main.vigilancia_resultados"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.get("/vigilancia/resultados", endpoint="vigilancia_resultados")
    @_access
    def results():
        prefeitura = _scope()
        report, filters, selected_sinan, sinan_data = None, {}, {}, None
        demo, error, status = True, None, 200
        try:
            demo = _mode()
            filters, selected_sinan = filters_from(request.args), sinan_filters(request.args)
            if prefeitura:
                report = ResultsStore().report(prefeitura, demo, filters)
                sinan_data = _sinan(prefeitura, demo, selected_sinan)
        except (FieldInputError, PreviewValidationError) as exc:
            error, status, report = str(exc), 400, None
        except FieldStoreError as exc:
            error, status, report = str(exc), 503, None
        legacy = can_coordinate_field(current_user)
        ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
        return render_template("vigilancia_resultados.html", prefeitura_id=prefeitura,
            **_municipality_filter_context(prefeitura), demo=demo, report=report,
            filters=filters, sinan_data=sinan_data, sinan_filters=selected_sinan, diseases=sinan.DISEASES,
            query={"prefeitura_id": prefeitura, "demo": "true" if demo else "false", **filters},
            erro=error, generated_at=datetime.now(ZoneInfo("America/Sao_Paulo")),
            territorial_context=pernambuco_context(ibge), territorial_ibge=ibge,
            can_export=can_access_endpoint(current_user, "main.vigilancia_resultados_export", "GET", legacy=legacy),
            contornos=schematic(report["geografia"]) if report else []), status

    @bp.get("/vigilancia/resultados/exportar", endpoint="vigilancia_resultados_export")
    @_access
    def export():
        prefeitura = _scope()
        if not prefeitura:
            abort(400)
        try:
            demo, filters = _mode(), filters_from(request.args)
            report = ResultsStore().report(prefeitura, demo, filters)
            fmt = request.args.get("formato", "csv")
            if fmt == "csv":
                content, mime, extension = indicators_csv(report), "text/csv; charset=utf-8", "csv"
            elif fmt == "geojson":
                content = json.dumps({**report["geografia"], "prefeitura_id": prefeitura, "demo": demo,
                    "filtros": filters, "preliminar": True}, ensure_ascii=False, allow_nan=False)
                mime, extension = "application/geo+json", "geojson"
            else:
                raise FieldInputError("Selecione CSV ou GeoJSON para exportar.")
        except (FieldInputError, PreviewValidationError) as exc:
            abort(400, description=str(exc))
        except FieldStoreError as exc:
            abort(503, description=str(exc))
        return Response(content, content_type=mime, headers={"Content-Disposition":
            f'attachment; filename="liraa-{"demo" if demo else "autorizado"}-{prefeitura}.{extension}"',
            "X-Content-Type-Options": "nosniff"})
