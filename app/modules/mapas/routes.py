from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.clients.google_maps_client import geocode_endereco_google
from app.modules.mapas.service import (
    build_heatmap_points,
    build_uvis_disponiveis,
    get_consulta_geolocalizacao_key,
    get_mapa_relatorio_key,
    normalize_larva_filter,
)

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _optional_integer_filter(name, *, minimum, maximum=None):
    value = (request.args.get(name) or "").strip()
    if not value:
        return None
    if not value.isdecimal():
        raise ValueError(f"Filtro {name} inválido.")
    value = int(value)
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"Filtro {name} inválido.")
    return value


def register_routes(bp):
    @bp.route("/api/geocode", methods=["POST"], endpoint="api_geocode")
    @login_required
    def api_geocode():
        try:
            data = request.get_json(silent=True) or {}

            logradouro = (data.get("logradouro") or "").strip()
            numero = (data.get("numero") or "").strip()
            bairro = (data.get("bairro") or "").strip()
            cidade = (data.get("cidade") or "").strip()
            uf = (data.get("uf") or "").strip()
            cep = (data.get("cep") or "").strip()

            if not logradouro or not numero or not cidade or not uf:
                return jsonify({"ok": False, "message": "Endere\u00e7o incompleto"}), 200

            lat, lng = geocode_endereco_google(
                logradouro=logradouro,
                numero=numero,
                bairro=bairro,
                cidade=cidade,
                uf=uf,
                cep=cep,
            )

            if lat is None or lng is None:
                return jsonify({"ok": False, "message": "N\u00e3o foi poss\u00edvel geocodificar"}), 200

            return jsonify({"ok": True, "lat": lat, "lng": lng}), 200
        except Exception as exc:
            current_app.logger.error("ERRO /api/geocode: %s", exc)
            return jsonify({"ok": False, "message": "Erro interno"}), 200

    @bp.route("/api/heatmap-data", endpoint="heatmap_data")
    @login_required
    def heatmap_data():
        try:
            filters = {
                "uvis_id": _optional_integer_filter("uvis_id", minimum=1),
                "mes": _optional_integer_filter("mes", minimum=1, maximum=12),
                "ano": _optional_integer_filter("ano", minimum=1, maximum=9999),
                "larva_visualizada": normalize_larva_filter(request.args.get("larva_visualizada")),
            }
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        pontos = build_heatmap_points(
            current_user,
            **filters,
        )
        return jsonify(pontos)

    @bp.route("/mapa-relatorio", endpoint="mapa_relatorio")
    @login_required
    def mapa_relatorio():
        google_maps_key = get_mapa_relatorio_key()
        hoje_brasil = datetime.now(BRAZIL_TZ)
        if not google_maps_key:
            current_app.logger.warning(
                "Google Maps API Key nao encontrada (Maps_KEY_FRONT / KEY_API_GOOGLE_MAPS)."
            )

        return render_template(
            "mapa_relatorio.html",
            uvis_disponiveis=build_uvis_disponiveis(current_user),
            google_maps_key=google_maps_key,
            mes_atual=hoje_brasil.month,
            ano_atual=hoje_brasil.year,
        )

    @bp.route(
        "/consultar_endereco_geolocalizacao",
        methods=["GET"],
        endpoint="consultar_endereco_geolocalizacao",
    )
    @login_required
    def consultar_endereco_geolocalizacao():
        return render_template(
            "consultar_endereco_geolocalizacao.html",
            google_maps_key=get_consulta_geolocalizacao_key(),
        )
