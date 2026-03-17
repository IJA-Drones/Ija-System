from flask import current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.dashboard.service import build_dashboard_context


def register_routes(bp):
    @bp.route("/", endpoint="dashboard")
    @login_required
    def dashboard():
        google_maps_key = current_app.config.get("KEY_API_GOOGLE_MAPS")

        if current_user.tipo_usuario == "piloto":
            return redirect(url_for("main.piloto_os"))

        if current_user.tipo_usuario == "equipe_uvis":
            return redirect(url_for("main.dashboard_equipe_uvis"))

        if current_user.tipo_usuario in ["admin", "operario", "visualizar"]:
            return redirect(url_for("main.admin_dashboard"))

        context = build_dashboard_context(current_user, request.args, google_maps_key)
        return render_template("dashboard.html", **context)
