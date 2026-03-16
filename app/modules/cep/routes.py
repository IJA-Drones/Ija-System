from flask import current_app, jsonify
from flask_login import login_required

from app.modules.cep.service import build_cep_response


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
