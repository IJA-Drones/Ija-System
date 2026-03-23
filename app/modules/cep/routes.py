from flask import current_app, jsonify, request
from flask_login import login_required

from app.modules.cep.service import build_cep_by_address_response, build_cep_response


def register_routes(bp):
    @bp.route("/api/cep/<cep>", methods=["GET"], endpoint="api_cep")
    @login_required
    def api_cep(cep):
        payload, status_code = build_cep_response(
            cep,
            logger=current_app.logger,
            debug=current_app.debug,
        )
        return jsonify(payload), status_code

    @bp.route("/api/cep/busca-endereco", methods=["POST"], endpoint="api_cep_by_address")
    @login_required
    def api_cep_by_address():
        payload, status_code = build_cep_by_address_response(
            request.get_json(silent=True) or {},
            logger=current_app.logger,
            debug=current_app.debug,
        )
        return jsonify(payload), status_code
