from app.modules.gestao_ti.permissions import route_access
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Prefeitura
from app.modules.estoque.exporters import XLSX_MIME, build_estoque_excel
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
from app.shared.access import normalize_role, is_admin_global_user


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
