from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import EquipeUvis, Solicitacao, Usuario
from app.modules.uvis_equipes.service import (
    MAX_MEMBROS_EQUIPE_UVIS,
    assign_team_to_solicitacao,
    build_admin_uvis_teams_listing,
    build_uvis_teams_listing,
    create_team_account,
    get_operational_uvis_account,
    get_team_account,
    get_team_members,
    next_team_name_for_user,
    next_team_slot,
    suggested_team_login,
    team_exists_for_user,
    upsert_operational_uvis_account,
    validate_team_login,
    validate_team_password,
)
from app.shared.access import is_admin_global_user, normalize_role


def _uvis_only():
    if getattr(current_user, "tipo_usuario", None) != "uvis":
        abort(403)


def _admin_only():
    if not is_admin_global_user(current_user):
        abort(403)


def _admin_or_operario_view_only():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "admin", "operario", "operador"}:
        abort(403)


def register_routes(bp):
    @bp.route("/uvis/acesso-operacional", methods=["GET", "POST"], endpoint="uvis_acesso_operacional")
    @login_required
    def uvis_acesso_operacional():
        _uvis_only()

        conta = get_operational_uvis_account(current_user.id)
        errors = {}
        form = {
            "login_operacional": conta.login if conta else "",
        }

        if request.method == "POST":
            login_operacional = (request.form.get("login_operacional") or "").strip()
            senha = (request.form.get("senha") or "").strip()
            senha2 = (request.form.get("senha2") or "").strip()
            form["login_operacional"] = login_operacional

            login_error = validate_team_login(
                login_operacional,
                current_login=conta.login if conta else None,
            )
            if login_error:
                errors["login_operacional"] = login_error

            errors.update(validate_team_password(senha, senha2, required=conta is None))

            if errors:
                flash("Revise os dados do acesso operacional.", "warning")
                return render_template(
                    "uvis_acesso_operacional.html",
                    conta=conta,
                    form=form,
                    errors=errors,
                )

            try:
                upsert_operational_uvis_account(current_user, login_operacional, senha)
                db.session.commit()
                flash("Acesso operacional da UVIS salvo com sucesso.", "success")
                return redirect(url_for("main.uvis_acesso_operacional"))
            except IntegrityError:
                db.session.rollback()
                errors["login_operacional"] = "Este login ja esta em uso. Escolha outro."
                flash(errors["login_operacional"], "danger")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao salvar acesso operacional UVIS para usuario %s.", current_user.id)
                flash("Erro interno ao salvar o acesso operacional. Tente novamente.", "danger")

        return render_template(
            "uvis_acesso_operacional.html",
            conta=conta,
            form=form,
            errors=errors,
        )

    @bp.route("/uvis/equipes", methods=["GET"], endpoint="listar_equipes_uvis")
    @login_required
    def listar_equipes_uvis():
        _uvis_only()
        equipes = build_uvis_teams_listing(current_user.id)
        return render_template("uvis_equipes_listar.html", equipes=equipes)

    @bp.route("/uvis/equipes/<string:nome_equipe>/credenciais", methods=["POST"], endpoint="atualizar_credenciais_equipe_uvis")
    @login_required
    def atualizar_credenciais_equipe_uvis(nome_equipe):
        _uvis_only()

        nome_equipe = (nome_equipe or "").strip()
        if not nome_equipe:
            flash("Equipe invalida.", "danger")
            return redirect(url_for("main.listar_equipes_uvis"))

        conta = get_team_account(current_user.id, nome_equipe)
        if not conta:
            flash("Conta (login) desta equipe nao encontrada.", "warning")
            return redirect(url_for("main.listar_equipes_uvis"))

        login_novo = (request.form.get("login_equipe") or "").strip()
        senha = (request.form.get("senha") or "").strip()
        senha2 = (request.form.get("senha2") or "").strip()

        login_error = validate_team_login(login_novo, current_login=conta.login)
        if login_error:
            flash(login_error, "warning" if "uso" not in login_error.lower() else "danger")
            return redirect(url_for("main.listar_equipes_uvis"))

        password_errors = validate_team_password(senha, senha2, required=False)
        if password_errors:
            flash(next(iter(password_errors.values())), "warning")
            return redirect(url_for("main.listar_equipes_uvis"))

        conta.login = login_novo
        if senha:
            conta.set_senha(senha)

        db.session.commit()
        flash("Credenciais atualizadas com sucesso!", "success")
        return redirect(url_for("main.listar_equipes_uvis"))

    @bp.route("/uvis/equipes/<string:nome_equipe>", methods=["GET"], endpoint="listar_membros_equipe_uvis")
    @login_required
    def listar_membros_equipe_uvis(nome_equipe):
        _uvis_only()

        nome_equipe = (nome_equipe or "").strip()
        if not nome_equipe:
            abort(404)

        membros = get_team_members(current_user.id, nome_equipe)
        return render_template(
            "uvis_equipe_membros_listar.html",
            nome_equipe=nome_equipe,
            membros=membros,
            total=len(membros),
            maximo=MAX_MEMBROS_EQUIPE_UVIS,
        )

    @bp.route("/uvis/equipes/<string:nome_equipe>/adicionar", methods=["GET", "POST"], endpoint="adicionar_membro_equipe_uvis")
    @login_required
    def adicionar_membro_equipe_uvis(nome_equipe):
        _uvis_only()

        nome_equipe = (nome_equipe or "").strip()
        if not nome_equipe:
            abort(404)

        errors = {}
        form = {"nome_equipe": nome_equipe}

        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            funcao = (request.form.get("funcao") or "").strip()
            contato = (request.form.get("contato") or "").strip()

            form.update({"nome": nome, "funcao": funcao, "contato": contato})
            if not nome:
                errors["nome"] = "Informe o nome do membro."

            slot = next_team_slot(current_user.id, nome_equipe)
            if not slot:
                errors["limite"] = "Limite maximo de 5 pessoas nesta equipe atingido."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "uvis_equipe_membro_adicionar.html",
                    form=form,
                    errors=errors,
                    nome_equipe=nome_equipe,
                )

            novo = EquipeUvis(
                uvis_usuario_id=current_user.id,
                nome_equipe=nome_equipe,
                ordem=slot,
                nome=nome,
                funcao=funcao or None,
                contato=contato or None,
            )
            db.session.add(novo)
            db.session.commit()

            flash("Membro adicionado com sucesso!", "success")
            return redirect(url_for("main.listar_membros_equipe_uvis", nome_equipe=nome_equipe))

        return render_template(
            "uvis_equipe_membro_adicionar.html",
            form=form,
            errors=errors,
            nome_equipe=nome_equipe,
        )

    @bp.route("/uvis/equipes/nova", methods=["GET", "POST"], endpoint="criar_equipe_uvis")
    @login_required
    def criar_equipe_uvis():
        _uvis_only()

        errors = {}
        nome_equipe = next_team_name_for_user(current_user)
        form = {
            "nome_equipe": nome_equipe,
            "login_equipe": suggested_team_login(nome_equipe),
        }

        if request.method == "POST":
            nome_equipe = next_team_name_for_user(current_user)
            form["nome_equipe"] = nome_equipe

            login_equipe = (request.form.get("login_equipe") or "").strip()
            senha = (request.form.get("senha") or "").strip()
            senha2 = (request.form.get("senha2") or "").strip()
            form["login_equipe"] = login_equipe

            if not nome_equipe:
                errors["nome_equipe"] = "Nao foi possivel gerar o nome automatico da equipe."

            login_error = validate_team_login(login_equipe)
            if login_error:
                errors["login_equipe"] = login_error

            errors.update(validate_team_password(senha, senha2, required=True))

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("uvis_equipe_criar.html", form=form, errors=errors)

            create_team_account(current_user, nome_equipe, login_equipe, senha)

            try:
                db.session.commit()
                flash("Equipe criada! Login da equipe definido com sucesso.", "success")
                return redirect(url_for("main.adicionar_membro_equipe_uvis", nome_equipe=nome_equipe))
            except IntegrityError:
                db.session.rollback()
                errors["login_equipe"] = "Este login ja esta em uso. Escolha outro."
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao criar equipe UVIS para usuario %s.", current_user.id)
                flash("Erro interno ao criar a equipe. Tente novamente.", "danger")

            return render_template("uvis_equipe_criar.html", form=form, errors=errors)

        return render_template("uvis_equipe_criar.html", form=form, errors=errors)

    @bp.route("/uvis/equipe-membro/<int:membro_id>/editar", methods=["GET", "POST"], endpoint="editar_membro_equipe_uvis")
    @login_required
    def editar_membro_equipe_uvis(membro_id):
        _uvis_only()

        membro = EquipeUvis.query.get_or_404(membro_id)
        if membro.uvis_usuario_id != current_user.id:
            abort(403)

        errors = {}
        form = {}

        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            funcao = (request.form.get("funcao") or "").strip()
            contato = (request.form.get("contato") or "").strip()
            form = {"nome": nome, "funcao": funcao, "contato": contato}

            if not nome:
                errors["nome"] = "Informe o nome do membro."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("uvis_equipe_membro_editar.html", membro=membro, form=form, errors=errors)

            membro.nome = nome
            membro.funcao = funcao or None
            membro.contato = contato or None
            db.session.commit()

            flash("Membro atualizado com sucesso!", "success")
            return redirect(url_for("main.listar_membros_equipe_uvis", nome_equipe=membro.nome_equipe))

        form = {
            "nome": membro.nome or "",
            "funcao": membro.funcao or "",
            "contato": membro.contato or "",
        }
        return render_template("uvis_equipe_membro_editar.html", membro=membro, form=form, errors=errors)

    @bp.route("/uvis/equipe-membro/<int:membro_id>/deletar", methods=["POST"], endpoint="deletar_membro_equipe_uvis")
    @login_required
    def deletar_membro_equipe_uvis(membro_id):
        _uvis_only()

        membro = EquipeUvis.query.get_or_404(membro_id)
        if membro.uvis_usuario_id != current_user.id:
            abort(403)

        nome_equipe = membro.nome_equipe
        db.session.delete(membro)
        db.session.commit()

        flash("Membro removido com sucesso.", "success")

        restante = EquipeUvis.query.filter_by(
            uvis_usuario_id=current_user.id,
            nome_equipe=nome_equipe,
        ).count()
        if restante == 0:
            flash("Equipe ficou sem membros e nao sera mais exibida.", "info")
            return redirect(url_for("main.listar_equipes_uvis"))

        return redirect(url_for("main.listar_membros_equipe_uvis", nome_equipe=nome_equipe))

    @bp.route("/solicitacao/<int:id>/atribuir-equipe-uvis", methods=["POST"], endpoint="atribuir_equipe_uvis_solicitacao")
    @login_required
    def atribuir_equipe_uvis_solicitacao(id):
        solicitacao = Solicitacao.query.get_or_404(id)

        if solicitacao.usuario_id != current_user.id and not is_admin_global_user(current_user):
            flash("Voce nao tem permissao para alterar esta solicitacao.", "danger")
            return redirect(url_for("main.dashboard"))

        nome_equipe = (request.form.get("nome_equipe") or "").strip()
        if not nome_equipe:
            flash("Selecione uma equipe.", "warning")
            return redirect(url_for("main.dashboard"))

        if not team_exists_for_user(current_user.id, nome_equipe):
            flash("Equipe UVIS nao encontrada para seu usuario.", "danger")
            return redirect(url_for("main.dashboard"))

        assign_team_to_solicitacao(id, nome_equipe)
        db.session.commit()

        flash("Equipe UVIS atribuida com sucesso!", "success")
        return redirect(url_for("main.dashboard"))

    @bp.route("/admin/uvis/equipes", methods=["GET"], endpoint="admin_listar_equipes_uvis")
    @login_required
    def admin_listar_equipes_uvis():
        _admin_or_operario_view_only()
        search = (request.args.get("q") or "").strip()
        equipes = build_admin_uvis_teams_listing(search=search)
        return render_template(
            "admin_uvis_equipes_listar.html",
            equipes=equipes,
            search=search,
        )

    @bp.route(
        "/admin/uvis/<int:uvis_id>/acesso-operacional",
        methods=["POST"],
        endpoint="admin_atualizar_acesso_operacional_uvis",
    )
    @login_required
    def admin_atualizar_acesso_operacional_uvis(uvis_id):
        _admin_or_operario_view_only()

        uvis = Usuario.query.filter_by(id=uvis_id, tipo_usuario="uvis").first_or_404()
        conta = get_operational_uvis_account(uvis.id)
        login_operacional = (request.form.get("login_operacional") or "").strip()
        senha = (request.form.get("senha") or "").strip()
        senha2 = (request.form.get("senha2") or "").strip()

        login_error = validate_team_login(
            login_operacional,
            current_login=conta.login if conta else None,
        )
        if login_error:
            flash(login_error, "danger" if "uso" in login_error.lower() else "warning")
            return redirect(url_for("main.admin_listar_equipes_uvis"))

        password_errors = validate_team_password(senha, senha2, required=conta is None)
        if password_errors:
            flash(next(iter(password_errors.values())), "warning")
            return redirect(url_for("main.admin_listar_equipes_uvis"))

        try:
            upsert_operational_uvis_account(uvis, login_operacional, senha)
            db.session.commit()
            flash(f"Acesso operacional de {uvis.nome_uvis} atualizado com sucesso.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Este login ja esta em uso. Escolha outro.", "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Erro ao salvar acesso operacional da UVIS %s pelo painel administrativo.",
                uvis.id,
            )
            flash("Erro interno ao salvar o acesso operacional. Tente novamente.", "danger")

        return redirect(url_for("main.admin_listar_equipes_uvis"))

    @bp.route("/admin/uvis/<int:uvis_id>/equipes/<string:nome_equipe>", methods=["GET"], endpoint="admin_listar_membros_equipe_uvis")
    @login_required
    def admin_listar_membros_equipe_uvis(uvis_id, nome_equipe):
        _admin_or_operario_view_only()
        flash("A gestao por membros foi substituida pelo acesso operacional unico de cada UVIS.", "info")
        return redirect(url_for("main.admin_listar_equipes_uvis"))
