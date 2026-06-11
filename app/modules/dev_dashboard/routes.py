from flask import abort, render_template
from flask_login import current_user, login_required

from app.modules.dev_dashboard.service import build_dev_dashboard_context
from app.shared.access import is_dev_user


def register_routes(bp):
    @bp.route("/dev", methods=["GET"], endpoint="dev_dashboard")
    @login_required
    def dev_dashboard():
        if not is_dev_user(current_user):
            abort(403)
        return render_template("dev_dashboard.html", **build_dev_dashboard_context())
