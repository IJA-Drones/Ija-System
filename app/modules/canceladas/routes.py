from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Solicitacao
from app.modules.canceladas.service import build_canceladas_query
from app.shared.access import is_admin_global_user


def register_routes(bp):
    @bp.post("/solicitacao/<int:id>/cancelar", endpoint="cancelar_solicitacao")
    @login_required
    def cancelar_solicitacao(id):
        solicitacao = Solicitacao.query.get_or_404(id)

        if not is_admin_global_user(current_user) and solicitacao.usuario_id != current_user.id:
            abort(403)

        solicitacao.status = "CANCELADO"
        db.session.commit()

        flash("Solicitacao cancelada.", "success")
        return redirect(request.referrer or url_for("main.dashboard"))

    @bp.route("/canceladas", endpoint="solicitacoes_canceladas")
    @login_required
    def solicitacoes_canceladas():
        if current_user.tipo_usuario in {"piloto", "equipe_oceano"}:
            return redirect(url_for("main.piloto_os"))

        page = request.args.get("page", 1, type=int)
        paginacao = build_canceladas_query(current_user).paginate(page=page, per_page=6, error_out=False)

        return render_template(
            "dashboard_canceladas.html",
            solicitacoes=paginacao.items,
            paginacao=paginacao,
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )
