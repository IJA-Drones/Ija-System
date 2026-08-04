from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.clients.google_maps_client import geocode_endereco_google
from app.modules.mapas.service import (
    build_heatmap_points,
    build_uvis_disponiveis,
    get_consulta_geolocalizacao_key,
    get_mapa_relatorio_key,
)


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

            lat, lng, place_id = geocode_endereco_google(
                logradouro=logradouro,
                numero=numero,
                bairro=bairro,
                cidade=cidade,
                uf=uf,
                cep=cep,
            )

            if lat is None or lng is None:
                return jsonify({"ok": False, "message": "N\u00e3o foi poss\u00edvel geocodificar"}), 200

            return jsonify({"ok": True, "lat": lat, "lng": lng, "place_id": place_id}), 200
        except Exception as exc:
            current_app.logger.error("ERRO /api/geocode: %s", exc)
            return jsonify({"ok": False, "message": "Erro interno"}), 200

    @bp.route("/api/heatmap-data", endpoint="heatmap_data")
    @login_required
    def heatmap_data():
        pontos = build_heatmap_points(
            current_user,
            uvis_id=request.args.get("uvis_id", type=int),
            mes=request.args.get("mes", type=int),
            ano=request.args.get("ano", type=int),
        )
        return jsonify(pontos)

    @bp.route("/mapa-relatorio", endpoint="mapa_relatorio")
    @login_required
    def mapa_relatorio():
        google_maps_key = get_mapa_relatorio_key()
        if not google_maps_key:
            current_app.logger.warning(
                "Google Maps API Key nao encontrada (Maps_KEY_FRONT / KEY_API_GOOGLE_MAPS)."
            )

        return render_template(
            "mapa_relatorio.html",
            uvis_disponiveis=build_uvis_disponiveis(current_user),
            google_maps_key=google_maps_key,
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
