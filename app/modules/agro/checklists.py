import base64
import binascii
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from unicodedata import normalize

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.extensions import db
from app.models import ChecklistSemanalAgro, EquipamentoAgro
from app.modules.agenda_notificacoes import agora_brasilia_naive
from app.modules.agro.routes import _equipamento_agro_pode_ser_drone
from app.modules.gestao_ti.permissions import can_access_endpoint, route_access
from app.modules.piloto_checklists.service import (
    CHECKLIST_DRONE_BOOL_LABELS,
    CHECKLIST_DRONE_TEXT_GROUPS,
    CHECKLIST_VEICULO_BOOL_LABELS,
    CHECKLIST_VEICULO_TEXT_GROUPS,
)
from app.shared.access import get_user_prefeitura_id


ENDPOINT = "main.agro_piloto_checklist_semanal"
SIGNATURE_PREFIX = "data:image/png;base64,"
MAX_OBSERVACAO = 2000
GROUPS = {
    "veiculo": CHECKLIST_VEICULO_TEXT_GROUPS,
    "drone": CHECKLIST_DRONE_TEXT_GROUPS,
}
GROUP_TITLES = {
    "condicao_luzes_direcao": "Luzes de direção e iluminação",
    "condicao_luz_painel": "Luzes do painel",
    "condicao_itens_manutencao": "Manutenção preventiva",
    "condicao_embreagem_freios": "Embreagem e freios",
    "condicao_vidros_retrovisores": "Vidros e retrovisores",
    "condicao_pneus_estepe": "Pneus e itens de apoio",
    "condicao_itens_seguranca": "Itens de segurança",
    "condicao_itens_carro_interno": "Itens internos do carro",
    "condicao_giroflex_isqueiro_carregador": "Giroflex, isqueiro e carregador",
    "condicao_lataria": "Lataria",
    "condicao_lataria_portas": "Portas",
    "condicao_itens_carro_externo": "Para-choques e externos",
    "condicao_helices": "Hélices",
    "condicao_estrutura": "Tanque, trem de pouso e câmeras",
    "condicao_carregador_bateria": "Energia e carregamento",
    "condicao_cabos_correia": "Cabos e correia",
}
ITEM_LABELS = dict(CHECKLIST_VEICULO_BOOL_LABELS + CHECKLIST_DRONE_BOOL_LABELS)
ITEM_LABELS.update({
    "farois_funcionando": "Faróis", "limpador_parabrisa": "Limpador de para-brisa",
    "agua_radiador": "Água do radiador", "oleo_motor": "Óleo do motor", "triangulo": "Triângulo",
    "cinto_seguranca": "Cinto de segurança", "radio": "Rádio",
    "parachoque_frontal": "Para-choque frontal", "parachoque_traseiro": "Para-choque traseiro",
    "helices_status": "Hélices", "cameras": "Câmeras", "correia_pescoco": "Correia de pescoço",
})


def _normalized(value):
    return normalize("NFKD", value or "").encode("ascii", "ignore").decode().strip().lower()


def _team_equipment(user, equipe):
    options = {"veiculo": {}, "drone": {}}
    tenant = get_user_prefeitura_id(user)
    if equipe is None or not equipe.ativa or (tenant is not None and equipe.prefeitura_id != tenant):
        return options

    equipment = EquipamentoAgro.query.filter(
        EquipamentoAgro.equipe_agro_id == equipe.id,
        db.or_(EquipamentoAgro.prefeitura_id.is_(None), EquipamentoAgro.prefeitura_id == equipe.prefeitura_id),
    ).order_by(EquipamentoAgro.identificacao, EquipamentoAgro.id).all()
    for item in equipment:
        if _normalized(item.status) not in {"ativo", "operacional"}:
            continue
        tipo = _normalized(item.tipo)
        if tipo.partition(" ")[0] in {
            "veiculo", "carro", "caminhonete", "caminhao", "picape", "pickup", "automovel", "utilitario", "van",
        }:
            options["veiculo"][str(item.id)] = item
        elif _equipamento_agro_pode_ser_drone(item) and (
            "drone" in tipo or _normalized(item.funcao_operacional) in {"pulverizacao", "mapeamento"}
        ):
            options["drone"][str(item.id)] = item
    return options


def _has_tank(drone):
    tipo = _normalized(drone.tipo)
    funcao = _normalized(drone.funcao_operacional)
    return bool(drone.capacidade_tanque_l or "pulveriza" in tipo or funcao == "pulverizacao")


def _valid_signature(signature):
    if not signature.startswith(SIGNATURE_PREFIX) or len(signature) > 160_000:
        return False
    try:
        raw = base64.b64decode(signature[len(SIGNATURE_PREFIX):], validate=True)
        with Image.open(BytesIO(raw), formats=["PNG"]) as image:
            return image.size == (640, 160) and image.convert("RGBA").getchannel("A").getbbox() is not None
    except (binascii.Error, OSError, ValueError, Image.DecompressionBombError):
        return False


def validate_inspection(kind, form, errors, *, has_tank=False):
    answers = {}
    for group, fields in GROUPS[kind].items():
        applicable = [field for field in fields if field != "tanque" or has_tank]
        missing = [field for field in applicable if form.get(field) not in {"0", "1"}]
        if missing:
            errors.append("Marque a condição de " + ", ".join(ITEM_LABELS[field] for field in missing) + ".")
        answers.update({field: form.get(field) == "1" for field in applicable})
        if any(form.get(field) == "0" for field in applicable):
            description = form.get(group, "").strip()
            if not 1 <= len(description) <= MAX_OBSERVACAO:
                errors.append(f"Descreva o defeito em {GROUP_TITLES[group]} (até {MAX_OBSERVACAO} caracteres).")
            answers[group] = description

    if kind == "veiculo":
        try:
            km = Decimal(form.get("km_leitura", "").strip().replace(",", "."))
            if not km.is_finite() or not 0 <= km <= Decimal("9999999.99") or km != km.quantize(Decimal("0.01")):
                raise InvalidOperation
            answers["km_leitura"] = float(km)
        except InvalidOperation:
            errors.append("Informe uma quilometragem válida, com até duas casas decimais.")
    else:
        for field, label in (("num_baterias", "Número de baterias"), ("num_baterias_wb", "Baterias WB")):
            count = form.get(field, type=int)
            if count is None or not 0 <= count <= 9999:
                errors.append(f"Informe uma quantidade entre 0 e 9999 em {label}.")
            answers[field] = count
        observation = form.get("observacoes_equipamento", "").strip()
        if len(observation) > MAX_OBSERVACAO:
            errors.append(f"Use até {MAX_OBSERVACAO} caracteres nas observações do equipamento.")
        answers["observacoes_equipamento"] = observation
    return answers


def _save_records(piloto, equipe, week, now, records, name, signature):
    insert = postgresql_insert if db.session.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(ChecklistSemanalAgro).values([
        {
            "prefeitura_id": equipe.prefeitura_id, "equipe_agro_id": equipe.id, "piloto_agro_id": piloto.id,
            "semana_inicio": week, "equipamento_agro_id": item.id, "data_registro": now,
            "tipo": kind, "equipamento_identificacao": item.identificacao, "equipamento_modelo": item.modelo,
            "nome_responsavel": name, "assinatura_piloto": signature, "respostas": answers,
        }
        for kind, item, answers in records
    ])
    db.session.execute(statement.on_conflict_do_update(
        index_elements=("piloto_agro_id", "equipe_agro_id", "semana_inicio", "equipamento_agro_id"),
        set_={key: statement.excluded[key] for key in (
            "prefeitura_id", "data_registro", "tipo", "equipamento_identificacao", "equipamento_modelo",
            "nome_responsavel", "assinatura_piloto", "respostas",
        )},
    ))
    db.session.commit()


def register_routes(bp):
    @bp.route("/agro/piloto/checklists/semanais", methods=["GET", "POST"])
    @login_required
    def agro_piloto_checklist_semanal():
        piloto = current_user.piloto_agro
        if current_user.tipo_usuario != "piloto_agro" or not piloto or not piloto.ativo or not route_access(current_user, True):
            abort(403)

        equipe = piloto.equipe
        options = _team_equipment(current_user, equipe)
        now = agora_brasilia_naive()
        week = now.date() - timedelta(days=now.weekday())
        errors = []
        draft = None
        can_save = can_access_endpoint(current_user, ENDPOINT, "POST")
        name = piloto.nome
        signature = ""

        if request.method == "POST":
            if not can_access_endpoint(current_user, ENDPOINT):
                abort(403)
            form = request.form
            name = form.get("nome_responsavel", "").strip()
            if not 1 <= len(name) <= 150:
                errors.append("Informe o nome do responsável, com até 150 caracteres.")
            signature = form.get("assinatura_piloto", "")
            if not _valid_signature(signature):
                errors.append("Assine o checklist no quadro de assinatura.")
                signature = ""
            records = []
            draft = {}
            for kind, choices in options.items():
                selected_id = form.get(f"{kind}_id", "")
                item = choices.get(selected_id)
                if selected_id and item is None:
                    label = "veículo" if kind == "veiculo" else "drone"
                    errors.append(f"Selecione um {label} disponível da sua equipe.")
                elif item is not None:
                    answers = validate_inspection(kind, form, errors, has_tank=kind == "drone" and _has_tank(item))
                    records.append((kind, item, answers))
                draft[kind] = {"id": selected_id if item else "", "fields": {}}
                if item is not None:
                    fields = GROUPS[kind].keys() | {field for group in GROUPS[kind].values() for field in group}
                    extra_fields = ({"km_leitura"} if kind == "veiculo" else
                                    {"num_baterias", "num_baterias_wb", "observacoes_equipamento"})
                    draft[kind]["fields"] = {field: form.get(field, "")[:MAX_OBSERVACAO] for field in fields | extra_fields}
            if not records:
                errors.append("Selecione pelo menos um veículo ou um drone.")
            if not errors:
                _save_records(piloto, equipe, week, now, records, name, signature)
                flash("Checklist semanal salvo com sucesso.", "success")
                return redirect(url_for(ENDPOINT, **{f"{kind}_id": draft[kind]["id"] for kind in options}), code=303)

        selected = {}
        for kind, choices in options.items():
            if draft is not None:
                selected[kind] = draft[kind]["id"]
            else:
                default = next(iter(choices)) if len(choices) == 1 else ""
                selected_id = request.args.get(f"{kind}_id", default)
                selected[kind] = selected_id if selected_id in choices else ""

        saved = {}
        ids = [int(equipment_id) for choices in options.values() for equipment_id in choices]
        if ids:
            saved = {
                str(row.equipamento_agro_id): {
                    "fields": row.respostas, "savedAt": row.data_registro.strftime("%d/%m/%Y às %H:%M"),
                    "responsible": row.nome_responsavel,
                }
                for row in ChecklistSemanalAgro.query.filter_by(
                    piloto_agro_id=piloto.id, equipe_agro_id=equipe.id, semana_inicio=week,
                ).filter(ChecklistSemanalAgro.equipamento_agro_id.in_(ids))
            }

        return render_template(
            "piloto_agro_checklist_semanal.html", options=options, selected=selected, saved=saved, draft=draft,
            groups=GROUPS, titles=GROUP_TITLES, labels=ITEM_LABELS, has_tank=_has_tank,
            errors=errors, can_save=can_save, name=name, signature=signature,
            week=week, week_end=week + timedelta(days=6), max_observation=MAX_OBSERVACAO,
        ), 422 if errors else 200
