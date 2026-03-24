from flask import abort, flash, redirect, send_from_directory, url_for
from flask_login import current_user, login_required

from app.models import Solicitacao
from app.modules.anexos.service import (
    can_remove_attachment,
    can_view_attachment,
    remove_attachment,
    resolve_attachment_file,
)


def register_routes(bp):
    @bp.route("/solicitacao/<int:id>/anexo", endpoint="baixar_anexo")
    @bp.route("/admin/solicitacao/<int:id>/anexo", endpoint="baixar_anexo_admin")
    @login_required
    def baixar_anexo(id):
        pedido = Solicitacao.query.get_or_404(id)

        if not can_view_attachment(current_user, pedido):
            abort(403)

        try:
            upload_folder, rel, download_name = resolve_attachment_file(pedido)
        except FileNotFoundError:
            abort(404)

        return send_from_directory(
            upload_folder,
            rel,
            as_attachment=False,
            download_name=download_name,
        )

    @bp.route("/admin/solicitacao/<int:id>/remover_anexo", methods=["POST"], endpoint="remover_anexo")
    @login_required
    def remover_anexo(id):
        pedido = Solicitacao.query.get_or_404(id)
        if not can_remove_attachment(current_user, pedido):
            abort(403)

        remove_attachment(pedido)
        flash("PDF removido com sucesso!", "success")
        return redirect(url_for("main.dashboard"))
