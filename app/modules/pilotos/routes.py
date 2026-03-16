from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Equipe, EquipePiloto, Pilotos, Usuario
from app.modules.pilotos.service import (
    build_pilotos_export,
    build_pilotos_filters,
    build_pilotos_query,
    format_phone_br,
    login_em_uso,
    normalize_page,
    normalize_pagination,
    normalize_per_page,
    only_digits,
    piloto_duplicado,
    serialize_pilotos,
    validate_piloto_data,
)


def register_routes(bp):
    @bp.route("/pilotos/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_pilotos")
    @login_required
    def cadastrar_pilotos():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        errors = {}
        form = {}

        if request.method == "POST":
            nome_piloto = (request.form.get("nome_piloto") or "").strip()
            regiao = (request.form.get("regiao") or "").strip().upper()
            telefone = (request.form.get("telefone") or "").strip()

            login = (request.form.get("login") or "").strip()
            senha = request.form.get("senha") or ""
            senha2 = request.form.get("senha2") or ""

            form = {
                "nome_piloto": nome_piloto,
                "regiao": regiao,
                "telefone": telefone,
                "login": login,
                "senha": senha,
                "senha2": senha2,
            }

            errors, tel_digits = validate_piloto_data(nome_piloto, regiao, telefone)

            if piloto_duplicado(nome_piloto, tel_digits):
                errors["nome_piloto"] = "Ja existe um piloto com esse nome (e telefone)."

            if not login:
                errors["login"] = "Informe um login para o piloto."
            elif login_em_uso(login):
                errors["login"] = "Esse login ja esta em uso."

            if not senha:
                errors["senha"] = "Informe uma senha."
            elif len(senha) < 6:
                errors["senha"] = "A senha deve ter pelo menos 6 caracteres."

            if senha != senha2:
                errors["senha2"] = "As senhas nao conferem."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("cadastrar_pilotos.html", form=form, errors=errors)

            try:
                novo_piloto = Pilotos(
                    nome_piloto=nome_piloto,
                    regiao=regiao or None,
                    telefone=tel_digits or None,
                )
                db.session.add(novo_piloto)
                db.session.flush()

                user_piloto = Usuario(
                    nome_uvis=nome_piloto,
                    regiao=regiao or None,
                    codigo_setor=None,
                    login=login,
                    tipo_usuario="piloto",
                    piloto_id=novo_piloto.id,
                )
                user_piloto.set_senha(senha)

                db.session.add(user_piloto)
                db.session.commit()

                flash("Piloto e usuario criados com sucesso!", "success")
                return redirect(url_for("main.listar_pilotos"))
            except Exception:
                db.session.rollback()
                flash("Erro ao cadastrar piloto/usuario. Tente novamente.", "danger")
                return render_template("cadastrar_pilotos.html", form=form, errors=errors)

        return render_template("cadastrar_pilotos.html", form=form, errors=errors)

    @bp.route("/pilotos", methods=["GET"], endpoint="listar_pilotos")
    @login_required
    def listar_pilotos():
        user_tipo = getattr(current_user, "tipo_usuario", None)
        if user_tipo not in ("admin", "uvis", "visualizar"):
            abort(403)

        q = (request.args.get("q") or "").strip()
        regiao = (request.args.get("regiao") or "").strip().upper()
        telefone = (request.args.get("telefone") or "").strip()
        sort = (request.args.get("sort") or "nome_asc").strip()
        page = normalize_page(request.args.get("page"))
        per_page = normalize_per_page(request.args.get("per_page"))
        export = (request.args.get("export") or "").strip().lower()

        uvis_regiao = (getattr(current_user, "regiao", None) or "").strip().upper()
        if user_tipo == "uvis":
            regiao = uvis_regiao

        if user_tipo == "uvis" and not uvis_regiao:
            filters = build_pilotos_filters(q, regiao, telefone, sort, page, per_page, 0, 1)
            flash("Sua UVIS esta sem regiao cadastrada. Contate o administrador.", "warning")
            return render_template("listar_pilotos.html", pilotos=[], filters=filters, is_admin=False)

        query = build_pilotos_query(user_tipo, regiao, telefone, q, sort)

        if export == "xlsx":
            if user_tipo not in ["admin", "visualizar"]:
                abort(403)

            output, filename = build_pilotos_export(query.all(), user_tipo, uvis_regiao)
            return send_file(
                output,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        total = query.count()
        page, total_pages = normalize_pagination(total, page, per_page)
        pilotos = serialize_pilotos(query.offset((page - 1) * per_page).limit(per_page).all())
        filters = build_pilotos_filters(q, regiao, telefone, sort, page, per_page, total, total_pages)

        return render_template(
            "listar_pilotos.html",
            pilotos=pilotos,
            filters=filters,
            is_admin=(user_tipo == "admin"),
            is_editable=user_tipo in ["admin", "operario"],
            tipo_usuario=user_tipo,
            uvis_regiao=(uvis_regiao if user_tipo == "uvis" else None),
        )

    @bp.route("/pilotos/<int:piloto_id>/editar", methods=["GET", "POST"], endpoint="editar_piloto")
    @login_required
    def editar_piloto(piloto_id):
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        piloto = Pilotos.query.get_or_404(piloto_id)
        usuario_piloto = Usuario.query.filter_by(piloto_id=piloto.id, tipo_usuario="piloto").first()

        errors = {}
        form = {}

        if request.method == "POST":
            nome_piloto = (request.form.get("nome_piloto") or "").strip()
            regiao = (request.form.get("regiao") or "").strip().upper()
            telefone = (request.form.get("telefone") or "").strip()
            login = (request.form.get("login") or "").strip()
            senha = (request.form.get("senha") or "").strip()
            senha2 = (request.form.get("senha2") or "").strip()

            form = {
                "nome_piloto": nome_piloto,
                "regiao": regiao,
                "telefone": telefone,
                "login": login,
            }

            errors, tel_digits = validate_piloto_data(nome_piloto, regiao, telefone)

            if piloto_duplicado(nome_piloto, tel_digits, exclude_id=piloto.id):
                errors["nome_piloto"] = "Ja existe um piloto com esse nome (e telefone)."

            if not login:
                errors["login"] = "Informe o login do piloto."
            elif login_em_uso(login, exclude_user_id=(usuario_piloto.id if usuario_piloto else None)):
                errors["login"] = "Este login ja esta em uso. Escolha outro."

            if senha or senha2:
                if len(senha) < 4:
                    errors["senha"] = "A senha deve ter pelo menos 4 caracteres."
                if senha != senha2:
                    errors["senha2"] = "As senhas nao conferem."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "editar_piloto.html",
                    piloto=piloto,
                    form=form,
                    errors=errors,
                    usuario_piloto=usuario_piloto,
                )

            piloto.nome_piloto = nome_piloto
            piloto.regiao = regiao or None
            piloto.telefone = tel_digits or None

            if not usuario_piloto:
                usuario_piloto = Usuario(
                    nome_uvis=nome_piloto,
                    regiao=regiao or None,
                    codigo_setor=None,
                    login=login,
                    tipo_usuario="piloto",
                    piloto_id=piloto.id,
                )
                if not senha:
                    errors["senha"] = "Defina uma senha para criar o acesso do piloto."
                    flash("Corrija os campos destacados.", "warning")
                    return render_template(
                        "editar_piloto.html",
                        piloto=piloto,
                        form=form,
                        errors=errors,
                        usuario_piloto=usuario_piloto,
                    )
                usuario_piloto.set_senha(senha)
                db.session.add(usuario_piloto)
            else:
                usuario_piloto.nome_uvis = nome_piloto
                usuario_piloto.regiao = regiao or None
                usuario_piloto.login = login
                if senha:
                    usuario_piloto.set_senha(senha)

            db.session.commit()

            flash("Piloto atualizado com sucesso!", "success")
            return redirect(url_for("main.listar_pilotos"))

        form = {
            "nome_piloto": piloto.nome_piloto,
            "regiao": piloto.regiao or "",
            "telefone": format_phone_br(piloto.telefone or ""),
            "login": usuario_piloto.login if usuario_piloto else "",
        }

        return render_template(
            "editar_piloto.html",
            piloto=piloto,
            form=form,
            errors=errors,
            usuario_piloto=usuario_piloto,
        )

    @bp.route("/pilotos/<int:piloto_id>/deletar", methods=["POST"], endpoint="deletar_piloto")
    @login_required
    def deletar_piloto(piloto_id):
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        piloto = Pilotos.query.get_or_404(piloto_id)
        vinculo = EquipePiloto.query.filter(EquipePiloto.piloto_id == piloto.id).first()

        if vinculo:
            equipe = Equipe.query.get(vinculo.equipe_id)
            nome_equipe = equipe.nome_equipe if equipe and equipe.nome_equipe else f"ID {vinculo.equipe_id}"
            papel = (vinculo.papel or "").lower()

            flash(
                f"Nao e possivel excluir o piloto '{piloto.nome_piloto}' porque ele esta vinculado a equipe '{nome_equipe}' como {papel}. Remova o vinculo da equipe antes de excluir.",
                "warning",
            )
            return redirect(url_for("main.listar_pilotos"))

        Usuario.query.filter_by(piloto_id=piloto.id, tipo_usuario="piloto").delete(synchronize_session=False)
        db.session.delete(piloto)
        db.session.commit()

        flash("Piloto excluido com sucesso.", "success")
        return redirect(url_for("main.listar_pilotos"))
