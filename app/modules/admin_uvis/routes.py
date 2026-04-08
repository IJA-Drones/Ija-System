from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Prefeitura, Solicitacao, Usuario
from app.modules.admin_uvis.service import (
    build_uvis_export,
    build_uvis_query,
    can_access_admin_uvis,
    delete_uvis_user,
    is_admin_or_prefeitura_admin,
    is_admin_user,
    is_uvis_user,
    validate_edit_uvis,
    validate_new_uvis,
)


def _admin_only_redirect():
    if not is_admin_or_prefeitura_admin(current_user):
        flash("Voce nao tem permissao para acessar esta funcao.", "danger")
        return redirect(request.referrer or url_for("main.admin_uvis_listar"))
    return None


def _prefeituras_ativas():
    return Prefeitura.query.filter(Prefeitura.ativa.is_(True)).order_by(Prefeitura.nome.asc()).all()


def _resolve_prefeitura_uvis(prefeitura_id_form, atual_prefeitura_id=None):
    if getattr(current_user, "tipo_usuario", None) == "prefeitura_admin":
        return getattr(current_user, "prefeitura_id", None)
    return prefeitura_id_form or atual_prefeitura_id


def register_routes(bp):
    @bp.route("/admin/uvis/novo", methods=["GET", "POST"], endpoint="admin_uvis_novo")
    @login_required
    def admin_uvis_novo():
        if not is_admin_or_prefeitura_admin(current_user):
            abort(403)

        prefeituras = _prefeituras_ativas() if is_admin_user(current_user) else []
        form = {}

        if request.method == "POST":
            nome_uvis = (request.form.get("nome_uvis") or "").strip()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor = (request.form.get("codigo_setor") or "").strip() or None
            login = (request.form.get("login") or "").strip()
            senha = request.form.get("senha") or ""
            confirmar = request.form.get("confirmar") or ""
            prefeitura_id_form = request.form.get("prefeitura_id", type=int)
            prefeitura_id = _resolve_prefeitura_uvis(prefeitura_id_form)

            form = {
                "nome_uvis": nome_uvis,
                "regiao": regiao or "",
                "codigo_setor": codigo_setor or "",
                "login": login,
                "prefeitura_id": prefeitura_id_form or "",
            }

            if is_admin_user(current_user) and not prefeitura_id:
                flash("Selecione a prefeitura da UVIS.", "warning")
                return render_template("admin_uvis_novo.html", prefeituras=prefeituras, form=form)
            if not prefeitura_id:
                flash("Nao foi possivel identificar a prefeitura para essa UVIS.", "warning")
                return render_template("admin_uvis_novo.html", prefeituras=prefeituras, form=form)

            if prefeitura_id and not Prefeitura.query.filter(Prefeitura.id == prefeitura_id).first():
                flash("Prefeitura selecionada nao encontrada.", "warning")
                return render_template("admin_uvis_novo.html", prefeituras=prefeituras, form=form)

            category, message = validate_new_uvis(nome_uvis, login, senha, confirmar)
            if message:
                flash(message, category)
                return render_template("admin_uvis_novo.html", prefeituras=prefeituras, form=form)

            novo_user = Usuario(
                nome_uvis=nome_uvis,
                regiao=regiao,
                codigo_setor=codigo_setor,
                login=login,
                tipo_usuario="uvis",
                prefeitura_id=prefeitura_id,
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
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao cadastrar UVIS.")
                flash("Erro interno ao cadastrar a UVIS. Tente novamente.", "danger")

        return render_template("admin_uvis_novo.html", prefeituras=prefeituras, form=form)

    @bp.route("/admin/uvis", methods=["GET"], endpoint="admin_uvis_listar")
    @login_required
    def admin_uvis_listar():
        if not can_access_admin_uvis(current_user):
            abort(403)

        q = (request.args.get("q") or "").strip()
        regiao = (request.args.get("regiao") or "").strip()
        codigo_setor = (request.args.get("codigo_setor") or "").strip()
        prefeitura_id = request.args.get("prefeitura_id", type=int)
        page = request.args.get("page", 1, type=int)
        prefeituras = _prefeituras_ativas() if is_admin_user(current_user) else []

        query = build_uvis_query(
            current_user,
            q,
            regiao,
            codigo_setor,
            prefeitura_id=prefeitura_id,
        )
        total = query.count()
        paginacao = query.paginate(page=page, per_page=10, error_out=False)

        filters = {
            "q": q,
            "regiao": regiao,
            "codigo_setor": codigo_setor,
            "prefeitura_id": prefeitura_id or "",
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
            prefeitura_id=prefeitura_id,
            prefeituras=prefeituras,
            is_admin=is_admin_or_prefeitura_admin(current_user),
        )

    @bp.route("/admin/uvis/<int:id>/editar", methods=["GET", "POST"], endpoint="admin_uvis_editar")
    @login_required
    def admin_uvis_editar(id):
        resp = _admin_only_redirect()
        if resp:
            return resp

        uvis = build_uvis_query(current_user, "", "", "").filter(Usuario.id == id).first_or_404()
        if not is_uvis_user(uvis):
            flash("Registro invalido para edicao.", "danger")
            return redirect(url_for("main.admin_uvis_listar"))
        prefeituras = _prefeituras_ativas() if is_admin_user(current_user) else []
        form = {}

        if request.method == "POST":
            nome_uvis = (request.form.get("nome_uvis") or "").strip()
            regiao = (request.form.get("regiao") or "").strip() or None
            codigo_setor_field = request.form.get("codigo_setor")
            codigo_setor = (codigo_setor_field or "").strip() or None
            login = (request.form.get("login") or "").strip()
            senha = (request.form.get("senha") or "").strip()
            confirmar = (request.form.get("confirmar") or "").strip()
            prefeitura_id_form = request.form.get("prefeitura_id", type=int)
            prefeitura_id = _resolve_prefeitura_uvis(prefeitura_id_form, atual_prefeitura_id=uvis.prefeitura_id)

            form = {
                "nome_uvis": nome_uvis,
                "regiao": regiao or "",
                "codigo_setor": codigo_setor or "",
                "login": login,
                "prefeitura_id": prefeitura_id_form or "",
            }

            if is_admin_user(current_user) and not prefeitura_id:
                flash("Selecione a prefeitura da UVIS.", "warning")
                return render_template("admin_uvis_editar.html", uvis=uvis, prefeituras=prefeituras, form=form)
            if not prefeitura_id:
                flash("Nao foi possivel identificar a prefeitura para essa UVIS.", "warning")
                return render_template("admin_uvis_editar.html", uvis=uvis, prefeituras=prefeituras, form=form)

            if prefeitura_id and not Prefeitura.query.filter(Prefeitura.id == prefeitura_id).first():
                flash("Prefeitura selecionada nao encontrada.", "warning")
                return render_template("admin_uvis_editar.html", uvis=uvis, prefeituras=prefeituras, form=form)

            category, message = validate_edit_uvis(
                nome_uvis=nome_uvis,
                login=login,
                senha=senha,
                confirmar=confirmar,
                uvis_id=uvis.id,
            )
            if message:
                flash(message, category)
                return render_template("admin_uvis_editar.html", uvis=uvis, prefeituras=prefeituras, form=form)

            uvis.nome_uvis = nome_uvis
            uvis.regiao = regiao
            uvis.prefeitura_id = prefeitura_id
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
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao editar UVIS %s.", uvis.id)
                flash("Erro interno ao salvar a UVIS. Tente novamente.", "danger")

        if not form:
            form = {
                "nome_uvis": uvis.nome_uvis or "",
                "regiao": uvis.regiao or "",
                "codigo_setor": uvis.codigo_setor or "",
                "login": uvis.login or "",
                "prefeitura_id": uvis.prefeitura_id or "",
            }

        return render_template("admin_uvis_editar.html", uvis=uvis, prefeituras=prefeituras, form=form)

    @bp.route("/admin/uvis/<int:id>/excluir", methods=["POST"], endpoint="admin_uvis_excluir")
    @login_required
    def admin_uvis_excluir(id):
        resp = _admin_only_redirect()
        if resp:
            return resp

        uvis = build_uvis_query(current_user, "", "", "").filter(Usuario.id == id).first_or_404()
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
        prefeitura_id = request.args.get("prefeitura_id", type=int)
        rows = build_uvis_query(
            current_user,
            q,
            regiao,
            codigo_setor,
            prefeitura_id=prefeitura_id,
        ).all()
        output, filename = build_uvis_export(rows)

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
