from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.modules.piloto_checklists.service import (
    PilotoChecklistError,
    build_piloto_checklist_context,
    save_piloto_checklist,
)


def _require_piloto():
    if getattr(current_user, "tipo_usuario", None) != "piloto":
        abort(403)


def register_routes(bp):
    @bp.route("/piloto/checklists/semanais", methods=["GET", "POST"], endpoint="piloto_checklist_semanal")
    @login_required
    def piloto_checklist_semanal():
        _require_piloto()

        try:
            context = build_piloto_checklist_context(current_user, request.args)
        except PilotoChecklistError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error("Erro no carregamento dos checklists (GET): %s", exc)
            flash("Erro interno ao carregar dados do checklist. Tente novamente.", "danger")
            return redirect(url_for("main.piloto_os"))

        if request.method == "POST":
            try:
                result = save_piloto_checklist(current_user, request.form)
                if result["pendencias_semanais"]:
                    flash(
                        "Checklist salvo com pendencias: " + " | ".join(result["pendencias_semanais"]),
                        "warning",
                    )
                flash("Checklist semanal salvo com sucesso.", "success")
                return redirect(
                    url_for(
                        "main.piloto_checklist_semanal",
                        veiculo_id=result["veiculo_id"],
                        drone_id=result["drone_id"],
                    )
                )
            except PilotoChecklistError as exc:
                flash(str(exc), exc.category)
                return redirect(url_for(exc.redirect_endpoint))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao salvar checklist semanal.")
                flash("Erro interno ao salvar o checklist. Tente novamente.", "danger")

                try:
                    context = build_piloto_checklist_context(current_user, request.args)
                except Exception:
                    return redirect(url_for("main.piloto_os"))

        return render_template("piloto_checklist_semanal.html", **context)
