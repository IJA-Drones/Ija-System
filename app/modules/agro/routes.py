import math

from flask import abort, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ClienteAgro, EquipamentoAgro, EquipeAgro, OrcamentoAgro, PilotoAgro
from app.modules.agro.exporters import build_orcamento_agro_pdf
from app.modules.agro.service import (
    agro_bool_label,
    build_clientes_agro_query,
    build_endereco_agro,
    build_orcamentos_agro_query,
    can_access_agro_panel,
    can_edit_agro_panel,
    get_agro_dashboard_context,
    remove_orcamento_attachment,
    resolve_orcamento_attachment,
    save_orcamento_attachment,
    serialize_cliente_agro,
    update_orcamento_snapshot_from_cliente,
)
from app.shared.access import apply_prefeitura_scope
from app.shared.formatters import format_cep, format_currency_br, format_documento, format_phone_br, only_digits, parse_currency_br
from app.shared.validators import validate_documento


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _require_agro_access():
    if not can_access_agro_panel(current_user):
        abort(403)


def _require_agro_edit():
    if not can_edit_agro_panel(current_user):
        abort(403)


def _get_cliente_agro_or_404(cliente_id: int):
    query = apply_prefeitura_scope(ClienteAgro.query, current_user, ClienteAgro.prefeitura_id)
    return query.filter(ClienteAgro.id == cliente_id).first_or_404()


def _get_orcamento_agro_or_404(orcamento_id: int):
    query = apply_prefeitura_scope(OrcamentoAgro.query, current_user, OrcamentoAgro.prefeitura_id)
    return query.filter(OrcamentoAgro.id == orcamento_id).first_or_404()


def _get_equipe_agro_or_404(equipe_id: int):
    query = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id)
    return query.filter(EquipeAgro.id == equipe_id).first_or_404()


def _get_piloto_agro_or_404(piloto_id: int):
    query = apply_prefeitura_scope(PilotoAgro.query, current_user, PilotoAgro.prefeitura_id)
    return query.filter(PilotoAgro.id == piloto_id).first_or_404()


def _get_equipamento_agro_or_404(equipamento_id: int):
    query = apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
    return query.filter(EquipamentoAgro.id == equipamento_id).first_or_404()


def _normalize_cliente_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "documento": (form_source.get("documento") or "").strip(),
        "cep": format_cep(form_source.get("cep") or ""),
        "logradouro": (form_source.get("logradouro") or "").strip(),
        "numero": (form_source.get("numero") or "").strip(),
        "complemento": (form_source.get("complemento") or "").strip(),
        "bairro": (form_source.get("bairro") or "").strip(),
        "cidade": (form_source.get("cidade") or "").strip(),
        "uf": (form_source.get("uf") or "").strip().upper(),
    }


def _validate_cliente_agro_form(form, *, cliente_atual=None):
    errors = {}

    if not form["nome"]:
        errors["nome"] = "Informe o nome do cliente."

    if not form["documento"]:
        errors["documento"] = "Informe o documento do cliente."

    doc_ok = False
    doc_digits = ""
    doc_fmt = ""
    if form["documento"]:
        doc_ok, _doc_tipo, doc_digits, doc_fmt, doc_error = validate_documento(form["documento"])
        if not doc_ok:
            errors["documento"] = doc_error

    cep_digits = only_digits(form["cep"])
    if len(cep_digits) != 8:
        errors["cep"] = "Informe um CEP válido com 8 dígitos."

    for field, label in (
        ("logradouro", "logradouro"),
        ("numero", "numero"),
        ("bairro", "bairro"),
        ("cidade", "cidade"),
        ("uf", "UF"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    if form["uf"] and len(form["uf"]) != 2:
        errors["uf"] = "UF deve ter 2 letras."

    if doc_ok:
        query = ClienteAgro.query.filter(ClienteAgro.documento == doc_digits)
        if cliente_atual is not None:
            query = query.filter(ClienteAgro.id != cliente_atual.id)
        query = apply_prefeitura_scope(query, current_user, ClienteAgro.prefeitura_id)
        if query.first():
            errors["documento"] = "Já existe um cliente agro com esse documento."

    return errors, doc_digits, doc_fmt, cep_digits


def _normalize_orcamento_form(form_source):
    return {
        "cliente_agro_id": (form_source.get("cliente_agro_id") or "").strip(),
        "nome_fazenda": (form_source.get("nome_fazenda") or "").strip(),
        "mapeamento": (form_source.get("mapeamento") or "NAO").strip().upper(),
        "risco_operacional": (form_source.get("risco_operacional") or "").strip(),
        "cultura": (form_source.get("cultura") or "").strip(),
        "protocolo": (form_source.get("protocolo") or "").strip(),
        "preco_base": (form_source.get("preco_base") or "").strip(),
        "cep": format_cep(form_source.get("cep") or ""),
        "logradouro": (form_source.get("logradouro") or "").strip(),
        "numero": (form_source.get("numero") or "").strip(),
        "complemento": (form_source.get("complemento") or "").strip(),
        "bairro": (form_source.get("bairro") or "").strip(),
        "cidade": (form_source.get("cidade") or "").strip(),
        "uf": (form_source.get("uf") or "").strip().upper(),
    }


def _normalize_bool_form(value, default=True):
    raw = (value or "").strip().upper()
    if not raw:
        return default
    return raw in {"1", "SIM", "TRUE", "ATIVO"}


def _normalize_optional_int(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_equipe_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "descricao": (form_source.get("descricao") or "").strip(),
        "ativa": (form_source.get("ativa") or "SIM").strip().upper(),
    }


def _validate_equipe_agro_form(form, *, equipe_atual=None):
    errors = {}
    if not form["nome"]:
        errors["nome"] = "Informe o nome da equipe."

    if form["nome"]:
        query = apply_prefeitura_scope(
            EquipeAgro.query.filter(db.func.lower(EquipeAgro.nome) == form["nome"].lower()),
            current_user,
            EquipeAgro.prefeitura_id,
        )
        if equipe_atual is not None:
            query = query.filter(EquipeAgro.id != equipe_atual.id)
        if query.first():
            errors["nome"] = "Já existe uma equipe agro com esse nome."

    return errors, _normalize_bool_form(form["ativa"], default=True)


def _normalize_piloto_form(form_source):
    return {
        "nome": (form_source.get("nome") or "").strip(),
        "telefone": (form_source.get("telefone") or "").strip(),
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
        "ativo": (form_source.get("ativo") or "SIM").strip().upper(),
    }


def _validate_piloto_agro_form(form, equipes, *, piloto_atual=None):
    del piloto_atual
    errors = {}
    equipe = None
    if not form["nome"]:
        errors["nome"] = "Informe o nome do piloto."

    telefone_digits = only_digits(form["telefone"])
    if form["telefone"] and len(telefone_digits) not in (10, 11):
        errors["telefone"] = "Informe um telefone com DDD e 10 ou 11 dígitos."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    if form["equipe_agro_id"] and equipe_id is None:
        errors["equipe_agro_id"] = "Selecione uma equipe válida."
    elif equipe_id:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada não foi encontrada."

    return errors, telefone_digits, equipe_id, equipe, _normalize_bool_form(form["ativo"], default=True)


def _normalize_equipamento_form(form_source):
    return {
        "tipo": (form_source.get("tipo") or "").strip(),
        "modelo": (form_source.get("modelo") or "").strip(),
        "identificacao": (form_source.get("identificacao") or "").strip(),
        "numero_serie": (form_source.get("numero_serie") or "").strip(),
        "status": (form_source.get("status") or "Ativo").strip(),
        "equipe_agro_id": (form_source.get("equipe_agro_id") or "").strip(),
    }


def _validate_equipamento_agro_form(form, equipes, *, equipamento_atual=None):
    errors = {}
    equipe = None

    for field, label in (
        ("tipo", "o tipo do equipamento"),
        ("modelo", "o modelo"),
        ("identificacao", "a identificação"),
        ("status", "o status"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    equipe_id = _normalize_optional_int(form["equipe_agro_id"])
    if form["equipe_agro_id"] and equipe_id is None:
        errors["equipe_agro_id"] = "Selecione uma equipe válida."
    elif equipe_id:
        equipe = next((item for item in equipes if item.id == equipe_id), None)
        if not equipe:
            errors["equipe_agro_id"] = "A equipe selecionada não foi encontrada."

    numero_serie = (form["numero_serie"] or "").strip() or None
    if numero_serie:
        query = EquipamentoAgro.query.filter(EquipamentoAgro.numero_serie == numero_serie)
        query = apply_prefeitura_scope(query, current_user, EquipamentoAgro.prefeitura_id)
        if equipamento_atual is not None:
            query = query.filter(EquipamentoAgro.id != equipamento_atual.id)
        if query.first():
            errors["numero_serie"] = "Já existe um equipamento agro com esse número de série."

    return errors, numero_serie, equipe_id, equipe


def _validate_orcamento_form(form):
    errors = {}
    cliente = None
    preco_base = parse_currency_br(form.get("preco_base"))

    try:
        cliente_id = int(form["cliente_agro_id"])
    except (TypeError, ValueError):
        cliente_id = None

    if not cliente_id:
        errors["cliente_agro_id"] = "Selecione o cliente."
    else:
        cliente = _get_cliente_agro_or_404(cliente_id)

    if not form["nome_fazenda"]:
        errors["nome_fazenda"] = "Informe o nome da fazenda."

    if not form["preco_base"]:
        errors["preco_base"] = "Informe o preço base do orçamento."
    elif preco_base is None:
        errors["preco_base"] = "Informe um valor monetário válido. Ex.: 1500,00"
    elif preco_base < 0:
        errors["preco_base"] = "O preço base não pode ser negativo."

    if len(form["cultura"]) > 100:
        errors["cultura"] = "Cultura deve ter no máximo 100 caracteres."

    cep_digits = only_digits(form["cep"])
    if len(cep_digits) != 8:
        errors["cep"] = "Informe um CEP válido com 8 dígitos."

    for field, label in (
        ("logradouro", "logradouro"),
        ("numero", "numero"),
        ("bairro", "bairro"),
        ("cidade", "cidade"),
        ("uf", "UF"),
    ):
        if not form[field]:
            errors[field] = f"Informe {label}."

    if form["uf"] and len(form["uf"]) != 2:
        errors["uf"] = "UF deve ter 2 letras."

    return errors, cliente, cep_digits, preco_base


def register_routes(bp):
    @bp.route("/agro", endpoint="agro_root")
    @login_required
    def agro_root():
        _require_agro_access()
        return redirect(url_for("main.admin_agro"))

    @bp.route("/agro/admin", endpoint="admin_agro")
    @login_required
    def admin_agro():
        _require_agro_access()
        context = get_agro_dashboard_context(current_user)
        return render_template("admin_agro.html", **context)

    @bp.route("/agro/clientes", methods=["GET"], endpoint="agro_clientes_listar")
    @login_required
    def agro_clientes_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = 12

        query = build_clientes_agro_query(current_user, q=q)
        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(max(1, page), total_pages)

        clientes = query.offset((page - 1) * per_page).limit(per_page).all()

        return render_template(
            "agro_clientes_listar.html",
            clientes=clientes,
            clientes_serializados=[serialize_cliente_agro(cliente) for cliente in clientes],
            filters={"q": q, "page": page, "total": total, "total_pages": total_pages},
            pagination_args=_query_args_without_page(),
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/clientes/cadastrar", methods=["GET", "POST"], endpoint="agro_cliente_novo")
    @login_required
    def agro_cliente_novo():
        _require_agro_edit()

        errors = {}
        form = _normalize_cliente_form(request.form if request.method == "POST" else {})

        if request.method == "POST":
            errors, doc_digits, doc_fmt, cep_digits = _validate_cliente_agro_form(form)
            if errors:
                flash("Corrija os campos destacados do cliente agro.", "warning")
                return render_template("agro_cliente_form.html", form=form, errors=errors, modo="novo")

            cliente = ClienteAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                documento=doc_digits,
                nome=form["nome"],
                cep=cep_digits,
                logradouro=form["logradouro"],
                numero=form["numero"],
                complemento=form["complemento"] or None,
                bairro=form["bairro"],
                cidade=form["cidade"],
                uf=form["uf"],
            )
            db.session.add(cliente)
            db.session.commit()

            flash(f"Cliente agro cadastrado com sucesso. Documento salvo como {doc_fmt}.", "success")
            return redirect(url_for("main.agro_clientes_listar"))

        return render_template("agro_cliente_form.html", form=form, errors=errors, modo="novo")

    @bp.route("/agro/clientes/<int:cliente_id>/editar", methods=["GET", "POST"], endpoint="agro_cliente_editar")
    @login_required
    def agro_cliente_editar(cliente_id):
        _require_agro_edit()
        cliente = _get_cliente_agro_or_404(cliente_id)

        errors = {}
        if request.method == "POST":
            form = _normalize_cliente_form(request.form)
            errors, doc_digits, doc_fmt, cep_digits = _validate_cliente_agro_form(form, cliente_atual=cliente)
            if errors:
                flash("Corrija os campos destacados do cliente agro.", "warning")
                return render_template(
                    "agro_cliente_form.html",
                    form=form,
                    errors=errors,
                    modo="editar",
                    cliente=cliente,
                )

            cliente.documento = doc_digits
            cliente.nome = form["nome"]
            cliente.cep = cep_digits
            cliente.logradouro = form["logradouro"]
            cliente.numero = form["numero"]
            cliente.complemento = form["complemento"] or None
            cliente.bairro = form["bairro"]
            cliente.cidade = form["cidade"]
            cliente.uf = form["uf"]
            db.session.commit()

            flash(f"Cliente agro atualizado com sucesso. Documento: {doc_fmt}", "success")
            return redirect(url_for("main.agro_clientes_listar"))

        form = {
            "nome": cliente.nome,
            "documento": format_documento(cliente.documento),
            "cep": format_cep(cliente.cep or ""),
            "logradouro": cliente.logradouro or "",
            "numero": cliente.numero or "",
            "complemento": cliente.complemento or "",
            "bairro": cliente.bairro or "",
            "cidade": cliente.cidade or "",
            "uf": cliente.uf or "",
        }
        return render_template("agro_cliente_form.html", form=form, errors=errors, modo="editar", cliente=cliente)

    @bp.route("/agro/clientes/<int:cliente_id>/deletar", methods=["POST"], endpoint="agro_cliente_deletar")
    @login_required
    def agro_cliente_deletar(cliente_id):
        _require_agro_edit()
        cliente = _get_cliente_agro_or_404(cliente_id)

        if cliente.orcamentos:
            flash("Não é possível excluir este cliente porque ele já possui orçamentos vinculados.", "warning")
            return redirect(url_for("main.agro_clientes_listar"))

        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_clientes_listar"))

    @bp.route("/agro/orcamentos", methods=["GET"], endpoint="agro_orcamentos_listar")
    @login_required
    def agro_orcamentos_listar():
        _require_agro_access()

        q = (request.args.get("q") or "").strip()
        cliente_id = request.args.get("cliente_id", type=int)
        mapeamento = (request.args.get("mapeamento") or "").strip().upper()
        page = request.args.get("page", 1, type=int)
        per_page = 12

        query = build_orcamentos_agro_query(current_user, q=q, cliente_id=cliente_id, mapeamento=mapeamento)
        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(max(1, page), total_pages)
        orcamentos = query.offset((page - 1) * per_page).limit(per_page).all()

        clientes = build_clientes_agro_query(current_user).all()
        return render_template(
            "agro_orcamentos_listar.html",
            orcamentos=orcamentos,
            clientes=clientes,
            agro_bool_label=agro_bool_label,
            filters={
                "q": q,
                "cliente_id": cliente_id,
                "mapeamento": mapeamento,
                "page": page,
                "total": total,
                "total_pages": total_pages,
            },
            pagination_args=_query_args_without_page(),
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/orcamentos/cadastrar", methods=["GET", "POST"], endpoint="agro_orcamento_novo")
    @login_required
    def agro_orcamento_novo():
        _require_agro_edit()
        clientes = build_clientes_agro_query(current_user).all()
        errors = {}
        form = _normalize_orcamento_form(request.form if request.method == "POST" else {})

        if request.method == "POST":
            errors, cliente, cep_digits, preco_base = _validate_orcamento_form(form)
            if errors:
                flash("Corrija os campos destacados do orçamento agro.", "warning")
                return render_template(
                    "agro_orcamento_form.html",
                    form=form,
                    errors=errors,
                    modo="novo",
                    clientes=clientes,
                )

            orcamento = OrcamentoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                nome_fazenda=form["nome_fazenda"],
                mapeamento=form["mapeamento"] == "SIM",
                risco_operacional=form["risco_operacional"] or None,
                cultura=form["cultura"] or None,
                protocolo=form["protocolo"] or None,
                preco_base=preco_base,
            )
            update_orcamento_snapshot_from_cliente(orcamento, cliente)
            orcamento.cep = cep_digits
            orcamento.logradouro = form["logradouro"]
            orcamento.numero = form["numero"]
            orcamento.complemento = form["complemento"] or None
            orcamento.bairro = form["bairro"]
            orcamento.cidade = form["cidade"]
            orcamento.uf = form["uf"]

            db.session.add(orcamento)
            db.session.flush()

            uploaded_file = request.files.get("anexo")
            if uploaded_file and uploaded_file.filename:
                try:
                    save_orcamento_attachment(orcamento, uploaded_file)
                except ValueError as exc:
                    db.session.rollback()
                    errors["anexo"] = str(exc)
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_orcamento_form.html",
                        form=form,
                        errors=errors,
                        modo="novo",
                        clientes=clientes,
                    )

            db.session.commit()
            flash("Orçamento agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_orcamentos_listar"))

        return render_template("agro_orcamento_form.html", form=form, errors=errors, modo="novo", clientes=clientes)

    @bp.route("/agro/orcamentos/<int:orcamento_id>/editar", methods=["GET", "POST"], endpoint="agro_orcamento_editar")
    @login_required
    def agro_orcamento_editar(orcamento_id):
        _require_agro_edit()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        clientes = build_clientes_agro_query(current_user).all()
        errors = {}

        if request.method == "POST":
            form = _normalize_orcamento_form(request.form)
            errors, cliente, cep_digits, preco_base = _validate_orcamento_form(form)
            if errors:
                flash("Corrija os campos destacados do orçamento agro.", "warning")
                return render_template(
                    "agro_orcamento_form.html",
                    form=form,
                    errors=errors,
                    modo="editar",
                    clientes=clientes,
                    orcamento=orcamento,
                )

            update_orcamento_snapshot_from_cliente(orcamento, cliente)
            orcamento.nome_fazenda = form["nome_fazenda"]
            orcamento.mapeamento = form["mapeamento"] == "SIM"
            orcamento.risco_operacional = form["risco_operacional"] or None
            orcamento.cultura = form["cultura"] or None
            orcamento.protocolo = form["protocolo"] or None
            orcamento.preco_base = preco_base
            orcamento.cep = cep_digits
            orcamento.logradouro = form["logradouro"]
            orcamento.numero = form["numero"]
            orcamento.complemento = form["complemento"] or None
            orcamento.bairro = form["bairro"]
            orcamento.cidade = form["cidade"]
            orcamento.uf = form["uf"]

            uploaded_file = request.files.get("anexo")
            if uploaded_file and uploaded_file.filename:
                try:
                    save_orcamento_attachment(orcamento, uploaded_file)
                except ValueError as exc:
                    db.session.rollback()
                    errors["anexo"] = str(exc)
                    flash(str(exc), "warning")
                    return render_template(
                        "agro_orcamento_form.html",
                        form=form,
                        errors=errors,
                        modo="editar",
                        clientes=clientes,
                        orcamento=orcamento,
                    )

            db.session.commit()
            flash("Orçamento agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_orcamentos_listar"))

        form = {
            "cliente_agro_id": str(orcamento.cliente_agro_id or ""),
            "nome_fazenda": orcamento.nome_fazenda or "",
            "mapeamento": "SIM" if orcamento.mapeamento else "NAO",
            "risco_operacional": orcamento.risco_operacional or "",
            "cultura": orcamento.cultura or "",
            "protocolo": orcamento.protocolo or "",
            "preco_base": format_currency_br(orcamento.preco_base),
            "cep": format_cep(orcamento.cep or ""),
            "logradouro": orcamento.logradouro or "",
            "numero": orcamento.numero or "",
            "complemento": orcamento.complemento or "",
            "bairro": orcamento.bairro or "",
            "cidade": orcamento.cidade or "",
            "uf": orcamento.uf or "",
        }
        return render_template(
            "agro_orcamento_form.html",
            form=form,
            errors=errors,
            modo="editar",
            clientes=clientes,
            orcamento=orcamento,
        )

    @bp.route("/agro/orcamentos/<int:orcamento_id>/anexo", endpoint="agro_orcamento_anexo")
    @login_required
    def agro_orcamento_anexo(orcamento_id):
        _require_agro_access()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        try:
            upload_folder, rel, download_name = resolve_orcamento_attachment(orcamento)
        except FileNotFoundError:
            abort(404)
        return send_from_directory(upload_folder, rel, as_attachment=False, download_name=download_name)

    @bp.route("/agro/orcamentos/<int:orcamento_id>/pdf", endpoint="agro_orcamento_pdf")
    @login_required
    def agro_orcamento_pdf(orcamento_id):
        _require_agro_access()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        pdf = build_orcamento_agro_pdf(orcamento)
        filename = f"orcamento_agro_{orcamento.id}.pdf"
        return send_file(pdf, mimetype="application/pdf", as_attachment=False, download_name=filename)

    @bp.route("/agro/orcamentos/<int:orcamento_id>/deletar", methods=["POST"], endpoint="agro_orcamento_deletar")
    @login_required
    def agro_orcamento_deletar(orcamento_id):
        _require_agro_edit()
        orcamento = _get_orcamento_agro_or_404(orcamento_id)
        remove_orcamento_attachment(orcamento)
        db.session.delete(orcamento)
        db.session.commit()
        flash("Orçamento agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_orcamentos_listar"))

    @bp.route("/agro/equipes", methods=["GET"], endpoint="agro_equipes_listar")
    @login_required
    def agro_equipes_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    EquipeAgro.nome.ilike(f"%{q}%"),
                    EquipeAgro.descricao.ilike(f"%{q}%"),
                )
            )
        equipes = query.order_by(EquipeAgro.nome.asc(), EquipeAgro.id.desc()).all()
        return render_template(
            "agro_equipes_listar.html",
            equipes=equipes,
            filters={"q": q, "total": len(equipes)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/equipes/cadastrar", methods=["GET", "POST"], endpoint="agro_equipe_nova")
    @login_required
    def agro_equipe_nova():
        _require_agro_edit()
        errors = {}
        form = _normalize_equipe_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, ativa = _validate_equipe_agro_form(form)
            if errors:
                flash("Corrija os campos destacados da equipe agro.", "warning")
                return render_template("agro_equipe_form.html", form=form, errors=errors, modo="novo")

            equipe = EquipeAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                nome=form["nome"],
                descricao=form["descricao"] or None,
                ativa=ativa,
            )
            db.session.add(equipe)
            db.session.commit()
            flash("Equipe agro cadastrada com sucesso.", "success")
            return redirect(url_for("main.agro_equipes_listar"))

        return render_template("agro_equipe_form.html", form=form, errors=errors, modo="novo")

    @bp.route("/agro/equipes/<int:equipe_id>/editar", methods=["GET", "POST"], endpoint="agro_equipe_editar")
    @login_required
    def agro_equipe_editar(equipe_id):
        _require_agro_edit()
        equipe = _get_equipe_agro_or_404(equipe_id)
        errors = {}
        if request.method == "POST":
            form = _normalize_equipe_form(request.form)
            errors, ativa = _validate_equipe_agro_form(form, equipe_atual=equipe)
            if errors:
                flash("Corrija os campos destacados da equipe agro.", "warning")
                return render_template("agro_equipe_form.html", form=form, errors=errors, modo="editar", equipe=equipe)

            equipe.nome = form["nome"]
            equipe.descricao = form["descricao"] or None
            equipe.ativa = ativa
            db.session.commit()
            flash("Equipe agro atualizada com sucesso.", "success")
            return redirect(url_for("main.agro_equipes_listar"))

        form = {
            "nome": equipe.nome or "",
            "descricao": equipe.descricao or "",
            "ativa": "SIM" if equipe.ativa else "NAO",
        }
        return render_template("agro_equipe_form.html", form=form, errors=errors, modo="editar", equipe=equipe)

    @bp.route("/agro/equipes/<int:equipe_id>/deletar", methods=["POST"], endpoint="agro_equipe_deletar")
    @login_required
    def agro_equipe_deletar(equipe_id):
        _require_agro_edit()
        equipe = _get_equipe_agro_or_404(equipe_id)
        if equipe.pilotos or equipe.equipamentos:
            flash("Não é possível excluir a equipe porque ela possui pilotos ou equipamentos vinculados.", "warning")
            return redirect(url_for("main.agro_equipes_listar"))
        db.session.delete(equipe)
        db.session.commit()
        flash("Equipe agro removida com sucesso.", "success")
        return redirect(url_for("main.agro_equipes_listar"))

    @bp.route("/agro/pilotos", methods=["GET"], endpoint="agro_pilotos_listar")
    @login_required
    def agro_pilotos_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(PilotoAgro.query, current_user, PilotoAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    PilotoAgro.nome.ilike(f"%{q}%"),
                    PilotoAgro.telefone.ilike(f"%{only_digits(q)}%") if only_digits(q) else db.false(),
                )
            )
        pilotos = query.order_by(PilotoAgro.nome.asc(), PilotoAgro.id.desc()).all()
        return render_template(
            "agro_pilotos_listar.html",
            pilotos=pilotos,
            filters={"q": q, "total": len(pilotos)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/pilotos/cadastrar", methods=["GET", "POST"], endpoint="agro_piloto_novo")
    @login_required
    def agro_piloto_novo():
        _require_agro_edit()
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        form = _normalize_piloto_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, telefone_digits, equipe_id, _equipe, ativo = _validate_piloto_agro_form(form, equipes)
            if errors:
                flash("Corrija os campos destacados do piloto agro.", "warning")
                return render_template("agro_piloto_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

            piloto = PilotoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                equipe_agro_id=equipe_id,
                nome=form["nome"],
                telefone=telefone_digits or None,
                ativo=ativo,
            )
            db.session.add(piloto)
            db.session.commit()
            flash("Piloto agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_pilotos_listar"))

        return render_template("agro_piloto_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

    @bp.route("/agro/pilotos/<int:piloto_id>/editar", methods=["GET", "POST"], endpoint="agro_piloto_editar")
    @login_required
    def agro_piloto_editar(piloto_id):
        _require_agro_edit()
        piloto = _get_piloto_agro_or_404(piloto_id)
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        if request.method == "POST":
            form = _normalize_piloto_form(request.form)
            errors, telefone_digits, equipe_id, _equipe, ativo = _validate_piloto_agro_form(form, equipes, piloto_atual=piloto)
            if errors:
                flash("Corrija os campos destacados do piloto agro.", "warning")
                return render_template("agro_piloto_form.html", form=form, errors=errors, modo="editar", piloto=piloto, equipes=equipes)

            piloto.nome = form["nome"]
            piloto.telefone = telefone_digits or None
            piloto.equipe_agro_id = equipe_id
            piloto.ativo = ativo
            db.session.commit()
            flash("Piloto agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_pilotos_listar"))

        form = {
            "nome": piloto.nome or "",
            "telefone": format_phone_br(piloto.telefone or ""),
            "equipe_agro_id": str(piloto.equipe_agro_id or ""),
            "ativo": "SIM" if piloto.ativo else "NAO",
        }
        return render_template("agro_piloto_form.html", form=form, errors=errors, modo="editar", piloto=piloto, equipes=equipes)

    @bp.route("/agro/pilotos/<int:piloto_id>/deletar", methods=["POST"], endpoint="agro_piloto_deletar")
    @login_required
    def agro_piloto_deletar(piloto_id):
        _require_agro_edit()
        piloto = _get_piloto_agro_or_404(piloto_id)
        db.session.delete(piloto)
        db.session.commit()
        flash("Piloto agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_pilotos_listar"))

    @bp.route("/agro/equipamentos", methods=["GET"], endpoint="agro_equipamentos_listar")
    @login_required
    def agro_equipamentos_listar():
        _require_agro_access()
        q = (request.args.get("q") or "").strip()
        query = apply_prefeitura_scope(EquipamentoAgro.query, current_user, EquipamentoAgro.prefeitura_id)
        if q:
            query = query.filter(
                db.or_(
                    EquipamentoAgro.tipo.ilike(f"%{q}%"),
                    EquipamentoAgro.modelo.ilike(f"%{q}%"),
                    EquipamentoAgro.identificacao.ilike(f"%{q}%"),
                    EquipamentoAgro.numero_serie.ilike(f"%{q}%"),
                )
            )
        equipamentos = query.order_by(EquipamentoAgro.identificacao.asc(), EquipamentoAgro.id.desc()).all()
        return render_template(
            "agro_equipamentos_listar.html",
            equipamentos=equipamentos,
            filters={"q": q, "total": len(equipamentos)},
            is_editable=can_edit_agro_panel(current_user),
        )

    @bp.route("/agro/equipamentos/cadastrar", methods=["GET", "POST"], endpoint="agro_equipamento_novo")
    @login_required
    def agro_equipamento_novo():
        _require_agro_edit()
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        form = _normalize_equipamento_form(request.form if request.method == "POST" else {})
        if request.method == "POST":
            errors, numero_serie, equipe_id, _equipe = _validate_equipamento_agro_form(form, equipes)
            if errors:
                flash("Corrija os campos destacados do equipamento agro.", "warning")
                return render_template("agro_equipamento_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

            equipamento = EquipamentoAgro(
                prefeitura_id=getattr(current_user, "prefeitura_id", None),
                equipe_agro_id=equipe_id,
                tipo=form["tipo"],
                modelo=form["modelo"],
                identificacao=form["identificacao"],
                numero_serie=numero_serie,
                status=form["status"],
            )
            db.session.add(equipamento)
            db.session.commit()
            flash("Equipamento agro cadastrado com sucesso.", "success")
            return redirect(url_for("main.agro_equipamentos_listar"))

        return render_template("agro_equipamento_form.html", form=form, errors=errors, modo="novo", equipes=equipes)

    @bp.route("/agro/equipamentos/<int:equipamento_id>/editar", methods=["GET", "POST"], endpoint="agro_equipamento_editar")
    @login_required
    def agro_equipamento_editar(equipamento_id):
        _require_agro_edit()
        equipamento = _get_equipamento_agro_or_404(equipamento_id)
        equipes = apply_prefeitura_scope(EquipeAgro.query, current_user, EquipeAgro.prefeitura_id).order_by(EquipeAgro.nome.asc()).all()
        errors = {}
        if request.method == "POST":
            form = _normalize_equipamento_form(request.form)
            errors, numero_serie, equipe_id, _equipe = _validate_equipamento_agro_form(form, equipes, equipamento_atual=equipamento)
            if errors:
                flash("Corrija os campos destacados do equipamento agro.", "warning")
                return render_template(
                    "agro_equipamento_form.html",
                    form=form,
                    errors=errors,
                    modo="editar",
                    equipamento=equipamento,
                    equipes=equipes,
                )

            equipamento.tipo = form["tipo"]
            equipamento.modelo = form["modelo"]
            equipamento.identificacao = form["identificacao"]
            equipamento.numero_serie = numero_serie
            equipamento.status = form["status"]
            equipamento.equipe_agro_id = equipe_id
            db.session.commit()
            flash("Equipamento agro atualizado com sucesso.", "success")
            return redirect(url_for("main.agro_equipamentos_listar"))

        form = {
            "tipo": equipamento.tipo or "",
            "modelo": equipamento.modelo or "",
            "identificacao": equipamento.identificacao or "",
            "numero_serie": equipamento.numero_serie or "",
            "status": equipamento.status or "Ativo",
            "equipe_agro_id": str(equipamento.equipe_agro_id or ""),
        }
        return render_template(
            "agro_equipamento_form.html",
            form=form,
            errors=errors,
            modo="editar",
            equipamento=equipamento,
            equipes=equipes,
        )

    @bp.route("/agro/equipamentos/<int:equipamento_id>/deletar", methods=["POST"], endpoint="agro_equipamento_deletar")
    @login_required
    def agro_equipamento_deletar(equipamento_id):
        _require_agro_edit()
        equipamento = _get_equipamento_agro_or_404(equipamento_id)
        db.session.delete(equipamento)
        db.session.commit()
        flash("Equipamento agro removido com sucesso.", "success")
        return redirect(url_for("main.agro_equipamentos_listar"))

    @bp.app_template_filter("agro_endereco")
    def agro_endereco_filter(obj):
        if obj is None:
            return ""
        return build_endereco_agro(
            getattr(obj, "cep", None),
            getattr(obj, "logradouro", None),
            getattr(obj, "numero", None),
            getattr(obj, "complemento", None),
            getattr(obj, "bairro", None),
            getattr(obj, "cidade", None),
            getattr(obj, "uf", None),
        )
