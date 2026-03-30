import math

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Clientes
from app.modules.clientes.service import (
    build_clientes_export,
    build_clientes_query,
    build_endereco_full,
    format_documento,
    format_phone_br,
    only_digits,
    serialize_clientes,
    validate_documento,
    validate_email,
)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def register_routes(bp):
    @bp.route("/clientes/cadastrar", methods=["GET", "POST"], endpoint="cadastrar_clientes")
    @login_required
    def cadastrar_clientes():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        errors = {}
        form = {}

        if request.method == "POST":
            nome_cliente = (request.form.get("nome_cliente") or "").strip()
            documento = (request.form.get("documento") or "").strip()
            contato = (request.form.get("contato") or "").strip()
            telefone = (request.form.get("telefone") or "").strip()
            email = (request.form.get("email") or "").strip()
            cep = (request.form.get("cep") or "").strip()
            logradouro = (request.form.get("logradouro") or "").strip()
            numero = (request.form.get("numero") or "").strip()
            complemento = (request.form.get("complemento") or "").strip()
            bairro = (request.form.get("bairro") or "").strip()
            cidade = (request.form.get("cidade") or "").strip()
            uf = (request.form.get("uf") or "").strip().upper()
            endereco_raw = (request.form.get("endereco") or "").strip()

            tem_endereco_novo = any([cep, logradouro, numero, complemento, bairro, cidade, uf])
            endereco_full = (
                build_endereco_full(cep, logradouro, numero, complemento, bairro, cidade, uf)
                if tem_endereco_novo
                else endereco_raw
            )

            form = {
                "nome_cliente": nome_cliente,
                "documento": documento,
                "contato": contato,
                "telefone": telefone,
                "email": email,
                "cep": cep,
                "logradouro": logradouro,
                "numero": numero,
                "complemento": complemento,
                "bairro": bairro,
                "cidade": cidade,
                "uf": uf,
                "endereco": endereco_full,
            }

            if not nome_cliente:
                errors["nome_cliente"] = "Informe o nome do cliente."
            if not documento:
                errors["documento"] = "Informe CPF ou CNPJ."

            doc_ok, doc_tipo, doc_digits, doc_fmt, doc_err = validate_documento(documento)
            if documento and not doc_ok:
                errors["documento"] = doc_err

            if email and not validate_email(email):
                errors["email"] = "E-mail invalido. Ex: nome@dominio.com"

            if telefone:
                tel_digits = only_digits(telefone)
                if len(tel_digits) not in (10, 11):
                    errors["telefone"] = "Telefone deve ter 10 ou 11 digitos (com DDD)."

            if cep:
                cep_digits = only_digits(cep)
                if len(cep_digits) != 8:
                    errors["cep"] = "CEP deve ter 8 digitos."

            if doc_ok:
                existe = Clientes.query.filter_by(documento=doc_digits).first()
                if existe:
                    errors["documento"] = f"Ja existe um cliente cadastrado com esse {doc_tipo}."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("cadastrar_clientes.html", form=form, errors=errors)

            novo = Clientes(
                nome_cliente=nome_cliente,
                documento=doc_digits,
                contato=contato or None,
                telefone=only_digits(telefone) or None,
                email=email or None,
                endereco=endereco_full or None,
            )

            db.session.add(novo)
            db.session.commit()

            flash(f"Cliente cadastrado com sucesso! Documento salvo como {doc_fmt}.", "success")
            return redirect(url_for("main.listar_clientes"))

        return render_template("cadastrar_clientes.html", form=form, errors=errors)

    @bp.route("/clientes", methods=["GET"], endpoint="listar_clientes")
    @login_required
    def listar_clientes():
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        q = (request.args.get("q") or "").strip()
        documento = (request.args.get("doc") or "").strip()
        email = (request.args.get("email") or "").strip()
        telefone = (request.args.get("telefone") or "").strip()
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

        query = build_clientes_query(q, documento, email, telefone, sort)

        if export == "xlsx":
            output, filename = build_clientes_export(query.all())
            return send_file(
                output,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        if page > total_pages:
            page = total_pages

        clientes_db = query.offset((page - 1) * per_page).limit(per_page).all()
        clientes = serialize_clientes(clientes_db)

        filters = {
            "q": q,
            "doc": documento,
            "email": email,
            "telefone": telefone,
            "sort": sort,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

        return render_template(
            "listar_clientes.html",
            clientes=clientes,
            filters=filters,
            pagination_args=_query_args_without_page(),
        )

    @bp.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"], endpoint="editar_cliente")
    @login_required
    def editar_cliente(cliente_id):
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        cliente = Clientes.query.get_or_404(cliente_id)
        errors = {}
        form = {}

        if request.method == "POST":
            nome_cliente = (request.form.get("nome_cliente") or "").strip()
            documento = (request.form.get("documento") or "").strip()
            contato = (request.form.get("contato") or "").strip()
            telefone = (request.form.get("telefone") or "").strip()
            email = (request.form.get("email") or "").strip()
            endereco = (request.form.get("endereco") or "").strip()

            form = {
                "nome_cliente": nome_cliente,
                "documento": documento,
                "contato": contato,
                "telefone": telefone,
                "email": email,
                "endereco": endereco,
            }

            if not nome_cliente:
                errors["nome_cliente"] = "Informe o nome do cliente."
            if not documento:
                errors["documento"] = "Informe CPF ou CNPJ."

            doc_ok, doc_tipo, doc_digits, doc_fmt, doc_err = validate_documento(documento)
            if documento and not doc_ok:
                errors["documento"] = doc_err

            if email and not validate_email(email):
                errors["email"] = "E-mail invalido. Ex: nome@dominio.com"

            if telefone:
                tel_digits = only_digits(telefone)
                if len(tel_digits) not in (10, 11):
                    errors["telefone"] = "Telefone deve ter 10 ou 11 digitos (com DDD)."

            if doc_ok:
                existe = (
                    Clientes.query
                    .filter(Clientes.documento == doc_digits, Clientes.id != cliente.id)
                    .first()
                )
                if existe:
                    errors["documento"] = f"Ja existe outro cliente com esse {doc_tipo}."

            if errors:
                flash("Corrija os campos destacados.", "warning")
                return render_template("editar_cliente.html", form=form, errors=errors, cliente=cliente)

            cliente.nome_cliente = nome_cliente
            cliente.documento = doc_digits
            cliente.contato = contato or None
            cliente.telefone = only_digits(telefone) or None
            cliente.email = email or None
            cliente.endereco = endereco or None

            db.session.commit()

            flash(f"Cliente atualizado! Documento: {doc_fmt}", "success")
            return redirect(url_for("main.listar_clientes"))

        form = {
            "nome_cliente": cliente.nome_cliente,
            "documento": format_documento(cliente.documento),
            "contato": cliente.contato or "",
            "telefone": format_phone_br(cliente.telefone or ""),
            "email": cliente.email or "",
            "endereco": cliente.endereco or "",
        }

        return render_template("editar_cliente.html", form=form, errors=errors, cliente=cliente)

    @bp.route("/clientes/<int:cliente_id>/deletar", methods=["POST"], endpoint="deletar_cliente")
    @login_required
    def deletar_cliente(cliente_id):
        if getattr(current_user, "tipo_usuario", None) != "admin":
            abort(403)

        cliente = Clientes.query.get_or_404(cliente_id)
        db.session.delete(cliente)
        db.session.commit()

        flash("Cliente removido com sucesso.", "success")
        return redirect(url_for("main.listar_clientes"))
