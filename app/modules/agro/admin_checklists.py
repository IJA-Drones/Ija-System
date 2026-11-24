import hashlib
import json
from datetime import date, datetime, time

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import defer

from app.extensions import db
from app.models import ChecklistSemanalAgro, EquipamentoAgro, EquipeAgro, PilotoAgro
from app.modules.admin_checklists.service import build_admin_checklists_totals, group_admin_checklists_by_week
from app.modules.agro.checklists import GROUPS, GROUP_TITLES, ITEM_LABELS, MAX_OBSERVACAO, SIGNATURE_PREFIX, validate_inspection
from app.modules.agro.service import can_access_agro_panel, can_edit_agro_panel
from app.modules.auditoria.recorder import mark_outcome
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.shared.access import apply_prefeitura_scope, normalize_role
from app.shared.query_filters import id_search_clause


LIST_ENDPOINT = "main.agro_checklists_semanais"
DETAIL_ENDPOINT = "main.agro_checklist_semanal_detalhe"
EDIT_ENDPOINT = "main.agro_checklist_semanal_editar"


def _require_admin(*, correction=False):
    legacy = can_edit_agro_panel(current_user) if correction else can_access_agro_panel(current_user)
    if normalize_role(current_user.tipo_usuario) == "piloto_agro" or not route_access(current_user, legacy):
        abort(403)


def _scope():
    query = ChecklistSemanalAgro.query.filter(ChecklistSemanalAgro.tipo.in_(GROUPS))
    return apply_prefeitura_scope(query, current_user, ChecklistSemanalAgro.prefeitura_id)


def _with_labels(query):
    record = ChecklistSemanalAgro
    return query.outerjoin(PilotoAgro, db.and_(
        PilotoAgro.id == record.piloto_agro_id,
        PilotoAgro.prefeitura_id.is_not_distinct_from(record.prefeitura_id),
    )).outerjoin(EquipeAgro, db.and_(
        EquipeAgro.id == record.equipe_agro_id,
        EquipeAgro.prefeitura_id.is_not_distinct_from(record.prefeitura_id),
    )).outerjoin(EquipamentoAgro, db.and_(
        EquipamentoAgro.id == record.equipamento_agro_id,
        db.or_(EquipamentoAgro.prefeitura_id == record.prefeitura_id, db.and_(
            EquipamentoAgro.prefeitura_id.is_(None), EquipamentoAgro.equipe_agro_id == record.equipe_agro_id,
        )),
    )).add_columns(PilotoAgro.nome, EquipeAgro.nome, EquipamentoAgro.numero_serie)


def _iso_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _labels(checklist):
    groups = GROUPS[checklist.tipo]
    bool_labels = [(field, ITEM_LABELS[field]) for fields in groups.values() for field in fields
                   if field != "tanque" or "tanque" in checklist.respostas]
    text_labels = [(field, GROUP_TITLES[field]) for field in groups]
    if checklist.tipo == "drone":
        text_labels.append(("observacoes_equipamento", "Observações do equipamento"))
    return bool_labels, text_labels


def _record(checklist, pilot_name, team_name, serial, *, show_signature=False):
    answers = checklist.respostas
    bool_labels, text_labels = _labels(checklist)
    items = [{"label": label, "ok": answers.get(field) is True} for field, label in bool_labels]
    notes = [{"label": label, "value": answers[field]} for field, label in text_labels if answers.get(field)]
    failures = sum(not item["ok"] for item in items)
    if checklist.piloto_agro_id:
        actor_id, actor_type, actor_label = checklist.piloto_agro_id, "piloto", "Piloto"
        actor_name = pilot_name or checklist.nome_responsavel
    elif checklist.equipe_agro_id:
        actor_id, actor_type, actor_label = checklist.equipe_agro_id, "equipe", "Equipe"
        actor_name = team_name or checklist.nome_responsavel
    else:
        actor_id, actor_type, actor_label = checklist.id, "registro", "Responsável"
        actor_name = checklist.nome_responsavel

    vehicle = checklist.tipo == "veiculo"
    meta = [
        ("Placa" if vehicle else "Código do drone", checklist.equipamento_identificacao),
        ("Modelo", checklist.equipamento_modelo),
        ("Equipe", team_name or "-"),
        ("Responsável informado", checklist.nome_responsavel),
    ]
    if vehicle:
        km = answers.get("km_leitura")
        meta.append(("Quilometragem", f"{km:.2f} km" if km is not None else "-"))
    else:
        meta.extend([("Série", serial or "-"), ("Baterias", answers.get("num_baterias", "-")),
                     ("Baterias WB", answers.get("num_baterias_wb", "-"))])

    signature = checklist.assinatura_piloto if show_signature else ""
    return {
        "id": checklist.id, "tipo": checklist.tipo, "tipo_label": "Veículo" if vehicle else "Drone",
        "data_registro": checklist.data_registro, "semana_inicio": checklist.semana_inicio,
        "actor_type": actor_type, "actor_id": actor_id, "actor_label": actor_label, "piloto_nome": actor_name,
        "titulo": checklist.equipamento_modelo, "subtitulo": checklist.equipamento_identificacao,
        "complemento": team_name if vehicle else serial,
        "status_label": f"{failures} pendência(s)" if failures else "Conforme",
        "falhas": failures, "itens_ok": len(items) - failures, "itens_total": len(items),
        "observacoes_total": len(notes), "meta": [{"label": label, "value": value} for label, value in meta],
        "detalhes_itens": items, "observacoes": notes,
        "assinatura": signature if signature and signature.startswith(SIGNATURE_PREFIX) else "",
    }


def _revision(checklist):
    content = json.dumps([checklist.data_registro.isoformat(), checklist.respostas], sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def register_routes(bp):
    @bp.get("/agro/checklists/semanais")
    @login_required
    def agro_checklists_semanais():
        _require_admin()
        filters = {field: request.args.get(field, "").strip() for field in ("q", "data_inicio", "data_fim")}
        record = ChecklistSemanalAgro
        query = _with_labels(_scope().options(defer(record.assinatura_piloto)))
        q = filters["q"]
        if q:
            match = f"%{q}%"
            query = query.filter(db.or_(
                id_search_clause(record.id, q), id_search_clause(record.equipamento_agro_id, q),
                id_search_clause(record.piloto_agro_id, q), id_search_clause(record.equipe_agro_id, q),
                PilotoAgro.nome.ilike(match), EquipeAgro.nome.ilike(match), EquipamentoAgro.numero_serie.ilike(match),
                record.nome_responsavel.ilike(match), record.equipamento_identificacao.ilike(match),
                record.equipamento_modelo.ilike(match),
            ))
        if start := _iso_date(filters["data_inicio"]):
            query = query.filter(record.data_registro >= datetime.combine(start, time.min))
        if end := _iso_date(filters["data_fim"]):
            query = query.filter(record.data_registro <= datetime.combine(end, time.max))
        groups = group_admin_checklists_by_week(_record(*row) for row in query.order_by(record.data_registro.desc(), record.id.desc()))
        for group in groups:
            anchor = (group["veiculos"] or group["drones"])[0]
            group["detalhe_url"] = url_for(DETAIL_ENDPOINT, checklist_id=anchor["id"])
        return render_template(
            "admin_checklists_semanais.html", grupos=groups, totais=build_admin_checklists_totals(groups), filters=filters,
            lista_url=url_for(LIST_ENDPOINT), central_url=url_for("main.admin_agro"), checklist_agro=True,
        )

    @bp.get("/agro/checklists/semanais/<int:checklist_id>")
    @login_required
    def agro_checklist_semanal_detalhe(checklist_id):
        _require_admin()
        record = ChecklistSemanalAgro
        anchor = _scope().filter_by(id=checklist_id).first_or_404()
        query = _scope().filter_by(semana_inicio=anchor.semana_inicio)
        if anchor.piloto_agro_id is not None:
            query = query.filter_by(piloto_agro_id=anchor.piloto_agro_id)
        elif anchor.equipe_agro_id is not None:
            query = query.filter_by(piloto_agro_id=None, equipe_agro_id=anchor.equipe_agro_id)
        else:
            query = query.filter_by(id=anchor.id)

        records = [_record(*row, show_signature=True)
                   for row in _with_labels(query).order_by(record.data_registro.desc(), record.id.desc())]
        if not records:
            abort(404)
        group = group_admin_checklists_by_week(records)[0]
        can_correct = can_access_endpoint(current_user, EDIT_ENDPOINT, legacy=can_edit_agro_panel(current_user))
        for item in records:
            item["editar_url"] = url_for(EDIT_ENDPOINT, checklist_id=item["id"])
            item["pode_corrigir"] = can_correct
        totals = {"veiculo": len(group["veiculos"]), "drone": len(group["drones"]), "pendencias": group["falhas"],
                  "itens_ok": group["itens_ok"], "itens_total": group["itens_total"]}
        return render_template("admin_checklist_semanal_detalhe.html", **group, totais=totals, lista_url=url_for(LIST_ENDPOINT))

    @bp.route("/agro/checklists/<int:checklist_id>/editar", methods=["GET", "POST"])
    @login_required
    def agro_checklist_semanal_editar(checklist_id):
        _require_admin(correction=True)
        query = _scope().filter_by(id=checklist_id)
        if request.method == "POST":
            query = query.with_for_update(of=ChecklistSemanalAgro)
        row = _with_labels(query).first_or_404()
        checklist = row[0]
        back = url_for(DETAIL_ENDPOINT, checklist_id=checklist_id)
        revision = _revision(checklist)
        errors = []
        form_data = {}
        status = 200
        if request.method == "POST":
            if revision != request.form.get("checklist_revision"):
                errors.append("O checklist mudou desde que você abriu a tela. Revise os dados atuais e tente novamente.")
                status = 409
            else:
                form_data = request.form
                answers = validate_inspection(checklist.tipo, form_data, errors, has_tank="tanque" in checklist.respostas)
                if errors:
                    status = 400
                else:
                    checklist.respostas = answers
                    db.session.commit()
                    mark_outcome("CHECKLIST_AGRO_CORRIGIDO", "SUCESSO")
                    flash("Checklist corrigido com sucesso.", "success")
                    return redirect(back, code=303)

        bool_labels, text_labels = _labels(checklist)
        item = _record(*row)
        return render_template(
            "admin_checklist_editar.html", registro=item, actor_nome=item["piloto_nome"],
            checklist={**checklist.respostas, "data_registro": checklist.data_registro},
            bool_labels=bool_labels, text_labels=text_labels, voltar_url=back, form_data=form_data,
            checklist_revision=revision, errors=errors, max_observation=MAX_OBSERVACAO,
        ), status
