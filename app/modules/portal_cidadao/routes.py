import re

from flask import current_app, jsonify, render_template, request

from app.clients.cep_client import CepLookupError, CepNotFoundError, lookup_cep
from app.clients.google_maps_client import reverse_geocode_lat_lng_google_details
from app.modules.portal_cidadao.health_news import get_portal_health_news
from app.modules.portal_cidadao.service import DenunciaValidationError, criar_denuncia
from app.shared.solicitacao_focos import build_focus_catalog


def register_routes(bp):
    @bp.route("/portal-cidadao", methods=["GET"], endpoint="portal_cidadao")
    def portal_cidadao():
        return render_template(
            "portal_cidadao.html",
            focus_catalog=build_focus_catalog(),
            health_news=get_portal_health_news(logger=current_app.logger),
        )

    @bp.route("/portal-cidadao/denuncias", methods=["POST"], endpoint="portal_cidadao_denuncias_criar")
    def portal_cidadao_denuncias_criar():
        try:
            denuncia = criar_denuncia(
                request.form,
                request.files,
                ip_origem=_resolve_request_ip(),
                user_agent=(request.headers.get("User-Agent") or "").strip() or None,
            )
        except DenunciaValidationError as exc:
            return jsonify({
                "success": False,
                "errors": exc.errors,
            }), 400

        return jsonify({
            "success": True,
            "protocolo": denuncia.protocolo,
            "denuncia_id": denuncia.id,
            "message": "Denuncia registrada com sucesso.",
        }), 201

    @bp.route("/portal-cidadao/cep/<cep>", methods=["GET"], endpoint="portal_cidadao_cep")
    def portal_cidadao_cep(cep):
        cep_digits = re.sub(r"\D", "", cep or "")
        if len(cep_digits) != 8:
            return jsonify({"ok": False, "error": "CEP invalido. Use 8 digitos."}), 400

        try:
            payload = lookup_cep(cep_digits, logger=current_app.logger)
        except CepNotFoundError:
            return jsonify({"ok": False, "error": "CEP nao encontrado."}), 404
        except CepLookupError:
            return jsonify({"ok": False, "error": "Falha ao consultar o servico de CEP."}), 502

        return jsonify({
            "ok": True,
            "cep": payload.get("cep", ""),
            "logradouro": payload.get("logradouro", ""),
            "complemento": payload.get("complemento", ""),
            "bairro": payload.get("bairro", ""),
            "cidade": payload.get("cidade", ""),
            "uf": payload.get("uf", ""),
        }), 200

    @bp.route("/portal-cidadao/reverse-geocode", methods=["POST"], endpoint="portal_cidadao_reverse_geocode")
    def portal_cidadao_reverse_geocode():
        data = request.get_json(silent=True) or {}
        lat = (data.get("latitude") or data.get("lat") or "").strip()
        lng = (data.get("longitude") or data.get("lng") or "").strip()

        if not _valid_coordinate(lat, -90, 90) or not _valid_coordinate(lng, -180, 180):
            return jsonify({"ok": False, "error": "Localizacao invalida."}), 400

        try:
            payload = reverse_geocode_lat_lng_google_details(lat=lat, lng=lng)
        except Exception:
            current_app.logger.exception("Falha reverse geocode portal cidadao.")
            return jsonify({"ok": False, "error": "Nao foi possivel resolver sua localizacao."}), 502

        if not payload:
            return jsonify({"ok": False, "error": "Endereco nao encontrado para a localizacao."}), 404

        return jsonify({"ok": True, **payload}), 200


def _resolve_request_ip():
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    return (request.headers.get("X-Real-IP") or "").strip() or request.remote_addr


def _valid_coordinate(value, minimum, maximum):
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return minimum <= numeric <= maximum
