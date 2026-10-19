from app.modules.gestao_ti.permissions import route_access
from flask import abort, current_app, render_template, request
from flask_login import current_user, login_required

from app.modules.auditoria.service import build_auditoria_filters, build_auditoria_query
from app.shared.access import is_dev_user
from app.models import AuditoriaArquivo, Prefeitura
from app.modules.auditoria.archive import archive_status
from app.modules.auditoria.syslog import syslog_status
from app.shared.skybox import build_skybox_marker, stream_skybox_file, SkyboxError


def _dev_only():
    if not is_dev_user(current_user) or not route_access(current_user, True):
        abort(403)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def register_routes(bp):
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
            prefeitura_id=request.args.get("prefeitura_id"),
            resultado=request.args.get("resultado"),
        )

        page = max(1, request.args.get("page", 1, type=int) or 1)
        paginacao = build_auditoria_query(**filters).paginate(page=page, per_page=25, error_out=False)

        return render_template(
            "admin_logs_usuarios.html",
            logs=paginacao.items,
            paginacao=paginacao,
            filters=filters,
            pagination_args=_query_args_without_page(),
            prefeituras=Prefeitura.query.order_by(Prefeitura.nome).all(),
            skybox=archive_status(),
            syslog=syslog_status(),
            retention=current_app.config.get('AUDIT_RETENTION_MAX_RECORDS', 15000),
        )

    @bp.get('/admin/logs-usuarios/arquivo/<string:arquivo_id>', endpoint='admin_auditoria_arquivo')
    @login_required
    def admin_auditoria_arquivo(arquivo_id):
        _dev_only()
        row = AuditoriaArquivo.query.filter_by(id=arquivo_id).first_or_404()
        if not row.enviado_em:
            abort(409, description='O arquivo ainda está aguardando envio.')
        try:
            return stream_skybox_file(build_skybox_marker(row.caminho), as_attachment=True)
        except SkyboxError:
            abort(503, description='Arquivo temporariamente indisponível. Tente novamente.')
