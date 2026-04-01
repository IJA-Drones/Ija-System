from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.modules.auditoria.service import build_auditoria_filters, build_auditoria_query
from app.shared.access import normalize_role


def _admin_only():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) != "admin":
        abort(403)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def register_routes(bp):
    @bp.route("/admin/logs-usuarios", methods=["GET"], endpoint="admin_logs_usuarios")
    @login_required
    def admin_logs_usuarios():
        _admin_only()

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
