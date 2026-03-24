from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Solicitacao, Usuario
from app.modules.admin_uvis.service import (
    build_uvis_export,
    build_uvis_query,
    can_access_admin_uvis,
    delete_uvis_user,
    is_admin_user,
    is_uvis_user,
    validate_edit_uvis,
    validate_new_uvis,
)


def _admin_only_redirect():
    if not is_admin_user(current_user):
        flash("Voce nao tem permissao para acessar esta funcao.", "danger")
        return redirect(request.referrer or url_for("main.admin_uvis_listar"))
    return None


def register_routes(bp):
    @bp.route("/admin/uvis/novo", methods=["GET", "POST"], endpoint="admin_uvis_novo")
    @login_required
    def admin_uvis_novo():
        if not is_admin_user(current_user):
            abort(403)

        if request.method == "POST":
            nome_uvis = (request.form.get("nome_uvis") or "").strip()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor = (request.form.get("codigo_setor") or "").strip() or None
            login = (request.form.get("login") or "").strip()
            senha = request.form.get("senha") or ""
            confirmar = request.form.get("confirmar") or ""

            category, message = validate_new_uvis(nome_uvis, login, senha, confirmar)
            if message:
                flash(message, category)
                return render_template("admin_uvis_novo.html")

            novo_user = Usuario(
                nome_uvis=nome_uvis,
                regiao=regiao,
                codigo_setor=codigo_setor,
                login=login,
                tipo_usuario="uvis",
            )
            novo_user.set_senha(senha)

            try:
                db.session.add(novo_user)
                db.session.commit()
                flash("UVIS cadastrada com sucesso!", "success")
                return redirect(url_for("main.admin_uvis_listar"))
            except IntegrityError:
                db.session.rollback()
                flash("Esse login ja esta em uso. Escolha outro.", "danger")
            except Exception as exc:
                db.session.rollback()
                flash(f"Erro ao cadastrar UVIS: {exc}", "danger")

        return render_template("admin_uvis_novo.html")

    @bp.route("/admin/uvis", methods=["GET"], endpoint="admin_uvis_listar")
    @login_required
    def admin_uvis_listar():
        if not can_access_admin_uvis(current_user):
            abort(403)

        q = (request.args.get("q") or "").strip()
        regiao = (request.args.get("regiao") or "").strip()
        codigo_setor = (request.args.get("codigo_setor") or "").strip()
        page = request.args.get("page", 1, type=int)

        query = build_uvis_query(current_user, q, regiao, codigo_setor)
        total = query.count()
        paginacao = query.paginate(page=page, per_page=10, error_out=False)

        filters = {
            "q": q,
            "regiao": regiao,
            "codigo_setor": codigo_setor,
            "total": total,
        }

        return render_template(
            "admin_uvis_listar.html",
            uvis=paginacao.items,
            paginacao=paginacao,
            filters=filters,
            q=q,
            regiao=regiao,
            codigo_setor=codigo_setor,
            is_admin=is_admin_user(current_user),
        )

    @bp.route("/admin/uvis/<int:id>/editar", methods=["GET", "POST"], endpoint="admin_uvis_editar")
    @login_required
    def admin_uvis_editar(id):
        resp = _admin_only_redirect()
        if resp:
            return resp

        uvis = Usuario.query.get_or_404(id)
        if not is_uvis_user(uvis):
            flash("Registro invalido para edicao.", "danger")
            return redirect(url_for("main.admin_uvis_listar"))

        if request.method == "POST":
            nome_uvis = (request.form.get("nome_uvis") or "").strip()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor_field = request.form.get("codigo_setor")
            codigo_setor = (codigo_setor_field or "").strip() or None
            login = (request.form.get("login") or "").strip()
            senha = (request.form.get("senha") or "").strip()
            confirmar = (request.form.get("confirmar") or "").strip()

            category, message = validate_edit_uvis(
                nome_uvis=nome_uvis,
                login=login,
                senha=senha,
                confirmar=confirmar,
                uvis_id=uvis.id,
            )
            if message:
                flash(message, category)
                return render_template("admin_uvis_editar.html", uvis=uvis)

            uvis.nome_uvis = nome_uvis
            uvis.regiao = regiao
            if codigo_setor_field is not None:
                uvis.codigo_setor = codigo_setor
            uvis.login = login

            if senha:
                uvis.set_senha(senha)

            try:
                db.session.commit()
                flash("UVIS atualizada com sucesso!", "success")
                return redirect(url_for("main.admin_uvis_listar"))
            except IntegrityError:
                db.session.rollback()
                flash("Esse login ja esta em uso. Escolha outro.", "danger")
            except Exception as exc:
                db.session.rollback()
                flash(f"Erro ao salvar: {exc}", "danger")

        return render_template("admin_uvis_editar.html", uvis=uvis)

    @bp.route("/admin/uvis/<int:id>/excluir", methods=["POST"], endpoint="admin_uvis_excluir")
    @login_required
    def admin_uvis_excluir(id):
        resp = _admin_only_redirect()
        if resp:
            return resp

        uvis = Usuario.query.get_or_404(id)
        if not is_uvis_user(uvis):
            flash("Registro invalido para exclusao.", "danger")
            return redirect(url_for("main.admin_uvis_listar"))

        existe = Solicitacao.query.filter_by(usuario_id=uvis.id).first()
        if existe:
            flash("Nao e possivel excluir: esta UVIS possui solicitacoes vinculadas.", "warning")
            return redirect(url_for("main.admin_uvis_listar"))

        try:
            delete_uvis_user(uvis)
            db.session.commit()
            flash("UVIS excluida com sucesso!", "success")
        except IntegrityError:
            db.session.rollback()
            flash(
                "Nao foi possivel excluir a UVIS porque ainda existem registros vinculados a ela no sistema.",
                "danger",
            )
        except Exception:
            db.session.rollback()
            flash("Erro ao excluir UVIS.", "danger")

        return redirect(url_for("main.admin_uvis_listar"))

    @bp.route("/admin/uvis/exportar", methods=["GET"], endpoint="admin_uvis_exportar")
    @login_required
    def admin_uvis_exportar():
        if not can_access_admin_uvis(current_user):
            abort(403)

        q = (request.args.get("q") or "").strip()
        regiao = (request.args.get("regiao") or "").strip()
        codigo_setor = (request.args.get("codigo_setor") or "").strip()
        rows = build_uvis_query(current_user, q, regiao, codigo_setor).all()
        output, filename = build_uvis_export(rows)

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
