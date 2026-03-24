from flask import abort, current_app, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.modules.agenda_notificacoes.service import (
    build_agenda_context,
    build_agenda_export,
    build_agenda_rotas_payload,
    can_export_agenda,
    clear_notificacoes,
    get_notificacao_or_404,
    list_notificacoes,
    mark_notificacao_as_read,
    soft_delete_notificacao,
)


def register_routes(bp):
    @bp.route("/agenda", endpoint="agenda")
    @login_required
    def agenda():
        try:
            return render_template("agenda.html", **build_agenda_context(current_user, request.args))
        except Exception as exc:
            current_app.logger.exception("Erro na agenda.")
            return f"ERRO NA AGENDA: {str(exc)}"

    @bp.route("/agenda/rotas-dia", endpoint="agenda_rotas_dia")
    @login_required
    def agenda_rotas_dia():
        try:
            return jsonify(build_agenda_rotas_payload(current_user, request.args))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            current_app.logger.exception("Erro ao montar rota do dia.")
            return jsonify(ok=False, error=str(exc)), 500

    @bp.route("/agenda/exportar_excel", endpoint="agenda_exportar_excel")
    @login_required
    def agenda_exportar_excel():
        if not can_export_agenda(current_user):
            abort(403)

        output, nome = build_agenda_export(current_user, request.args)
        return send_file(
            output,
            as_attachment=True,
            download_name=nome,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/notificacoes/<int:notif_id>/ler", endpoint="ler_notificacao")
    @login_required
    def ler_notificacao(notif_id):
        notificacao = get_notificacao_or_404(current_user, notif_id)
        mark_notificacao_as_read(notificacao)
        return redirect(notificacao.link or url_for("main.notificacoes"))

    @bp.route("/notificacoes", endpoint="notificacoes")
    @login_required
    def notificacoes():
        return render_template("notificacoes.html", itens=list_notificacoes(current_user))

    @bp.route("/notificacoes/<int:notif_id>/excluir", methods=["POST"], endpoint="excluir_notificacao")
    @login_required
    def excluir_notificacao(notif_id):
        notificacao = get_notificacao_or_404(current_user, notif_id)
        soft_delete_notificacao(notificacao)
        return redirect(url_for("main.notificacoes"))

    @bp.route("/notificacoes/limpar", methods=["POST"], endpoint="limpar_notificacoes")
    @login_required
    def limpar_notificacoes():
        clear_notificacoes(current_user)
        return redirect(url_for("main.notificacoes"))
