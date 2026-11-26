import json
import os
import re
import uuid
from datetime import date, datetime, timezone

from werkzeug.utils import secure_filename
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Baterias, ControlesRemotos, Drones, Equipamentos, Equipe, EquipePiloto, EstoquePeca, ManutencaoEquipamento, ManutencaoPecaUso, Veiculos
from app.shared.access import apply_prefeitura_scope, resolve_linked_prefeitura
from app.shared.maintenance_time import to_sao_paulo
from app.shared.equipment_models import part_matches_equipment
from app.shared.skybox import (
    SkyboxError,
    build_manutencao_media_remote_path,
    delete_skybox_file,
    is_skybox_path,
    upload_file_to_skybox,
)


MANUTENCAO_STATUS = "Em Manuten\u00e7\u00e3o"


def maintenance_overview(user, now=None):
    current = to_sao_paulo(now or datetime.now(timezone.utc))
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    utc_day = day_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_month = month_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_now = current.astimezone(timezone.utc).replace(tzinfo=None)
    orders = apply_prefeitura_scope(ManutencaoEquipamento.query, user, ManutencaoEquipamento.prefeitura_id)
    uses = apply_prefeitura_scope(ManutencaoPecaUso.query, user, ManutencaoPecaUso.prefeitura_id)
    return dict(
        abertas_hoje=orders.filter(ManutencaoEquipamento.aberta_em >= utc_day, ManutencaoEquipamento.aberta_em <= utc_now).count(),
        concluidas_mes=orders.filter(ManutencaoEquipamento.encerrada_em >= utc_month, ManutencaoEquipamento.encerrada_em <= utc_now).count(),
        pecas_mes=uses.with_entities(db.func.coalesce(db.func.sum(ManutencaoPecaUso.quantidade_usada), 0)).filter(
            ManutencaoPecaUso.criado_em >= utc_month, ManutencaoPecaUso.criado_em <= utc_now).scalar(),
    )
MANUTENCAO_STATUS_ALIASES = (
    MANUTENCAO_STATUS,
    "Manuten\u00e7\u00e3o",
    "Manutencao",
    "Em Manutencao",
)
MANUTENCAO_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
MANUTENCAO_IMAGE_MAX_BYTES = 12 * 1024 * 1024
MANUTENCAO_IMAGE_MAX_COUNT = 10
SIGNATURE_DATA_URL = re.compile(r"^data:image/png;base64,[A-Za-z0-9+/]+={0,2}$")


def _search_equipment(query, model, q):
    term = (q or "").strip()
    if term:
        query = query.filter(db.or_(
            model.numero_serie.icontains(term, autoescape=True),
            model.renomacao.icontains(term, autoescape=True),
            model.modelo.icontains(term, autoescape=True),
        ))
    return query


def list_equipamentos_dashboard(user=None, q=None):
    query = Equipamentos.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
    return {
        "equipamentos": _search_equipment(query, Equipamentos, q).order_by(Equipamentos.criado_em.desc()).all(),
        "total_drones": query.filter_by(tipo_equipamento="drones").count(),
        "total_baterias": query.filter_by(tipo_equipamento="baterias").count(),
        "total_controles": query.filter_by(tipo_equipamento="controles_remotos").count(),
        "em_manutencao": query.filter(Equipamentos.status.in_(MANUTENCAO_STATUS_ALIASES)).count(),
    }


def list_drones(user=None, q=None):
    query = Drones.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
    return _search_equipment(query, Drones, q).order_by(Drones.renomacao, Drones.id).all()


def list_baterias(user=None, q=None):
    query = Baterias.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Baterias.prefeitura_id)
    return _search_equipment(query, Baterias, q).options(selectinload(Baterias.drone_vinculado)).order_by(Baterias.renomacao, Baterias.id).all()


def equipment_team_assignments(equipamentos, *, user):
    """Resolve the current team roster without storing a second responsible person.

    A linked battery follows its drone's team. Vehicles are team allocations,
    not a claim that one particular vehicle is transporting the equipment.
    """
    sources = {}
    equipment_by_id = {equipment.id: equipment for equipment in equipamentos}
    for equipamento in equipamentos:
        source = equipamento
        if isinstance(equipamento, (Baterias, ControlesRemotos)) and equipamento.drone_id is not None:
            source = equipamento.drone_vinculado
        if source is not None and (source.prefeitura_id is None or equipamento.prefeitura_id is None
                                   or source.prefeitura_id == equipamento.prefeitura_id):
            sources[equipamento.id] = source
    team_ids = {source.equipe_id for source in sources.values() if source.equipe_id is not None}
    if not team_ids:
        return {}
    teams = apply_prefeitura_scope(Equipe.query, user, Equipe.prefeitura_id).filter(Equipe.id.in_(team_ids)).options(
        selectinload(Equipe.membros).joinedload(EquipePiloto.piloto),
    ).all()
    teams_by_id = {team.id: team for team in teams}
    vehicles = apply_prefeitura_scope(Veiculos.query, user, Veiculos.prefeitura_id).filter(
        Veiculos.equipe_id.in_(team_ids),
    ).order_by(Veiculos.placa, Veiculos.id).all()
    vehicles_by_team = {}
    for vehicle in vehicles:
        team = teams_by_id.get(vehicle.equipe_id)
        if team is not None and vehicle.prefeitura_id in (None, team.prefeitura_id):
            vehicles_by_team.setdefault(team.id, []).append(vehicle)
    assignments = {}
    for equipment_id, source in sources.items():
        team = teams_by_id.get(source.equipe_id)
        if team is None or source.prefeitura_id not in (None, team.prefeitura_id):
            continue
        if equipment_by_id[equipment_id].prefeitura_id not in (None, team.prefeitura_id):
            continue
        def team_member(role):
            return next((member.piloto for member in team.membros
                         if member.papel == role and member.piloto is not None
                         and member.piloto.prefeitura_id == team.prefeitura_id), None)
        assignments[equipment_id] = dict(
            equipe=team, piloto=team_member("piloto"), auxiliar=team_member("auxiliar"),
            veiculos=vehicles_by_team.get(team.id, []),
        )
    return assignments


def list_active_equipes(user=None):
    query = Equipe.query.filter_by(ativa=True)
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipe.prefeitura_id)
    return query.order_by(Equipe.nome_equipe.asc()).all()


def list_drones_for_baterias(user=None):
    query = Drones.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
    return query.order_by(Drones.renomacao.asc()).all()


def list_equipamentos_manutencao(user=None):
    query = Equipamentos.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
    return (
        query
        .filter(Equipamentos.status.in_(MANUTENCAO_STATUS_ALIASES))
        .order_by(Equipamentos.criado_em.desc())
        .all()
    )


def list_pecas_compativeis_manutencao(drone, user=None):
    query = EstoquePeca.query.filter(
        EstoquePeca.prefeitura_id == drone.prefeitura_id,
        EstoquePeca.arquivada_em.is_(None),
    )
    if user is not None:
        query = apply_prefeitura_scope(query, user, EstoquePeca.prefeitura_id)
    pecas = query.order_by(EstoquePeca.modelo_peca.asc(), EstoquePeca.numero_serie.asc()).all()
    return [p for p in pecas if part_matches_equipment(p, drone)]


def list_pecas_disponiveis_manutencao(drone, user=None):
    return [p for p in list_pecas_compativeis_manutencao(drone, user=user)
            if p.status == "disponivel_manutencao" and p.quantidade > 0]


def list_pecas_usadas_manutencao(drone, user=None):
    manutencao = get_manutencao_aberta(drone, user=user)
    query = ManutencaoPecaUso.query.filter(ManutencaoPecaUso.drone_id == drone.id)
    if manutencao:
        query = query.filter(ManutencaoPecaUso.manutencao_id == manutencao.id)
    else:
        query = query.filter(ManutencaoPecaUso.manutencao_id.is_(None))
    if user is not None:
        query = apply_prefeitura_scope(query, user, ManutencaoPecaUso.prefeitura_id)
    return query.order_by(ManutencaoPecaUso.criado_em.desc()).all()


def list_imagens_manutencao(manutencao):
    if not manutencao or not manutencao.imagens_ocorrido:
        return []
    try:
        values = json.loads(manutencao.imagens_ocorrido)
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and is_skybox_path(value)]


def _signature_value(raw, label, errors):
    value = (raw or "").strip()
    if not value:
        return None
    if len(value) > 2_000_000 or not SIGNATURE_DATA_URL.fullmatch(value):
        errors[label] = "Assinatura inválida. Desenhe novamente no campo de assinatura."
        return None
    return value


def _upload_maintenance_images(manutencao, uploads):
    files = [item for item in (uploads or []) if item and getattr(item, "filename", "")]
    if not files:
        return []
    if len(files) > MANUTENCAO_IMAGE_MAX_COUNT:
        raise ValueError(f"Envie no máximo {MANUTENCAO_IMAGE_MAX_COUNT} imagens por registro.")

    markers = []
    try:
        for upload in files:
            filename = secure_filename(upload.filename or "")
            extension = os.path.splitext(filename)[1].lower().lstrip(".")
            if not filename or extension not in MANUTENCAO_IMAGE_EXTENSIONS:
                raise ValueError("Envie imagens nos formatos JPG, JPEG ou PNG.")
            if upload.mimetype and upload.mimetype.lower() not in {"image/jpeg", "image/png"}:
                raise ValueError("O arquivo selecionado não é uma imagem JPG ou PNG.")
            try:
                current = upload.stream.tell()
                upload.stream.seek(0, os.SEEK_END)
                size = upload.stream.tell()
                upload.stream.seek(current)
            except (AttributeError, OSError):
                size = None
            if size is not None and size > MANUTENCAO_IMAGE_MAX_BYTES:
                raise ValueError("Cada imagem pode ter no máximo 12 MB.")
            stored_name = f"ocorrido_{uuid.uuid4().hex}.{extension}"
            remote_path = build_manutencao_media_remote_path(manutencao.id, stored_name)
            markers.append(upload_file_to_skybox(upload, remote_path))
    except Exception:
        for marker in markers:
            try:
                delete_skybox_file(marker)
            except SkyboxError:
                pass
        raise
    return markers


def get_manutencao_aberta(drone, user=None):
    query = ManutencaoEquipamento.query.filter(
        ManutencaoEquipamento.drone_id == drone.id,
        ManutencaoEquipamento.status == "aberta",
    )
    if user is not None:
        query = apply_prefeitura_scope(query, user, ManutencaoEquipamento.prefeitura_id)
    return query.order_by(ManutencaoEquipamento.aberta_em.desc()).first()


def get_or_create_manutencao_aberta(drone, user=None):
    manutencao = get_manutencao_aberta(drone, user=user)
    if manutencao:
        return manutencao

    manutencao = ManutencaoEquipamento(
        prefeitura_id=drone.prefeitura_id,
        drone_id=drone.id,
        aberta_por_id=getattr(user, "id", None),
        status="aberta",
        aberta_em=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(manutencao)
    return manutencao


def lock_maintenance_equipment(drone):
    """Serialize opening/finalization, including old drones without an OS."""
    row = db.session.execute(select(Equipamentos.id).where(Equipamentos.id == drone.id).with_for_update()).scalar_one_or_none()
    if row is None:
        raise ValueError("O equipamento não está mais disponível. Recarregue a página.")
    db.session.refresh(drone, attribute_names=["status"])


def list_historico_manutencoes(user=None):
    query = ManutencaoEquipamento.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, ManutencaoEquipamento.prefeitura_id)
    return query.order_by(ManutencaoEquipamento.aberta_em.desc(), ManutencaoEquipamento.id.desc()).all()


def get_manutencao_scoped_or_404(manutencao_id, user=None):
    query = ManutencaoEquipamento.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, ManutencaoEquipamento.prefeitura_id)
    return query.filter(ManutencaoEquipamento.id == manutencao_id).first_or_404()


def list_historico_pecas_usadas(user=None):
    query = ManutencaoPecaUso.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, ManutencaoPecaUso.prefeitura_id)
    return query.order_by(ManutencaoPecaUso.criado_em.desc(), ManutencaoPecaUso.id.desc()).all()


def registrar_pecas_usadas_manutencao(drone, form_data, *, user=None, files_data=None):
    """Compatibility entry point: the worksheet now controls draft/completion."""
    from app.modules.equipamentos.manutencao import salvar_atendimento_manutencao
    return salvar_atendimento_manutencao(drone, form_data, user=user, files_data=files_data)


def _parse_int(raw_value, *, min_value=None, max_value=None, error_message):
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_message) from exc

    if min_value is not None and value < min_value:
        raise ValueError(error_message)
    if max_value is not None and value > max_value:
        raise ValueError(error_message)
    return value


def _parse_float(raw_value, *, min_value=None, error_message):
    try:
        value = float(str(raw_value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(error_message) from exc

    if min_value is not None and value <= min_value:
        raise ValueError(error_message)
    return value


def _parse_optional_date(raw_value, *, error_message):
    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(error_message) from exc


def _validate_equipe_id(equipe_id_raw, *, user=None):
    if not equipe_id_raw:
        return None

    try:
        equipe_id = int(equipe_id_raw)
    except ValueError as exc:
        raise ValueError("Equipe invalida.") from exc

    query = Equipe.query.filter_by(id=equipe_id, ativa=True)
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipe.prefeitura_id)
    equipe = query.first()
    if not equipe:
        raise ValueError("Equipe invalida.")

    return equipe_id


def _validate_drone_id(drone_id_raw, *, user=None):
    if not drone_id_raw:
        return None

    try:
        drone_id = int(drone_id_raw)
    except ValueError as exc:
        raise ValueError("Drone invalido.") from exc

    query = Drones.query.filter(Drones.id == drone_id)
    if user is not None:
        query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
    if not query.first():
        raise ValueError("Drone invalido.")

    return drone_id


def validate_drone_form(form_data, *, existing_drone=None, user=None):
    errors = {}

    modelo = (form_data.get("modelo") or "").strip()
    renomacao = (form_data.get("renomacao") or "").strip()
    categoria = (form_data.get("categoria") or "").strip()
    status = (form_data.get("status") or "Ativo").strip()
    ano_fabricacao_raw = (form_data.get("ano_fabricacao") or "").strip()
    numero_serie = (form_data.get("numero_serie") or "").strip()
    registro_anatel = (form_data.get("registro_anatel") or "").strip()
    registro_anac = (form_data.get("registro_anac") or "").strip()
    pmd_kg_raw = (form_data.get("pmd_kg") or "").strip()
    equipe_id_raw = (form_data.get("equipe_id") or "").strip()
    ultima_manutencao_raw = (form_data.get("ultima_manutencao") or "").strip()

    form = {
        "modelo": modelo,
        "renomacao": renomacao,
        "categoria": categoria,
        "status": status,
        "ano_fabricacao": ano_fabricacao_raw,
        "numero_serie": numero_serie,
        "registro_anatel": registro_anatel,
        "registro_anac": registro_anac,
        "pmd_kg": pmd_kg_raw,
        "equipe_id": equipe_id_raw,
        "ultima_manutencao": ultima_manutencao_raw,
    }

    if not modelo:
        errors["modelo"] = "Informe o modelo do drone."
    if not renomacao:
        errors["renomacao"] = "Informe a renomacao do drone."
    if not registro_anatel:
        errors["registro_anatel"] = "Informe o registro ANATEL."
    if not registro_anac:
        errors["registro_anac"] = "Informe o registro ANAC."
    if not pmd_kg_raw:
        errors["pmd_kg"] = "Informe o PMD (kg)."

    pmd_kg = None
    if pmd_kg_raw:
        try:
            pmd_kg = _parse_float(pmd_kg_raw, min_value=0, error_message="PMD invalido. Use um numero (ex: 25.5).")
        except ValueError as exc:
            errors["pmd_kg"] = str(exc)

    ano_fabricacao = None
    if ano_fabricacao_raw:
        try:
            ano_fabricacao = _parse_int(
                ano_fabricacao_raw,
                min_value=1900,
                max_value=2100,
                error_message="Ano de fabricacao invalido.",
            )
        except ValueError as exc:
            errors["ano_fabricacao"] = str(exc)

    equipe_id = None
    if equipe_id_raw:
        try:
            equipe_id = _validate_equipe_id(equipe_id_raw, user=user)
            if existing_drone is not None:
                resolve_linked_prefeitura(existing_drone.prefeitura_id, db.session.get(Equipe, equipe_id))
        except ValueError as exc:
            errors["equipe_id"] = str(exc)

    ultima_manutencao = None
    if ultima_manutencao_raw:
        try:
            ultima_manutencao = _parse_optional_date(
                ultima_manutencao_raw,
                error_message="Data invalida.",
            )
        except ValueError as exc:
            errors["ultima_manutencao"] = str(exc)

    if registro_anac and not errors.get("registro_anac"):
        query = Drones.query.filter(Drones.registro_anac == registro_anac)
        if existing_drone is not None:
            query = query.filter(Drones.id != existing_drone.id)
        if query.first():
            errors["registro_anac"] = (
                "Ja existe outro drone com esse ANAC."
                if existing_drone is not None
                else "Ja existe um drone com esse Registro ANAC."
            )

    if numero_serie:
        query = Equipamentos.query.filter(Equipamentos.numero_serie == numero_serie)
        if existing_drone is not None:
            query = query.filter(Equipamentos.id != existing_drone.id)
        if query.first():
            errors["numero_serie"] = (
                "Numero de serie ja utilizado."
                if existing_drone is not None
                else "Ja existe um equipamento com esse Numero de Serie."
            )

    cleaned = {
        "modelo": modelo,
        "renomacao": renomacao,
        "categoria": categoria or None,
        "status": status,
        "ano_fabricacao": ano_fabricacao,
        "numero_serie": numero_serie or None,
        "registro_anatel": registro_anatel,
        "registro_anac": registro_anac,
        "pmd_kg": pmd_kg,
        "equipe_id": equipe_id,
        "ultima_manutencao": ultima_manutencao,
    }

    return form, cleaned, errors


def create_drone(cleaned_data, *, prefeitura_id=None):
    if cleaned_data["equipe_id"]:
        prefeitura_id = resolve_linked_prefeitura(prefeitura_id, db.session.get(Equipe, cleaned_data["equipe_id"]))
    drone = Drones(
        tipo_equipamento="drones",
        status=cleaned_data["status"],
        modelo=cleaned_data["modelo"],
        renomacao=cleaned_data["renomacao"],
        categoria=cleaned_data["categoria"],
        ano_fabricacao=cleaned_data["ano_fabricacao"],
        numero_serie=cleaned_data["numero_serie"],
        ultima_manutencao=cleaned_data["ultima_manutencao"],
        equipe_id=cleaned_data["equipe_id"],
        prefeitura_id=prefeitura_id,
        registro_anatel=cleaned_data["registro_anatel"],
        registro_anac=cleaned_data["registro_anac"],
        pmd_kg=cleaned_data["pmd_kg"],
    )
    db.session.add(drone)
    db.session.commit()
    return drone


def update_drone(drone, cleaned_data):
    if cleaned_data["equipe_id"]:
        drone.prefeitura_id = resolve_linked_prefeitura(drone.prefeitura_id, db.session.get(Equipe, cleaned_data["equipe_id"]))
    drone.modelo = cleaned_data["modelo"]
    drone.renomacao = cleaned_data["renomacao"]
    drone.categoria = cleaned_data["categoria"]
    drone.status = cleaned_data["status"]
    drone.ano_fabricacao = cleaned_data["ano_fabricacao"]
    drone.numero_serie = cleaned_data["numero_serie"]
    drone.ultima_manutencao = cleaned_data["ultima_manutencao"]
    drone.equipe_id = cleaned_data["equipe_id"]
    drone.registro_anatel = cleaned_data["registro_anatel"]
    drone.registro_anac = cleaned_data["registro_anac"]
    drone.pmd_kg = cleaned_data["pmd_kg"]
    db.session.commit()
    return drone


def build_drone_edit_form(drone):
    return {
        "modelo": drone.modelo,
        "renomacao": drone.renomacao,
        "categoria": drone.categoria,
        "status": drone.status,
        "ano_fabricacao": drone.ano_fabricacao,
        "numero_serie": drone.numero_serie,
        "registro_anatel": drone.registro_anatel,
        "registro_anac": drone.registro_anac,
        "pmd_kg": drone.pmd_kg,
        "equipe_id": drone.equipe_id,
        "ultima_manutencao": drone.ultima_manutencao,
    }


def delete_drone(drone):
    if drone.controles_remotos:
        raise ValueError("Transfira os controles remotos vinculados antes de remover o drone.")
    for bateria in list(drone.baterias):
        bateria.drone_id = None

    db.session.flush()
    db.session.delete(drone)
    db.session.commit()


def send_drone_to_manutencao(drone, *, user=None, form_data=None):
    lock_maintenance_equipment(drone)
    if (drone.status or "").strip() in MANUTENCAO_STATUS_ALIASES:
        return False

    drone.status = MANUTENCAO_STATUS
    manutencao = get_or_create_manutencao_aberta(drone, user=user)
    if form_data is not None:
        manutencao.avarias_identificadas = (form_data.get("avarias_identificadas") or "").strip() or None
        manutencao.responsavel_manutencao = (form_data.get("responsavel_manutencao") or "").strip() or None
    db.session.commit()
    return True


def encerrar_manutencao_drone(drone, *, user=None):
    from app.modules.equipamentos.manutencao import build_manutencao_form, salvar_atendimento_manutencao
    from werkzeug.datastructures import MultiDict
    order = get_manutencao_aberta(drone, user=user)
    if order is None:
        return False
    form = build_manutencao_form(order)
    data = MultiDict({key: value for key, value in form.items() if key not in {"pecas_avariadas", "pecas_reparo"}})
    data["drone_testado"] = "1" if form["drone_testado"] else "0"
    data["acao"] = "concluir"
    for row in form["pecas_avariadas"]:
        for key, value in (("avariada_id", row["peca_id"]), ("avariada_nome", row["nome"]), ("avariada_descricao", row["descricao"])):
            data.add(key, str(value))
    for row in form["pecas_reparo"]:
        for key, value in (("reparo_id", row["peca_id"]), ("reparo_quantidade", row["quantidade"]), ("reparo_observacoes", row["observacoes"])):
            data.add(key, str(value))
    _, errors = salvar_atendimento_manutencao(drone, data, user=user)
    if errors:
        raise ValueError("Preencha a OS antes de concluir: " + next(iter(errors.values())))
    return True


def validate_bateria_form(form_data, *, existing_bateria=None, user=None):
    errors = {}

    modelo = (form_data.get("modelo") or "").strip()
    renomacao = (form_data.get("renomacao") or "").strip()
    status = (form_data.get("status") or "Ativo").strip()
    categoria = (form_data.get("categoria") or "").strip()
    ano_raw = (form_data.get("ano_fabricacao") or "").strip()
    numero_serie = (form_data.get("numero_serie") or "").strip()
    ciclo_raw = (form_data.get("ciclo") or "").strip()
    drone_id_raw = (form_data.get("drone_id") or "").strip()
    manut_raw = (form_data.get("ultima_manutencao") or "").strip()

    form = {
        "modelo": modelo,
        "renomacao": renomacao,
        "status": status,
        "categoria": categoria,
        "ano_fabricacao": ano_raw,
        "numero_serie": numero_serie,
        "ciclo": ciclo_raw,
        "drone_id": drone_id_raw,
        "ultima_manutencao": manut_raw,
    }

    if not modelo:
        errors["modelo"] = "Informe o modelo da bateria."
    if not renomacao:
        errors["renomacao"] = "Informe a renomacao (ex: BAT-01)."

    if status not in {"Ativo", "Inativo", *MANUTENCAO_STATUS_ALIASES}:
        errors["status"] = "Selecione um status válido para a bateria."
    for field, value in (("modelo", modelo), ("renomacao", renomacao), ("numero_serie", numero_serie), ("categoria", categoria)):
        if len(value) > 100:
            errors[field] = "Use no máximo 100 caracteres."

    ciclo = None
    if ciclo_raw:
        try:
            from app.modules.equipamentos.baterias import parse_cycle_count
            ciclo = parse_cycle_count(ciclo_raw)
        except ValueError as exc:
            errors["ciclo"] = str(exc)

    ano_fabricacao = None
    if ano_raw:
        try:
            ano_fabricacao = _parse_int(
                ano_raw,
                min_value=1900,
                max_value=2100,
                error_message="Ano de fabricacao invalido.",
            )
        except ValueError as exc:
            errors["ano_fabricacao"] = str(exc)

    ultima_manutencao = None
    if manut_raw:
        try:
            ultima_manutencao = _parse_optional_date(manut_raw, error_message="Data invalida.")
        except ValueError as exc:
            errors["ultima_manutencao"] = str(exc)

    drone_id = None
    if drone_id_raw:
        try:
            drone_id = _validate_drone_id(drone_id_raw, user=user)
            from app.modules.equipamentos.baterias import resolve_battery_tenant
            resolve_battery_tenant(owner=getattr(user, "prefeitura_id", None),
                drone=db.session.get(Drones, drone_id), existing=existing_bateria)
        except ValueError as exc:
            errors["drone_id"] = str(exc)

    if not drone_id_raw:
        from app.modules.equipamentos.baterias import resolve_battery_tenant
        try:
            resolve_battery_tenant(owner=getattr(user, "prefeitura_id", None), existing=existing_bateria)
        except ValueError as exc:
            errors["drone_id"] = str(exc)

    if numero_serie:
        query = Equipamentos.query.filter(Equipamentos.numero_serie == numero_serie)
        if existing_bateria is not None:
            query = query.filter(Equipamentos.id != existing_bateria.id)
        if query.first():
            errors["numero_serie"] = (
                "Ja existe outro equipamento com esse Numero de Serie."
                if existing_bateria is not None
                else "Ja existe um equipamento com esse Numero de Serie."
            )

    cleaned = {
        "modelo": modelo,
        "renomacao": renomacao,
        "status": status,
        "categoria": categoria or None,
        "ano_fabricacao": ano_fabricacao,
        "numero_serie": numero_serie or None,
        "ciclo": ciclo,
        "drone_id": drone_id,
        "ultima_manutencao": ultima_manutencao,
    }

    return form, cleaned, errors


def create_bateria(cleaned_data, *, prefeitura_id=None, user=None):
    from app.modules.equipamentos.baterias import record_battery_update, resolve_battery_tenant
    prefeitura_id = resolve_battery_tenant(owner=prefeitura_id,
        drone=db.session.get(Drones, cleaned_data["drone_id"]) if cleaned_data["drone_id"] else None)
    bateria = Baterias(
        tipo_equipamento="baterias",
        status=cleaned_data["status"],
        modelo=cleaned_data["modelo"],
        renomacao=cleaned_data["renomacao"],
        categoria=cleaned_data["categoria"],
        ano_fabricacao=cleaned_data["ano_fabricacao"],
        numero_serie=cleaned_data["numero_serie"],
        ultima_manutencao=cleaned_data["ultima_manutencao"],
        prefeitura_id=prefeitura_id,
        ciclo=cleaned_data["ciclo"],
        drone_id=cleaned_data["drone_id"],
    )
    db.session.add(bateria)
    record_battery_update(bateria, user=user, tipo="cadastro", confirm_cycles=bateria.ciclo is not None)
    db.session.commit()
    return bateria


def update_bateria(bateria, cleaned_data, *, user=None):
    from app.modules.equipamentos.baterias import battery_snapshot, record_battery_update, resolve_battery_tenant
    before = battery_snapshot(bateria)
    bateria.prefeitura_id = resolve_battery_tenant(existing=bateria,
        drone=db.session.get(Drones, cleaned_data["drone_id"]) if cleaned_data["drone_id"] else None)
    if cleaned_data["drone_id"]:
        bateria.equipe_id = None
    bateria.modelo = cleaned_data["modelo"]
    bateria.renomacao = cleaned_data["renomacao"]
    bateria.status = cleaned_data["status"]
    bateria.categoria = cleaned_data["categoria"]
    bateria.numero_serie = cleaned_data["numero_serie"]
    bateria.ciclo = cleaned_data["ciclo"]
    bateria.drone_id = cleaned_data["drone_id"]
    bateria.ano_fabricacao = cleaned_data["ano_fabricacao"]
    bateria.ultima_manutencao = cleaned_data["ultima_manutencao"]
    record_battery_update(bateria, user=user, before=before)
    db.session.commit()
    return bateria


def build_bateria_edit_form(bateria):
    return {
        "modelo": bateria.modelo,
        "renomacao": bateria.renomacao,
        "status": bateria.status,
        "categoria": bateria.categoria,
        "ano_fabricacao": bateria.ano_fabricacao,
        "numero_serie": bateria.numero_serie,
        "ciclo": bateria.ciclo if bateria.ciclo is not None else "",
        "drone_id": bateria.drone_id,
        "ultima_manutencao": bateria.ultima_manutencao.strftime("%Y-%m-%d") if bateria.ultima_manutencao else "",
    }


def delete_bateria(bateria):
    from app.models import BateriaAtualizacao
    if BateriaAtualizacao.query.filter_by(bateria_id=bateria.id).first():
        raise ValueError("Esta bateria possui histórico. Altere o status para Inativo para preservar os registros.")
    bateria.drone_id = None
    db.session.flush()
    db.session.delete(bateria)
    db.session.commit()


def update_bateria_ciclos(bateria, payload, *, user=None):
    from app.modules.equipamentos.baterias import battery_snapshot, parse_cycle_count, record_battery_update
    if not isinstance(payload, dict):
        raise ValueError("Dados de ciclos inválidos.")
    operacao = payload.get("operacao", "add")
    if not isinstance(operacao, str) or operacao not in {"add", "sub", "definir"}:
        raise ValueError("Operação de ciclos inválida.")
    quantidade = parse_cycle_count(payload.get("quantidade", 1))
    db.session.refresh(bateria, attribute_names=["ciclo"], with_for_update={"of": Baterias.__table__})
    if operacao != "definir" and bateria.ciclo is None:
        raise ValueError("Informe primeiro a leitura total de ciclos na página da bateria.")
    before = battery_snapshot(bateria)
    if operacao == "definir":
        bateria.ciclo = quantidade
    elif operacao == "add":
        bateria.ciclo = parse_cycle_count(bateria.ciclo + quantidade)
    else:
        bateria.ciclo = max(0, bateria.ciclo - quantidade)
    record_battery_update(bateria, user=user, before=before, tipo="ciclos", confirm_cycles=True)
    db.session.commit()
    return {"novo_ciclo": bateria.ciclo, "cor": "bg-secondary"}
