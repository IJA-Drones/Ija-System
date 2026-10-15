from app.modules.gestao_ti.permissions import route_access
from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.modules.auditoria.service import build_auditoria_filters, build_auditoria_query
from app.modules.auditoria.permissoes import build_permission_audit_context, can_view_permission_audit
from app.shared.access import is_dev_user


def _dev_only():
    if not route_access(current_user, is_dev_user(current_user)):
        abort(403)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def register_routes(bp):
    @bp.app_context_processor
    def inject_permission_audit_access():
        return {"can_view_permission_audit": can_view_permission_audit}

    @bp.after_request
    def protect_permission_audit_cache(response):
        if request.endpoint == "main.auditoria_permissoes":
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Pragma"] = "no-cache"
        return response

    @bp.route("/auditoria/permissoes", methods=["GET"], endpoint="auditoria_permissoes")
    @login_required
    def auditoria_permissoes():
        if not can_view_permission_audit(current_user):
            abort(403)
        return render_template("gestao_ti_auditoria.html", **build_permission_audit_context(request.args))

    @bp.route("/admin/logs-usuarios", methods=["GET"], endpoint="admin_logs_usuarios")
    @login_required
    def admin_logs_usuarios():
        _dev_only()

        filters = build_auditoria_filters(
            q=request.args.get("q"),
            metodo=request.args.get("metodo"),
            tipo_evento=request.args.get("tipo_evento"),
            status=request.args.get("status"),
            data_inicio=request.args.get("data_inicio"),
            data_fim=request.args.get("data_fim"),
        )

        page = max(1, request.args.get("page", 1, type=int) or 1)
        paginacao = build_auditoria_query(**filters).paginate(page=page, per_page=25, error_out=False)

        return render_template(
            "admin_logs_usuarios.html",
            logs=paginacao.items,
            paginacao=paginacao,
            filters=filters,
            pagination_args=_query_args_without_page(),
        )
