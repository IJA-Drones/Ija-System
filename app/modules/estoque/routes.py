from app.modules.gestao_ti.permissions import route_access
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Prefeitura
from app.modules.estoque.exporters import XLSX_MIME, build_estoque_excel
from app.modules.estoque.importacao import (
    create_preview, get_preview, preview_state, confirm_preview, preview_revision, update_preview_quantities,
)
from app.modules.estoque.service import (
    ESTOQUE_STATUS,
    build_peca_form,
    create_peca,
    delete_peca,
    get_peca_scoped_or_404,
    list_equipamentos_for_estoque,
    list_pecas,
    modelos_para_estoque,
    update_peca,
    validate_peca_form,
)
from app.shared.access import normalize_role, is_admin_global_user, can_access_prefeitura, get_user_prefeitura_id


def _require_estoque_access():
    if not route_access(current_user, normalize_role(getattr(current_user, 'tipo_usuario', None)) in {'dev', 'diretor', 'manutencao'}):
        abort(403)


def _render_peca_form(form, errors, peca=None):
    equipamentos = list_equipamentos_for_estoque(user=current_user)
    modelos = modelos_para_estoque(equipamentos, peca)
    prefeituras_query = Prefeitura.query
    if not is_admin_global_user(current_user):
        prefeituras_query = prefeituras_query.filter_by(id=current_user.prefeitura_id)
    prefeituras = prefeituras_query.order_by(Prefeitura.nome.asc()).all()
    modelo_prefeituras = {
        modelo: sorted({e.prefeitura_id for e in equipamentos if (e.modelo or '').strip().casefold() == modelo.casefold() and e.prefeitura_id is not None})
        for modelo in modelos
    }
    if peca is not None and peca.prefeitura_id is not None:
        legados = {m.strip().casefold() for m in (peca.modelos_compativeis or '').split(',') if m.strip()}
        for modelo in modelos:
            if modelo.casefold() in legados:
                modelo_prefeituras[modelo] = sorted(set(modelo_prefeituras[modelo]) | {peca.prefeitura_id})
    return render_template('estoque_form.html', form=form, errors=errors, peca=peca,
                           equipamentos=equipamentos, modelos=modelos, modelo_prefeituras=modelo_prefeituras,
                           prefeituras=prefeituras, can_choose_prefeitura=is_admin_global_user(current_user),
                           status_labels=ESTOQUE_STATUS)


def register_routes(bp):
    @bp.route("/estoque/importar/modelo", methods=["GET"], endpoint="estoque_importar_modelo")
    @login_required
    def estoque_importar_modelo():
        _require_estoque_access()
        from pathlib import Path
        path = Path(current_app.root_path) / "resources/estoque/modelo_importacao_pecas.xlsx"
        return send_file(path, mimetype=XLSX_MIME, as_attachment=True, download_name="modelo_importacao_pecas.xlsx")

    @bp.route("/estoque/importar", methods=["GET", "POST"], endpoint="estoque_importar")
    @login_required
    def estoque_importar():
        _require_estoque_access()
        prefeituras = [p for p in Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all()
                       if can_access_prefeitura(current_user, p.id)]
        selected = request.form.get("prefeitura_id") or get_user_prefeitura_id(current_user)
        errors = []
        if request.method == "POST":
            try:
                prefeitura_id = int(selected)
            except (TypeError, ValueError):
                prefeitura_id = None
                errors.append("Selecione a prefeitura do estoque antes de enviar a planilha.")
            if prefeitura_id is not None:
                if prefeitura_id not in {p.id for p in prefeituras}:
                    abort(403)
                try:
                    batch = create_preview(request.files.get("arquivo"), current_user, prefeitura_id)
                    return redirect(url_for("main.estoque_importar_previa", batch_id=batch.id))
                except ValueError as exc:
                    errors.append(str(exc))
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("Erro ao gerar a prévia de peças.")
                    errors.append("Não foi possível processar o arquivo. Confira se é um Excel .xlsx ou .xlsm válido e tente novamente.")
        return render_template("estoque_importar.html", prefeituras=prefeituras, selected=str(selected or ""),
                               errors=errors, can_choose_prefeitura=is_admin_global_user(current_user)), 400 if errors else 200

    @bp.route("/estoque/importar/<batch_id>", methods=["GET", "POST"], endpoint="estoque_importar_previa")
    @login_required
    def estoque_importar_previa(batch_id):
        _require_estoque_access()
        batch = get_preview(batch_id, current_user, lock=request.method == "POST")
        if batch.concluida_em:
            flash("Esta importação já foi concluída. As peças estão disponíveis no estoque.", "info")
            return redirect(url_for("main.estoque_listar"))
        if request.method == "POST":
            try:
                problems = update_preview_quantities(batch, current_user, request.form)
                for problem in problems:
                    flash(problem, "warning")
                if not problems:
                    flash("Quantidades revisadas. Confira a validação antes de confirmar a importação.", "info")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao revisar quantidades da importação.")
                flash("Não foi possível revisar as quantidades. Nenhuma peça foi cadastrada.", "warning")
            return redirect(url_for("main.estoque_importar_previa", batch_id=batch.id))
        rows, problems = preview_state(batch, current_user)
        invalid = sum(bool(row['erros']) for row in rows)
        return render_template("estoque_importar_previa.html", batch=batch, prefeitura=db.session.get(Prefeitura, batch.prefeitura_id),
                               rows=rows, problems=problems, invalid=invalid,
                               units=sum(row['cleaned']['quantidade'] or 0 for row in rows if not row['erros']),
                               can_confirm=not invalid and not problems, revision=preview_revision(batch))

    @bp.route("/estoque/importar/<batch_id>/confirmar", methods=["POST"], endpoint="estoque_importar_confirmar")
    @login_required
    def estoque_importar_confirmar(batch_id):
        _require_estoque_access()
        batch = get_preview(batch_id, current_user, lock=True)
        try:
            if request.form.get("preview_revision", preview_revision(batch)) != preview_revision(batch):
                flash("A prévia mudou em outra aba. Confira as quantidades atuais antes de confirmar.", "warning")
                return redirect(url_for("main.estoque_importar_previa", batch_id=batch.id))
            if not batch.concluida_em and any(
                f"quantidade_{index}" in request.form and request.form[f"quantidade_{index}"].strip() != source['dados'].get('quantidade', '')
                for index, source in enumerate(batch.linhas)
            ):
                problems = update_preview_quantities(batch, current_user, request.form)
                for problem in problems:
                    flash(problem, "warning")
                if not problems:
                    flash("Quantidades revisadas. Confira a prévia e confirme novamente para cadastrar o lote.", "info")
                return redirect(url_for("main.estoque_importar_previa", batch_id=batch.id))
            success, problems = confirm_preview(batch, current_user)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao confirmar importação de peças.")
            success, problems = False, ["Não foi possível concluir a importação. Nenhuma peça deste envio foi salva."]
        if success:
            flash(f"Importação concluída: {len(batch.linhas)} peça(s) cadastrada(s) no estoque.", "success")
            return redirect(url_for("main.estoque_listar"))
        db.session.rollback()
        for problem in problems:
            flash(problem, "warning")
        return redirect(url_for("main.estoque_importar_previa", batch_id=batch.id))

    @bp.route("/estoque", methods=["GET"], endpoint="estoque_listar")
    @login_required
    def estoque_listar():
        _require_estoque_access()
        local = request.args.get("local", "")
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip()
        todos = list_pecas(user=current_user)
        resumo = dict(itens=len(todos), unidades=sum(p.quantidade for p in todos),
                      disponiveis=sum(p.quantidade for p in todos if p.status == "disponivel_manutencao"),
                      sem_saldo=sum(p.quantidade == 0 for p in todos))
        pecas = list_pecas(user=current_user, local=local, q=q, status=status)
        return render_template("estoque_listar.html", pecas=pecas, local=local, q=q, status=status,
                               resumo=resumo, status_labels=ESTOQUE_STATUS)

    @bp.route("/estoque/export/excel", methods=["GET"], endpoint="estoque_export_excel")
    @login_required
    def estoque_export_excel():
        _require_estoque_access()
        output, filename = build_estoque_excel(list_pecas(user=current_user))
        return send_file(output, mimetype=XLSX_MIME, as_attachment=True, download_name=filename)

    @bp.route("/estoque/novo", methods=["GET", "POST"], endpoint="estoque_novo")
    @login_required
    def estoque_novo():
        _require_estoque_access()
        errors = {}
        form = {"status": "disponivel_manutencao", "quantidade": "1", "prefeitura_id": str(current_user.prefeitura_id or "")}

        if request.method == "POST":
            form, cleaned, errors = validate_peca_form(request.form, user=current_user)
            if errors:
                flash("Corrija os campos destacados.", "warning")
                return _render_peca_form(form, errors)
            try:
                create_peca(cleaned, prefeitura_id=getattr(current_user, "prefeitura_id", None))
                flash("Peca cadastrada no estoque com sucesso.", "success")
                return redirect(url_for("main.estoque_listar"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar peca no estoque.")
                flash("Erro interno ao cadastrar a peca.", "danger")

        return _render_peca_form(form, errors)

    @bp.route("/estoque/<int:peca_id>/editar", methods=["GET", "POST"], endpoint="estoque_editar")
    @login_required
    def estoque_editar(peca_id):
        _require_estoque_access()
        peca = get_peca_scoped_or_404(peca_id, current_user)
        errors = {}

        if request.method == "POST":
            form, cleaned, errors = validate_peca_form(request.form, existing_peca=peca, user=current_user)
            if errors:
                flash("Corrija os campos destacados.", "warning")
                return _render_peca_form(form, errors, peca)
            try:
                update_peca(peca, cleaned)
                flash("Peca atualizada com sucesso.", "success")
                return redirect(url_for("main.estoque_listar"))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao atualizar peca %s.", peca.id)
                flash("Erro interno ao atualizar a peca.", "danger")

        return _render_peca_form(build_peca_form(peca), errors, peca)

    @bp.route("/estoque/<int:peca_id>/deletar", methods=["POST"], endpoint="estoque_deletar")
    @login_required
    def estoque_deletar(peca_id):
        _require_estoque_access()
        peca = get_peca_scoped_or_404(peca_id, current_user)
        try:
            delete_peca(peca)
            flash("Peca removida do estoque.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover peca %s.", peca.id)
            flash("Erro ao remover a peca.", "danger")
        return redirect(url_for("main.estoque_listar"))
