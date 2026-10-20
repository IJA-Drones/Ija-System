"""Mapa de risco municipal: arquivos agregados, análise e histórico auditável."""
import json
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Response, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user

from app.models import Prefeitura
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import is_admin_global_user
from .access import can_coordinate_field
from .field_routes import _scope
from .field_store import FieldStoreError
from .routes import _RequestError, _ensure_preview_csrf_token, _validate_preview_csrf
from .risk import MAX_BYTES, RiskError, analyze, example_files, csv_export, LABELS
from .risk_store import RiskStore
from .results import ResultsStore, filters_from, municipality_ibge
from .field_capture import FieldInputError
from .service import PreviewValidationError
from .territory import pernambuco_context
from .sample import build_geolocated_sample_csv


def _access(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False):
            abort(404)
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not can_coordinate_field(current_user) or not route_access(current_user, True):
            abort(403)
        return view(*args, **kwargs)
    return guarded


def _mode():
    values = request.form if request.method == "POST" else request.args
    if any(len(values.getlist(key)) != 1 for key in values):
        raise RiskError("Informe um único valor por campo.")
    mode = values.get("demo", "true" if request.method == "GET" else "")
    if mode not in {"true", "false"}:
        raise RiskError("Selecione demonstração ou dados autorizados.")
    if request.method == "POST" and request.args.getlist("demo") and request.args.getlist("demo") != [mode]:
        raise RiskError("O tipo de dado da URL difere do formulário.")
    return mode == "true"


def _file(name, extension):
    uploads=request.files.getlist(name)
    if len(uploads) != 1 or not uploads[0].filename.lower().endswith(extension):
        raise RiskError(f"Selecione um arquivo {extension} no campo {name}.")
    content=uploads[0].stream.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES:
        raise RiskError("Os arquivos juntos devem ter até 1 MiB.")
    return content


def register_routes(bp):
    @bp.after_request
    def risk_no_cache(response):
        if (request.endpoint or "").startswith("main.vigilancia_risco"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/vigilancia/risco", methods=["GET","POST"], endpoint="vigilancia_risco")
    @_access
    def risk_page():
        prefeitura=_scope()
        demo, selected, history, error, status = True, None, [], None, 200
        layer = request.args.get("camada", "historico" if request.method == "POST" or request.args.get("analise") else "liraa")
        field_report, field_filters = None, filters_from({"origem": "LIRAA"})
        ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
        try:
            demo=_mode()
            if layer not in {"liraa", "historico"}:
                raise RiskError("Selecione levantamento LIRAa ou histórico de casos.")
            if layer == "liraa":
                if not can_access_endpoint(current_user,"main.vigilancia_resultados","GET",legacy=True):
                    abort(403)
                field_filters = filters_from({name: request.args.get(name, "")
                    for name in ("levantamento", "estrato", "area", "bairro", "inicio", "fim")} | {"origem": "LIRAA"})
                if prefeitura:
                    field_report = ResultsStore().report(prefeitura, demo, field_filters, auto_single_survey=True)
                    field_filters = field_report["filtros"]
            if request.method == "POST":
                _validate_preview_csrf()
                if prefeitura is None:
                    abort(400)
                action=request.form.get("acao")
                if action == "exemplo":
                    if not demo:
                        raise RiskError("A demonstração só pode ser criada na opção de dados fictícios.")
                    geo, cases = example_files()
                    source="Demonstração · limites municipais reais do IBGE e casos fictícios"
                elif action == "analisar":
                    if request.form.get("conferido") != "sim":
                        raise RiskError("Confirme a origem e a cobertura dos arquivos antes da análise.")
                    geo, cases = _file("territorio", ".geojson"), _file("historico", ".csv")
                    source=request.form.get("fonte", "")
                else:
                    raise RiskError("Ação inválida.")
                identifier=RiskStore().save(analyze(geo,cases),prefeitura=prefeitura,demo=demo,actor=current_user.get_id(),fonte=source)
                return redirect(url_for("main.vigilancia_risco",prefeitura_id=prefeitura,demo="true" if demo else "false",camada="historico",analise=identifier),code=303)
            if prefeitura and layer == "historico":
                store=RiskStore()
                history=store.history(prefeitura,demo)
                identifier=request.args.get("analise") or (history[0]["id"] if history else None)
                if identifier:
                    selected=store.get(identifier,prefeitura,demo)
                    if not selected:
                        abort(404)
        except (_RequestError, RiskError, FieldInputError, PreviewValidationError) as exc:
            error, status = str(exc), getattr(exc,"status_code",400)
        except FieldStoreError:
            error, status = "O histórico de risco está indisponível. Confira a conexão e a migração do mapa de risco.", 503
        registered=Prefeitura.query.filter_by(id=prefeitura).first() if prefeitura else None
        global_user=is_admin_global_user(current_user)
        territory_context = pernambuco_context(ibge)
        context_codes = {feature['properties']['codigo'] for feature in territory_context['features']}
        history_context = territory_context if selected and all(
            feature['properties']['codigo'] in context_codes for feature in selected['report']['geografia']['features']) else None
        return render_template("vigilancia_risco.html",prefeitura_id=prefeitura,prefeitura_nome=registered.nome if registered else "",
            prefeituras=Prefeitura.query.order_by(Prefeitura.nome).all() if global_user else [],global_user=global_user,
            demo=demo, selected=selected, history=history, erro=error, csrf=_ensure_preview_csrf_token(), labels=LABELS,
            can_write=can_access_endpoint(current_user,"main.vigilancia_risco","POST",legacy=True),
            can_export=can_access_endpoint(current_user,"main.vigilancia_risco_export","GET",legacy=True),
            camada=layer, field_report=field_report, field_filters=field_filters,
            territorial_context=territory_context, territorial_ibge=ibge, history_context=history_context,
            criado=datetime.fromtimestamp(selected["criado"],ZoneInfo("America/Sao_Paulo")) if selected else None),status

    @bp.get("/vigilancia/risco/modelo/<kind>", endpoint="vigilancia_risco_modelo")
    @_access
    def risk_model(kind):
        if kind == "liraa":
            prefeitura = _scope()
            if not prefeitura:
                abort(400)
            try:
                if not _mode():
                    raise RiskError("Use a opção de demonstração para baixar dados fictícios.")
                ibge = municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)
                content = build_geolocated_sample_csv(prefeitura, ibge, datetime.now(ZoneInfo("America/Sao_Paulo")).date())
            except (RiskError, ValueError) as exc:
                abort(400, description=str(exc))
            return Response(content, mimetype="text/csv", headers={"Content-Disposition":
                f'attachment; filename="liraa-demo-geolocalizado-prefeitura-{prefeitura}.csv"'})
        if kind not in {"territorio", "historico"}:
            abort(404)
        geo,cases=example_files()
        return Response(geo if kind=="territorio" else cases,
            mimetype="application/geo+json" if kind=="territorio" else "text/csv",
            headers={"Content-Disposition":f'attachment; filename="risco-exemplo-ficticio.{"geojson" if kind=="territorio" else "csv"}"'})

    @bp.get("/vigilancia/risco/<identifier>/exportar", endpoint="vigilancia_risco_export")
    @_access
    def risk_export(identifier):
        prefeitura=_scope()
        if not prefeitura:
            abort(400)
        try:
            demo=_mode()
            saved=RiskStore().get(identifier,prefeitura,demo)
            if not saved:
                abort(404)
            report=saved["report"]
            fmt=request.args.get("formato","json")
            if fmt == "csv":
                if report["status"] != "CALCULADO":
                    raise RiskError("Histórico incompleto: baixe o relatório JSON para revisar os dados.")
                content,mime=csv_export(report),"text/csv"
            elif fmt == "json":
                content,mime=json.dumps(saved,ensure_ascii=False,allow_nan=False),"application/json"
            elif fmt == "geojson":
                features=[]
                for feature in report["geografia"]["features"]:
                    code=feature["properties"]["codigo"]
                    props={**feature["properties"],"recorrencia":next(r for r in report["recorrencia"] if r["codigo"]==code),"anual":[r for r in report["anual"] if r["codigo"]==code]}
                    features.append({**feature,"properties":props})
                content=json.dumps({"type":"FeatureCollection","features":features,"metodo":report["metodo"],"status":report["status"],"prefeitura_id":prefeitura,"demo":demo,"fonte":saved["fonte"],"analise":identifier},ensure_ascii=False,allow_nan=False)
                mime="application/geo+json"
            else:
                raise RiskError("Formato inválido.")
        except RiskError as exc:
            abort(400, description=str(exc))
        except FieldStoreError:
            abort(503,description="Análise indisponível no banco de dados.")
        return Response(content,mimetype=mime,headers={"Content-Disposition":f'attachment; filename="risco-{identifier}.{fmt}"'})
