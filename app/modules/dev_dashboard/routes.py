import hmac
import os

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.modules.dev_dashboard.service import (
    build_dev_dashboard_context,
    build_dev_dashboard_payload,
    get_dev_error_detail,
    record_watchdog_deploy_event,
    run_manual_check,
)
from app.shared.access import is_dev_user


def register_routes(bp):
    def require_dev_user():
        if not is_dev_user(current_user):
            abort(403)

    def require_watchdog_token():
        expected = current_app.config.get("WATCHDOG_EVENT_TOKEN") or os.getenv("WATCHDOG_EVENT_TOKEN")
        supplied = (
            request.headers.get("X-Watchdog-Token")
            or (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        )
        if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
            abort(403)

    @bp.route("/api/watchdog/deploy-events", methods=["POST"], endpoint="watchdog_deploy_event")
    def watchdog_deploy_event():
        require_watchdog_token()
        payload = request.get_json(silent=True) or {}
        try:
            event, error = record_watchdog_deploy_event(payload)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Payload do watchdog invalido."}), 400
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Falha ao registrar evento de deploy do watchdog.")
            return jsonify({"success": False, "error": "Falha ao registrar evento."}), 500
        if error:
            return jsonify({"success": False, "error": error}), 400
        return jsonify({"success": True, "event_id": event.event_id})

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
