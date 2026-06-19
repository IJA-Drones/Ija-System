from flask import abort, jsonify, render_template
from flask_login import current_user, login_required

from app.modules.dev_dashboard.service import (
    build_dev_dashboard_context,
    build_dev_dashboard_payload,
    get_dev_error_detail,
    run_manual_check,
)
from app.shared.access import is_dev_user


def register_routes(bp):
    def require_dev_user():
        if not is_dev_user(current_user):
            abort(403)

    @bp.route("/dev", methods=["GET"], endpoint="dev_dashboard")
    @login_required
    def dev_dashboard():
        require_dev_user()
        return render_template("dev_dashboard.html", **build_dev_dashboard_context())

    @bp.route("/dev/data", methods=["GET"], endpoint="dev_dashboard_data")
    @login_required
    def dev_dashboard_data():
        require_dev_user()
        return jsonify(build_dev_dashboard_payload())

    @bp.route("/dev/errors/<int:log_id>", methods=["GET"], endpoint="dev_dashboard_error_detail")
    @login_required
    def dev_dashboard_error_detail(log_id):
        require_dev_user()
        detail = get_dev_error_detail(log_id)
        if detail is None:
            abort(404)
        return jsonify(detail)

    @bp.route("/dev/checks/<slug>", methods=["POST"], endpoint="dev_dashboard_manual_check")
    @login_required
    def dev_dashboard_manual_check(slug):
        require_dev_user()
        result = run_manual_check(slug)
        if result is None:
            abort(404)
        return jsonify(result)
