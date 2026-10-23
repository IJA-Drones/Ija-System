"""Tela Vigilância → Migração de dados (TR 4.7): assistente em três etapas."""

import os
from datetime import datetime, timezone
from io import BytesIO

from flask import abort, current_app, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.modules.gestao_ti.permissions import can_access_endpoint
from app.shared.csrf_security import CSRF_SESSION_KEY
from . import migracao as mig
from . import sinan
from .access import can_coordinate_field
from .field_routes import _access, _municipality_filter_context, _scope
from .field_store import FieldConflict, FieldStoreError
from .results import municipality_ibge
from .routes import _RequestError, _ensure_preview_csrf_token, _validate_preview_csrf
from .sinan_store import StoreError

PAGE_SIZE = 50
VIEWS = {
    "problemas": ("Rejeitados e duplicados", {"REJEITADO", "DUPLICADO"}),
    "correcoes": ("Correções", {"CORRIGIDO"}),
    "padronizacoes": ("Padronizações", {"PADRONIZADO"}),
    "enriquecimentos": ("Enriquecimentos", {"ENRIQUECIDO"}),
}
FILES = {"original": "original", "extraido": "extraido", "adequado": "adequado", "relatorio": "relatorio"}


def _ibge(prefeitura):
    return municipality_ibge(current_app.config.get("VIGILANCIA_MUNICIPIOS_IBGE", {}), prefeitura)


def _maps_key():
    return (current_app.config.get("Maps_KEY_BACK") or os.getenv("GOOGLE_MAPS_KEY_BACK")
            or current_app.config.get("KEY_API_GOOGLE_MAPS") or os.getenv("KEY_API_GOOGLE_MAPS"))


def _geocoder(ibge, fallback_city):
    city = sinan.MUNICIPALITIES_BY_IBGE.get(ibge or "", {})
    name, uf = city.get("name", fallback_city).split(" (")[0], city.get("uf", "")

    def geocode(address):
        from app.clients.google_maps_client import geocode_endereco_google
        lat, lng, _ = geocode_endereco_google(logradouro=address, numero="", bairro="", cidade=name, uf=uf)
        return (float(lat), float(lng)) if lat is not None and lng is not None else None
    return geocode


def _options(destino, values, fonte):
    options = {"fonte": fonte, "geocodificar": values.get("geocodificar") == "sim"}
    if destino == "visitas":
        origem = values.get("origem_padrao", "LIRAA")
        if origem not in {"LIRAA", "FOCAL"}:
            raise mig.MigracaoError("Selecione a atividade padrão: LIRAa ou tratamento focal.")
        options.update(origem=origem, levantamento=mig._code(values.get("levantamento_padrao", ""))[:80],
                       estrato=mig._code(values.get("estrato_padrao", ""))[:80])
    elif destino == "sinan":
        doenca = values.get("doenca_padrao", "dengue")
        if doenca not in sinan.DISEASES:
            raise mig.MigracaoError("Selecione o agravo padrão.")
        options["doenca"] = doenca
    return options


def _sinan_store():
    from .sinan_workflow_routes import _owner, _store
    return _store(), _owner()


def register_routes(bp):
    @bp.after_request
    def migracao_no_cache(response):
        if (request.endpoint or "").startswith("main.vigilancia_migracao"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.route("/vigilancia/migracao", methods=["GET", "POST"], endpoint="vigilancia_migracao")
    @_access
    def migracao():
        prefeitura = _scope()
        _ensure_preview_csrf_token()
        store = mig.MigracaoStore()
        error, status, item, history = None, 200, None, []
        values = request.form if request.method == "POST" else request.args
        demo = values.get("demo", "true") != "false"
        try:
            if request.method == "POST":
                if prefeitura is None:
                    raise _RequestError("Selecione uma prefeitura cadastrada.")
                _validate_preview_csrf()
                action = request.form.get("acao")
                actor = str(current_user.get_id())
                if action == "extrair":
                    if request.form.get("demo") not in {"true", "false"}:
                        raise _RequestError("Identifique a origem demonstrativa ou autorizada dos dados.")
                    if not demo and request.form.get("autorizado") != "sim":
                        raise _RequestError("Confirme a autorização para migrar dados reais.")
                    upload = request.files.get("arquivo")
                    if upload is None or not upload.filename:
                        raise _RequestError("Selecione o arquivo exportado do sistema legado.")
                    content = upload.stream.read(mig.MAX_BYTES + 1)
                    identifier = store.create(prefeitura=prefeitura, demo=demo, actor=actor,
                                              destino=request.form.get("destino", ""), fonte=request.form.get("fonte", ""),
                                              filename=secure_filename(upload.filename) or "arquivo", content=content)
                    return redirect(url_for("main.vigilancia_migracao", prefeitura_id=prefeitura, id=identifier), code=303)
                item = store.get(request.form.get("id", ""), prefeitura)
                if item is None:
                    abort(404)
                if action == "validar":
                    if item["etapa"] == "CONCLUIDO":
                        raise FieldConflict("Esta migração já foi carregada. Inicie uma nova execução para alterar o mapeamento.")
                    header, _ = mig.read_extracted(item["extraido"])
                    mapping = mig.parse_mapping(item["destino"], header, request.form)
                    options = _options(item["destino"], request.form, item["fonte"])
                    ctx = store.context(item["destino"], prefeitura, item["demo"])
                    ibge = _ibge(prefeitura)
                    if item["destino"] == "sinan" and not ibge:
                        raise mig.MigracaoError("Configure o código IBGE desta prefeitura (VIGILANCIA_MUNICIPIOS_IBGE) para migrar casos do SINAN.")
                    ctx.update(prefeitura=prefeitura, ibge=ibge, demo=item["demo"])
                    if options["geocodificar"] and _maps_key():
                        ctx["geocode"] = _geocoder(ibge, _municipality_filter_context(prefeitura)["prefeitura_nome"])
                    report, adequado = mig.validate(item["destino"], item["extraido"], mapping, options, ctx)
                    store.save(item["id"], prefeitura, etapa="VALIDADO", relatorio=report, adequado=adequado,
                               mapeamento={"colunas": mapping, "opcoes": options}, resultado=None)
                elif action == "carregar":
                    if item["etapa"] == "EXTRAIDO":
                        raise FieldConflict("Valide os dados antes de confirmar a carga.")
                    if item["etapa"] == "VALIDADO":
                        sinan_store, owner = _sinan_store() if item["destino"] == "sinan" else (None, None)
                        result = mig.load(item, actor=actor, sinan_store=sinan_store, owner=owner)
                        store.save(item["id"], prefeitura, etapa="CONCLUIDO", resultado=result)
                else:
                    raise _RequestError("Ação inválida.")
                return redirect(url_for("main.vigilancia_migracao", prefeitura_id=prefeitura, id=item["id"]), code=303)
            if prefeitura and request.args.get("id"):
                item = store.get(request.args["id"], prefeitura)
                if item is None:
                    abort(404)
        except _RequestError as exc:
            error, status = str(exc), exc.status_code
        except mig.MigracaoError as exc:
            error, status = str(exc), 400
        except FieldConflict as exc:
            error, status = str(exc), 409
        except (FieldStoreError, StoreError) as exc:
            error, status = str(exc), 503
        if prefeitura:
            try:
                history = store.history(prefeitura)
                if item is None and request.form.get("id"):
                    item = store.get(request.form["id"], prefeitura)
            except FieldStoreError as exc:
                error, status = error or str(exc), status if error else 503
        if item:
            demo = item["demo"]
        view = request.args.get("ver", "problemas")
        view = view if view in VIEWS else "problemas"
        report = (item or {}).get("relatorio") or {}
        listed = [o for o in report.get("ocorrencias", []) if o["tipo"] in VIEWS[view][1]]
        pages = max(1, (len(listed) + PAGE_SIZE - 1) // PAGE_SIZE)
        raw_page = request.args.get("pagina", "1")
        page = min(int(raw_page), pages) if raw_page.isascii() and raw_page.isdecimal() and 0 < len(raw_page) < 6 and int(raw_page) > 0 else 1
        header, preview = mig.read_extracted(item["extraido"]) if item else ([], [])
        mapping = ((item or {}).get("mapeamento") or {})
        legacy = can_coordinate_field(current_user)
        return render_template(
            "vigilancia_migracao.html", prefeitura_id=prefeitura, **_municipality_filter_context(prefeitura),
            demo=demo, erro=error, item=item, history=history, destinos=mig.DESTINOS, targets=mig.TARGETS,
            header=header, preview=preview[:5], mapping=mapping.get("colunas", {}), options=mapping.get("opcoes", {}),
            report=report, view=view, views=VIEWS, listed=listed[(page - 1) * PAGE_SIZE:page * PAGE_SIZE],
            listed_total=len(listed), page=page, pages=pages, diseases=sinan.DISEASES, ibge=_ibge(prefeitura),
            geocode_available=bool(_maps_key()), preview_csrf_token=session[CSRF_SESSION_KEY],
            can_write=can_access_endpoint(current_user, "main.vigilancia_migracao", "POST", legacy=legacy),
            field_datetime=lambda value: datetime.fromtimestamp(value, timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        ), status

    @bp.get("/vigilancia/migracao/<identifier>/<kind>", endpoint="vigilancia_migracao_arquivo")
    @_access
    def migracao_arquivo(identifier, kind):
        prefeitura = _scope()
        if prefeitura is None or kind not in FILES:
            abort(404)
        store = mig.MigracaoStore()
        try:
            item = store.get(identifier, prefeitura)
            if item is None:
                abort(404)
            if kind == "relatorio":
                if not item["relatorio"]:
                    abort(404)
                content, name = mig.report_csv(item["relatorio"]), f"migracao-{identifier[:12]}-relatorio.csv"
            else:
                content = store.file(identifier, prefeitura, FILES[kind])
                if content is None:
                    abort(404)
                extension = os.path.splitext(item["filename"])[1] if kind == "original" else ".csv"
                name = f"migracao-{identifier[:12]}-{kind}{extension}"
        except FieldStoreError as exc:
            abort(503, description=str(exc))
        return send_file(BytesIO(content), mimetype="application/octet-stream" if kind == "original" else "text/csv",
                         as_attachment=True, download_name=name, max_age=0)

    @bp.get("/vigilancia/migracao/exemplo/<destino>", endpoint="vigilancia_migracao_exemplo")
    @_access
    def migracao_exemplo(destino):
        if destino not in mig.DESTINOS:
            abort(404)
        content, name, mimetype = mig.sample_file(destino, _ibge(_scope()))
        return send_file(BytesIO(content), mimetype=mimetype, as_attachment=True, download_name=name, max_age=0)
