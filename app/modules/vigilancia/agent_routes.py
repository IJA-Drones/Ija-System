"""Acesso individual de agente, restrito aos quarteirões atribuídos."""

import uuid

from flask import abort, current_app, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.models import Prefeitura
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.shared.csrf_security import CSRF_SESSION_KEY
from .planning import PlanningStore, text
from .field_routes import _scope
from .field_capture import capture_csv, FieldInputError
from .field_store import FieldConflict, FieldStoreError
from .routes import _ensure_preview_csrf_token, _validate_preview_csrf, _RequestError
from .domain import DEPOSIT_TYPES
from . import os_capture


def is_agent():
    return current_user.is_authenticated and current_user.tipo_usuario == "agente_endemias"


def register_routes(bp):
    @bp.before_app_request
    def agent_area():
        if is_agent() and (request.endpoint or "").startswith("main.") and request.endpoint not in {
            "main.vigilancia_agente", "main.vigilancia", "main.inicio"}:
            abort(403)

    @bp.route("/vigilancia/agente", methods=["GET", "POST"], endpoint="vigilancia_agente")
    def agent():
        if not current_app.config.get("VIGILANCIA_IMPORT_ENABLED", False):
            abort(404)
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not is_agent():
            abort(403)
        if not can_access_endpoint(current_user, "main.vigilancia_agente", "GET", legacy=True) or not can_access_endpoint(
            current_user, "main.vigilancia_agente", request.method, legacy=True):
            abort(403)
        prefeitura = _scope()
        if not Prefeitura.query.filter_by(id=prefeitura, ativa=True).first():
            abort(403)
        _ensure_preview_csrf_token()
        values = request.form if request.method == "POST" else request.args
        demo, error, status = False, None, 200
        blocks, selected, batch, form, os_reference = [], None, None, {}, None
        store = PlanningStore()
        can_write = can_access_endpoint(current_user, "main.vigilancia_agente", "POST", legacy=True)
        try:
            supplied = values.getlist("demo")
            if len(supplied) > 1 or (supplied and supplied[0] not in {"true", "false"}):
                raise FieldConflict("Origem de dados inválida.")
            demo = supplied == ["true"]
            blocks = store.agent_blocks(prefeitura, current_user.id, demo)
            plan, block = text(values, "plano", optional=True), text(values, "quarteirao", optional=True)
            if plan or block:
                selected = next((row for row in blocks if row["plano"] == plan and row["quarteirao"] == block), None)
                if selected is None:
                    abort(404)
            if request.method == "GET":
                os_ids = values.getlist("os_id")
                use_location = values.getlist("usar_localizacao")
                if len(use_location) > 1 or (use_location and use_location[0] not in {"true", "false"}):
                    raise FieldConflict("Confirme uma única opção para usar o endereço da OS.")
                if os_ids and os_ids != [""]:
                    if not selected:
                        raise FieldConflict("Selecione um quarteirão atribuído antes de consultar uma OS.")
                    if demo:
                        raise FieldConflict("A consulta de OS só está disponível para dados autorizados.")
                    os_reference = os_capture.selected_agent_address(values, prefeitura,
                        bairro=selected["territorio"]["bairro"])
                    if use_location == ["true"]:
                        if not os_reference["latitude"] or not os_reference["longitude"]:
                            raise FieldConflict("Esta OS não possui as duas coordenadas necessárias para preencher a localização.")
                        form.update(latitude=os_reference["latitude"], longitude=os_reference["longitude"],
                                    os_mesmo_endereco="sim")
                elif use_location == ["true"]:
                    raise FieldConflict("Consulte uma OS antes de usar seu endereço.")
            if request.method == "POST":
                _validate_preview_csrf()
                action = text(values, "acao")
                if action == "confirmar":
                    batch = store.get(text(values, "lote", 32), prefeitura)
                    if not batch or batch["actor"] != str(current_user.id) or batch["demo"] != demo or batch["report"].get("planejamento", {}).get("agente_id") != current_user.id:
                        abort(404)
                    batch = store.confirm(batch["id"], prefeitura=prefeitura, actor=str(current_user.id))
                elif action == "registrar":
                    if not selected:
                        raise FieldConflict("Selecione um quarteirão atribuído antes de registrar a visita.")
                    if request.form.getlist("amostra_liraa") != ["sim"]:
                        raise FieldConflict("Confirme a participação do imóvel na seleção deste quarteirão.")
                    if any(len(request.form.getlist(name)) != 1 for name in request.form):
                        raise FieldConflict("Informe um único valor por campo da visita.")
                    # O território é obtido do plano, nunca de campos ocultos enviados pelo navegador.
                    form = request.form.to_dict()
                    os_reference = os_capture.selected_agent_address(request.form, prefeitura,
                        bairro=selected["territorio"]["bairro"])
                    same_address = request.form.getlist("os_mesmo_endereco")
                    if same_address not in ([], ["sim"]):
                        raise FieldConflict("Confirme se a OS corresponde ao mesmo endereço.")
                    if same_address == ["sim"] and (not os_reference or demo):
                        raise FieldConflict("Consulte uma OS da mesma prefeitura para usar seu endereço.")
                    if same_address == ["sim"] and not form.get("latitude") and not form.get("longitude"):
                        if os_reference["latitude"] and os_reference["longitude"]:
                            form.update(latitude=os_reference["latitude"], longitude=os_reference["longitude"])
                    form.update(origem="LIRAA", levantamento_codigo=selected["plano"], estrato_codigo=selected["estrato"],
                                area_codigo=selected["territorio"]["area"], bairro=selected["territorio"]["bairro"])
                    content = capture_csv(form, prefeitura=prefeitura)
                    batch = store.prepare(content, prefeitura=prefeitura, actor=str(current_user.id),
                        source="Registro individual de agente", filename="visita-agente.csv", demo=demo,
                        plan_reference=dict(plano=selected["plano"], quarteirao=selected["quarteirao"], agente_id=current_user.id))
                else:
                    raise FieldConflict("Ação inválida.")
                return redirect(url_for("main.vigilancia_agente", demo="true" if demo else "false", lote=batch["id"]), code=303)
            if values.get("lote"):
                batch = store.get(text(values, "lote", 32), prefeitura)
                if not batch or batch["actor"] != str(current_user.id) or batch["demo"] != demo or batch["report"].get("planejamento", {}).get("agente_id") != current_user.id:
                    abort(404)
        except _RequestError as exc:
            error, status = str(exc), exc.status_code
        except (FieldConflict, FieldInputError) as exc:
            error, status = str(exc), 400
        except FieldStoreError as exc:
            error, status = str(exc), 503
        response = render_template("vigilancia_agente.html", blocks=blocks, selected=selected, batch=batch,
            form=form, demo=demo, erro=error, can_write=can_write, deposit_types=DEPOSIT_TYPES,
            os_reference=os_reference, os_id_value=values.get("os_id", ""),
            preview_csrf_token=session[CSRF_SESSION_KEY], new_inspection="VIS-" + uuid.uuid4().hex[:16])
        return response, status, {"Cache-Control": "private, no-store"}
