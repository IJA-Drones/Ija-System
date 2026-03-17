from flask import jsonify, render_template
from flask_login import current_user, login_required

from app.modules.backup.service import (
    get_backup_state,
    list_backups,
    start_daily_backup_scheduler,
    trigger_backup_async,
)


def register_routes(bp):
    @bp.record_once
    def _on_bp_load(state):
        start_daily_backup_scheduler()

    @bp.route("/backup", methods=["GET"], endpoint="backup_page")
    @login_required
    def backup_page():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            return (
                render_template(
                    "backup_aguarde.html",
                    codigo=403,
                    titulo="Acesso negado",
                    mensagem="Apenas administradores podem gerar backup do banco.",
                    is_error=True,
                ),
                403,
            )

        trigger_backup_async()

        return render_template(
            "backup_aguarde.html",
            codigo="Backup",
            titulo="Gerando backup do banco de dados",
            mensagem="Aguarde alguns segundos. Ao finalizar, voce podera ver a lista de backups gerados.",
            is_error=False,
        )

    @bp.route("/backup/status", methods=["GET"], endpoint="backup_status")
    @login_required
    def backup_status():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            return jsonify({"ok": False, "error": "forbidden"}), 403

        return jsonify(get_backup_state())

    @bp.route("/backups", methods=["GET"], endpoint="backups_list_page")
    @login_required
    def backups_list_page():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            return (
                render_template(
                    "backup_lista.html",
                    codigo=403,
                    titulo="Acesso negado",
                    mensagem="Apenas administradores podem visualizar os backups.",
                    backups=[],
                    is_error=True,
                ),
                403,
            )

        backups = list_backups()
        return render_template(
            "backup_lista.html",
            codigo="Backups",
            titulo="Backups do Banco",
            mensagem="Lista de backups gerados automaticamente (05:00) e manuais.",
            backups=backups,
            is_error=False,
        )
