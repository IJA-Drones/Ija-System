from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.equipe_uvis_dashboard.service import (
    EquipeUvisDashboardError,
    build_dashboard_equipe_uvis_context,
)


def register_routes(bp):
    @bp.route("/equipe-uvis", methods=["GET"], endpoint="dashboard_equipe_uvis")
    @login_required
    def dashboard_equipe_uvis():
        if getattr(current_user, "tipo_usuario", None) != "equipe_uvis":
            return redirect(url_for("main.dashboard"))

        google_maps_key = current_app.config.get("KEY_API_GOOGLE_MAPS")

        try:
            context = build_dashboard_equipe_uvis_context(
                current_user,
                request.args,
                google_maps_key,
            )
        except EquipeUvisDashboardError as exc:
            flash(exc.message, exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        return render_template("dashboard_equipe_uvis.html", **context)
