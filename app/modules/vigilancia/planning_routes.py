"""Cadastro territorial e planejamento com o acesso municipal já existente."""

import csv
import io

from flask import abort, redirect, render_template, request, session, url_for, Response
from flask_login import current_user

from app.modules.gestao_ti.permissions import can_access_endpoint
from app.shared.csrf_security import CSRF_SESSION_KEY
from .field_routes import _access, _scope, _municipality_filter_context
from .routes import _ensure_preview_csrf_token, _validate_preview_csrf, _uploaded_csv, _RequestError
from .field_store import FieldConflict, FieldStoreError
from .planning import PlanningStore, text, RG_COLUMNS, PLAN_COLUMNS
from .access import can_coordinate_field


def register_routes(bp):
    @bp.route("/vigilancia/planejamento", methods=["GET", "POST"], endpoint="vigilancia_planejamento")
    @_access
    def planning():
        prefeitura = _scope()
        _ensure_preview_csrf_token()
        values = request.form if request.method == "POST" else request.args
        demo, code, error, status, overview = True, "", None, 200, {}
        legacy = can_coordinate_field(current_user)
        try:
            supplied = values.getlist("demo")
            if len(supplied) > 1 or (request.method == "POST" and not supplied) or (supplied and supplied[0] not in {"true", "false"}):
                raise FieldConflict("Selecione demonstração ou dados autorizados.")
            demo = not supplied or supplied[0] == "true"
            code = text(values, "plano", optional=True)
            if request.method == "POST":
                _validate_preview_csrf()
                if not prefeitura:
                    raise FieldConflict("Selecione uma prefeitura cadastrada.")
                if not demo and request.form.get("autorizado") != "sim":
                    raise FieldConflict("Confirme a autorização para gravar dados reais.")
                action = text(values, "acao")
                content = _uploaded_csv() if action in {"importar_territorio", "importar_plano"} else None
                code = PlanningStore().mutate(prefeitura, demo, str(current_user.get_id()), action, values, content)
                block = text(values, "quarteirao", optional=True) if action == "territorio" else ""
                if action in {"territorio", "importar_territorio"}:
                    code = text(values, "retorno_plano", optional=True)
                target = "territorio" if action in {"territorio", "importar_territorio"} else "amostra" if code else "levantamentos"
                return redirect(url_for("main.vigilancia_planejamento", prefeitura_id=prefeitura,
                                        demo="true" if demo else "false", plano=code, territorio=block, _anchor=target), code=303)
            if prefeitura:
                overview = PlanningStore().overview(prefeitura, demo, code)
                if code and not overview["plano"]:
                    abort(404)
        except _RequestError as exc:
            error, status = str(exc), exc.status_code
        except FieldConflict as exc:
            error, status = str(exc), 400
        except FieldStoreError as exc:
            error, status = str(exc), 503
        if error and prefeitura:
            try:
                overview = PlanningStore().overview(prefeitura, demo, code)
            except FieldStoreError:
                pass
        map_data = [{name: row.get(name) for name in ("code", "bairro", "area", "imoveis", "referencia", "geometria", "atualizado_em")}
                    for row in overview.get("territorio", [])]
        for item in map_data:
            item["versao"] = str(item.pop("atualizado_em"))
        return render_template("vigilancia_planejamento.html", prefeitura_id=prefeitura,
            **_municipality_filter_context(prefeitura), demo=demo,
            preview_csrf_token=session[CSRF_SESSION_KEY], erro=error, overview=overview,
            form=values, map_data=map_data,
            territory_form=values if request.method == "POST" and values.get("acao") == "territorio" else {},
            can_write=can_access_endpoint(current_user, "main.vigilancia_planejamento", "POST", legacy=legacy)), status

    @bp.get("/vigilancia/planejamento/modelo/<kind>.csv", endpoint="vigilancia_planejamento_modelo")
    @_access
    def sample(kind):
        if kind not in {"territorio", "plano"}:
            abort(404)
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(RG_COLUMNS if kind == "territorio" else PLAN_COLUMNS)
        writer.writerow(["Q-001", "Bairro fictício", "A-01", 100, "RG de demonstração"] if kind == "territorio"
                        else ["E-01", 1000, 20, "Plano amostral de demonstração", "Q-001", 20, ""])
        return Response(stream.getvalue().encode("utf-8-sig"), mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="modelo-{kind}-liraa.csv"'})
