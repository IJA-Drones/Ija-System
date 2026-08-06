from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Equipe, EquipePiloto, Pilotos
from app.modules.equipes.service import (
    build_equipes_export,
    build_equipes_filters,
    build_equipes_query,
    build_regioes_list,
    build_equipe_accounts_map,
    find_piloto_conflict,
    get_equipe_account,
    get_pilotos_ordered,
    is_truthy,
    parse_optional_int,
    regiao_valida,
    upsert_equipe_account,
    validate_equipe_account_form,
)
from app.shared.access import apply_prefeitura_scope, normalize_role


def _require_admin_or_operario():
    if normalize_role(getattr(current_user, "tipo_usuario", None)) not in {"dev", "admin", "operario", "operador", "prefeitura_admin"}:
        abort(403)


def register_routes(bp):
    @bp.route("/equipes/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_equipes")
    @login_required
    def cadastrar_equipes():
        _require_admin_or_operario()

        errors = {}
        form = {}
        pilotos = get_pilotos_ordered(user=current_user)
        regioes = build_regioes_list()

        if request.method == "POST":
            nome_equipe = (request.form.get("nome_equipe") or "").strip()
            descricao = (request.form.get("descricao") or "").strip()
            regiao = (request.form.get("regiao") or "").strip().upper()
            trabalha_oceano_azul = request.form.get("trabalha_oceano_azul") == "1"
            piloto_id = (request.form.get("piloto_id") or "").strip()
            auxiliar_id = (request.form.get("auxiliar_id") or "").strip()

            form = {
                "nome_equipe": nome_equipe,
                "descricao": descricao,
                "regiao": regiao,
                "trabalha_oceano_azul": "1" if trabalha_oceano_azul else "",
                "piloto_id": piloto_id,
                "auxiliar_id": auxiliar_id,
            }

            if not nome_equipe:
                errors["nome_equipe"] = "Informe o nome da equipe."

            if not regiao_valida(regiao):
                errors["regiao"] = "Selecione uma regiao valida."

            if piloto_id and auxiliar_id and piloto_id == auxiliar_id:
                errors["auxiliar_id"] = "Auxiliar deve ser diferente do piloto titular."

            if nome_equipe:
                existe = apply_prefeitura_scope(
                    Equipe.query.filter(db.func.lower(Equipe.nome_equipe) == nome_equipe.lower()),
                    current_user,
                    Equipe.prefeitura_id,
                ).first()
                if existe:
                    errors["nome_equipe"] = "Ja existe uma equipe com esse nome."

            piloto_id_int = parse_optional_int(piloto_id)
            auxiliar_id_int = parse_optional_int(auxiliar_id)
            piloto_obj = None
            auxiliar_obj = None

            if piloto_id and piloto_id_int is None:
                errors["piloto_id"] = "Piloto titular invalido."
            elif piloto_id_int:
                piloto_obj = apply_prefeitura_scope(
                    Pilotos.query.filter(Pilotos.id == piloto_id_int),
                    current_user,
                    Pilotos.prefeitura_id,
                ).first()
                if not piloto_obj:
                    errors["piloto_id"] = "Piloto titular nao encontrado."

            if auxiliar_id and auxiliar_id_int is None:
                errors["auxiliar_id"] = "Piloto auxiliar invalido."
            elif auxiliar_id_int:
                auxiliar_obj = apply_prefeitura_scope(
                    Pilotos.query.filter(Pilotos.id == auxiliar_id_int),
                    current_user,
                    Pilotos.prefeitura_id,
                ).first()
                if not auxiliar_obj:
                    errors["auxiliar_id"] = "Piloto auxiliar nao encontrado."

            if piloto_id_int and "piloto_id" not in errors:
                vinculo, equipe = find_piloto_conflict(piloto_id_int, user=current_user)
                if vinculo:
                    nome_eq = equipe.nome_equipe if equipe else f"ID {vinculo.equipe_id}"
                    papel = (vinculo.papel or "").lower()
                    errors["piloto_id"] = f"Este piloto já está vinculado à equipe '{nome_eq}' como {papel}. Para atribuí-lo a esta equipe, primeiro remova o vínculo atual."
                    flash(errors["piloto_id"], "warning")

            if auxiliar_id_int and "auxiliar_id" not in errors:
                vinculo, equipe = find_piloto_conflict(auxiliar_id_int, user=current_user)
                if vinculo:
                    nome_eq = equipe.nome_equipe if equipe else f"ID {vinculo.equipe_id}"
                    papel = (vinculo.papel or "").lower()
                    errors["auxiliar_id"] = f"Este piloto ja esta na equipe '{nome_eq}' como {papel}. Remova de la antes."
                    flash(errors["auxiliar_id"], "warning")

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template(
                    "cadastrar_equipes.html",
                    form=form,
                    errors=errors,
                    pilotos=pilotos,
                    regioes=regioes,
                )

            equipe = Equipe(
                nome_equipe=nome_equipe,
                descricao=descricao or None,
                regiao=regiao or None,
                ativa=True,
                trabalha_oceano_azul=trabalha_oceano_azul,
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
            )
            db.session.add(equipe)
            db.session.flush()

            if piloto_obj:
                db.session.add(EquipePiloto(equipe_id=equipe.id, piloto_id=piloto_obj.id, papel="piloto"))
            if auxiliar_obj:
                db.session.add(EquipePiloto(equipe_id=equipe.id, piloto_id=auxiliar_obj.id, papel="auxiliar"))

            try:
                db.session.commit()
                flash("Equipe cadastrada com sucesso!", "success")
                return redirect(url_for("main.listar_equipes"))
            except Exception:
                db.session.rollback()
                flash("Erro ao salvar no banco. Verifique se os pilotos ja estao em outra equipe.", "danger")
                return render_template(
                    "cadastrar_equipes.html",
                    form=form,
                    errors=errors,
                    pilotos=pilotos,
                    regioes=regioes,
                )

        return render_template(
            "cadastrar_equipes.html",
            form=form,
            errors=errors,
            pilotos=pilotos,
            regioes=regioes,
        )

    @bp.route("/equipes", methods=["GET"], endpoint="listar_equipes")
    @login_required
    def listar_equipes():
        tipo = normalize_role(getattr(current_user, "tipo_usuario", None))
        q = (request.args.get("q") or "").strip()
        regiao = (request.args.get("regiao") or "").strip()
        ativa = (request.args.get("ativa") or "").strip().lower()
        piloto_id = (request.args.get("piloto_id") or "").strip()
        auxiliar_id = (request.args.get("auxiliar_id") or "").strip()
        sort = (request.args.get("sort") or "nome_asc").strip()
        export = (request.args.get("export") or "").strip().lower()

        try:
            page = max(1, int(request.args.get("page") or 1))
        except ValueError:
            page = 1

        try:
            per_page = int(request.args.get("per_page") or 20)
        except ValueError:
            per_page = 20
        per_page = 10 if per_page < 10 else 50 if per_page > 50 else per_page

        user_regiao = getattr(current_user, "regiao", None)
        query, regiao, ativa = build_equipes_query(
            tipo=tipo,
            regiao=regiao,
            ativa=ativa,
            piloto_id=piloto_id,
            auxiliar_id=auxiliar_id,
            q=q,
            sort=sort,
            user_regiao=user_regiao,
            user=current_user,
        )

        if export == "xlsx":
            if tipo not in ["dev", "admin", "visualizar", "prefeitura_admin"]:
                abort(403)

            output, filename = build_equipes_export(query.all())
            return send_file(
                output,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        equipes = pagination.items
        equipe_accounts = build_equipe_accounts_map(equipes)
        is_editable = tipo in ["dev", "admin", "operario", "operador", "prefeitura_admin"]
        filters = build_equipes_filters(
            q=q,
            regiao=regiao,
            ativa=ativa,
            piloto_id=piloto_id,
            auxiliar_id=auxiliar_id,
            sort=sort,
            page=page,
            per_page=per_page,
            total=pagination.total,
            total_pages=pagination.pages,
            locked_regiao=(tipo == "uvis"),
            locked_ativa=(tipo == "uvis"),
        )

        return render_template(
            "listar_equipes.html",
            equipes=equipes,
            filters=filters,
            is_admin=(tipo in {"dev", "admin"}),
            is_editable=is_editable,
            tipo_usuario=tipo,
            equipe_accounts=equipe_accounts,
        )

    @bp.route("/equipes/<int:equipe_id>/credenciais", methods=["POST"], endpoint="atualizar_credenciais_equipe")
    @login_required
    def atualizar_credenciais_equipe(equipe_id):
        _require_admin_or_operario()

        equipe = apply_prefeitura_scope(Equipe.query, current_user, Equipe.prefeitura_id).filter(Equipe.id == equipe_id).first_or_404()
        account = get_equipe_account(equipe.id)
        login = (request.form.get("login_equipe") or "").strip()
        senha = request.form.get("senha_equipe") or ""
        senha2 = request.form.get("senha_equipe2") or ""
        errors = validate_equipe_account_form(login, senha, senha2, current_account=account)
        if errors:
            for message in errors.values():
                flash(message, "warning")
            return redirect(url_for("main.listar_equipes"))

        try:
            upsert_equipe_account(equipe, login, senha)
            db.session.commit()
            flash(f"Login operacional da equipe '{equipe.nome_equipe}' atualizado.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao atualizar credenciais da equipe %s.", equipe.id)
            flash("Erro ao atualizar credenciais da equipe. Tente novamente.", "danger")

        return redirect(url_for("main.listar_equipes"))

    @bp.route("/equipes/<int:equipe_id>/editar", methods=["GET", "POST"], endpoint="editar_equipe")
    @login_required
    def editar_equipe(equipe_id):
        _require_admin_or_operario()

        equipe = (
            apply_prefeitura_scope(
                Equipe.query.options(
                    db.selectinload(Equipe.membros).selectinload(EquipePiloto.piloto),
                ),
                current_user,
                Equipe.prefeitura_id,
            )
            .filter(Equipe.id == equipe_id)
            .first_or_404()
        )
        piloto_atual = equipe.piloto_titular
        aux_atual = equipe.piloto_auxiliar
        errors = {}
        form = request.form.to_dict(flat=True) if request.method == "POST" else {}
        pilotos = get_pilotos_ordered(user=current_user)

        if request.method == "POST":
            nome_equipe = (request.form.get("nome_equipe") or "").strip()
            regiao = (request.form.get("regiao") or "").strip().upper()
            ativa_raw = (request.form.get("ativa") or "").strip()
            trabalha_oceano_azul = request.form.get("trabalha_oceano_azul") == "1"
            descricao = (request.form.get("descricao") or "").strip()
            piloto_id_raw = (request.form.get("piloto_id") or "").strip()
            auxiliar_id_raw = (request.form.get("auxiliar_id") or "").strip()
            form["trabalha_oceano_azul"] = "1" if trabalha_oceano_azul else ""

            if not nome_equipe:
                errors["nome_equipe"] = "Informe o nome da equipe."

            if not regiao_valida(regiao):
                errors["regiao"] = "Regiao invalida."

            ativa = is_truthy(ativa_raw)
            piloto_id = parse_optional_int(piloto_id_raw)
            auxiliar_id = parse_optional_int(auxiliar_id_raw)

            if piloto_id_raw and piloto_id is None:
                errors["piloto_id"] = "Piloto titular invalido."

            if auxiliar_id_raw and auxiliar_id is None:
                errors["auxiliar_id"] = "Auxiliar invalido."

            if piloto_id and auxiliar_id and piloto_id == auxiliar_id:
                errors["auxiliar_id"] = "O auxiliar nao pode ser o mesmo piloto titular."

            piloto_obj = (
                apply_prefeitura_scope(
                    Pilotos.query.filter(Pilotos.id == piloto_id),
                    current_user,
                    Pilotos.prefeitura_id,
                ).first()
                if piloto_id else None
            )
            if piloto_id and not piloto_obj:
                errors["piloto_id"] = "Piloto titular nao encontrado."

            aux_obj = (
                apply_prefeitura_scope(
                    Pilotos.query.filter(Pilotos.id == auxiliar_id),
                    current_user,
                    Pilotos.prefeitura_id,
                ).first()
                if auxiliar_id else None
            )
            if auxiliar_id and not aux_obj:
                errors["auxiliar_id"] = "Auxiliar nao encontrado."

            if piloto_id and "piloto_id" not in errors:
                vinculo, equipe_conflito = find_piloto_conflict(piloto_id, exclude_equipe_id=equipe.id, user=current_user)
                if vinculo:
                    nome_eq = equipe_conflito.nome_equipe if equipe_conflito and equipe_conflito.nome_equipe else f"ID {vinculo.equipe_id}"
                    papel = (vinculo.papel or "").lower()
                    msg = f"Este piloto ja esta na equipe '{nome_eq}' como {papel}. Remova de la antes de atribuir aqui."
                    errors["piloto_id"] = msg
                    flash(msg, "warning")

            if auxiliar_id and "auxiliar_id" not in errors:
                vinculo, equipe_conflito = find_piloto_conflict(auxiliar_id, exclude_equipe_id=equipe.id, user=current_user)
                if vinculo:
                    nome_eq = equipe_conflito.nome_equipe if equipe_conflito and equipe_conflito.nome_equipe else f"ID {vinculo.equipe_id}"
                    papel = (vinculo.papel or "").lower()
                    msg = f"Este piloto ja esta na equipe '{nome_eq}' como {papel}. Remova de la antes de atribuir aqui."
                    errors["auxiliar_id"] = msg
                    flash(msg, "warning")

            if not errors:
                equipe.nome_equipe = nome_equipe
                equipe.regiao = regiao or None
                equipe.ativa = ativa
                equipe.trabalha_oceano_azul = trabalha_oceano_azul
                equipe.descricao = descricao or None
                account = get_equipe_account(equipe.id)
                if account:
                    account.trabalha_oceano_azul = trabalha_oceano_azul

                membro_piloto = next((membro for membro in equipe.membros if membro.papel == "piloto"), None)
                if piloto_id:
                    if membro_piloto:
                        membro_piloto.piloto_id = piloto_id
                    else:
                        equipe.membros.append(EquipePiloto(equipe_id=equipe.id, piloto_id=piloto_id, papel="piloto"))
                elif membro_piloto:
                    db.session.delete(membro_piloto)

                membro_aux = next((membro for membro in equipe.membros if membro.papel == "auxiliar"), None)
                if auxiliar_id:
                    if membro_aux:
                        membro_aux.piloto_id = auxiliar_id
                    else:
                        equipe.membros.append(
                            EquipePiloto(equipe_id=equipe.id, piloto_id=auxiliar_id, papel="auxiliar")
                        )
                elif membro_aux:
                    db.session.delete(membro_aux)

                ids = [
                    membro.piloto_id
                    for membro in equipe.membros
                    if membro.piloto_id and membro not in db.session.deleted
                ]
                if len(ids) != len(set(ids)):
                    db.session.rollback()
                    errors["auxiliar_id"] = "Equipe nao pode ter o mesmo piloto em mais de um papel."
                    flash(errors["auxiliar_id"], "danger")
                    return render_template(
                        "editar_equipe.html",
                        equipe=equipe,
                        pilotos=pilotos,
                        errors=errors,
                        form=form,
                        piloto_atual=piloto_atual,
                        aux_atual=aux_atual,
                        is_admin=True,
                    )

                try:
                    db.session.commit()
                    flash("Equipe atualizada com sucesso.", "success")
                    return redirect(url_for("main.listar_equipes", equipe_id=equipe.id))
                except Exception as exc:
                    db.session.rollback()
                    current_app.logger.error(f"Erro ao atualizar equipe {equipe.id}: {exc}")
                    flash("Erro ao salvar alteracoes da equipe. Tente novamente.", "danger")
            else:
                flash("Corrija os campos destacados e tente novamente.", "danger")

        return render_template(
            "editar_equipe.html",
            equipe=equipe,
            pilotos=pilotos,
            errors=errors,
            form=form,
            piloto_atual=piloto_atual,
            aux_atual=aux_atual,
            is_admin=True,
        )

    @bp.route("/equipes/<int:equipe_id>/deletar", methods=["POST"], endpoint="deletar_equipe")
    @login_required
    def deletar_equipe(equipe_id):
        _require_admin_or_operario()

        equipe = apply_prefeitura_scope(Equipe.query, current_user, Equipe.prefeitura_id).filter(Equipe.id == equipe_id).first_or_404()

        try:
            db.session.delete(equipe)
            db.session.commit()
            flash(f"Equipe '{equipe.nome_equipe}' excluida com sucesso.", "success")
        except Exception:
            db.session.rollback()
            flash("Nao foi possivel excluir a equipe. Verifique se ha vinculos ativos no sistema.", "danger")

        return redirect(url_for("main.listar_equipes"))
