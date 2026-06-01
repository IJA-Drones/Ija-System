from datetime import date, datetime

from app.extensions import db
from app.models import Baterias, Drones, Equipamentos, Equipe
from app.shared.access import apply_prefeitura_scope


MANUTENCAO_STATUS = "Em Manuten\u00e7\u00e3o"
MANUTENCAO_STATUS_ALIASES = (
    MANUTENCAO_STATUS,
    "Manuten\u00e7\u00e3o",
    "Manutencao",
    "Em Manutencao",
)


def list_equipamentos_dashboard(user=None):
    query = Equipamentos.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
    return {
        "equipamentos": query.order_by(Equipamentos.criado_em.desc()).all(),
        "total_drones": query.filter_by(tipo_equipamento="drones").count(),
        "total_baterias": query.filter_by(tipo_equipamento="baterias").count(),
        "em_manutencao": query.filter(Equipamentos.status.in_(MANUTENCAO_STATUS_ALIASES)).count(),
    }


def list_drones(user=None):
    query = Drones.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
    return query.all()


def list_baterias(user=None):
    query = Baterias.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Baterias.prefeitura_id)
    return query.all()


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
        query = Drones.query.filter(Drones.numero_serie == numero_serie)
        if existing_drone is not None:
            query = query.filter(Drones.id != existing_drone.id)
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
    for bateria in list(drone.baterias):
        bateria.drone_id = None

    db.session.flush()
    db.session.delete(drone)
    db.session.commit()


def send_drone_to_manutencao(drone):
    if (drone.status or "").strip() in MANUTENCAO_STATUS_ALIASES:
        return False

    drone.status = MANUTENCAO_STATUS
    drone.ultima_manutencao = date.today()
    db.session.commit()
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

    ciclo = 0
    if ciclo_raw:
        try:
            ciclo = _parse_int(ciclo_raw, min_value=0, error_message="Ciclo invalido (use numero inteiro).")
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


def create_bateria(cleaned_data, *, prefeitura_id=None):
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
    db.session.commit()
    return bateria


def update_bateria(bateria, cleaned_data):
    bateria.modelo = cleaned_data["modelo"]
    bateria.renomacao = cleaned_data["renomacao"]
    bateria.status = cleaned_data["status"]
    bateria.categoria = cleaned_data["categoria"]
    bateria.numero_serie = cleaned_data["numero_serie"]
    bateria.ciclo = cleaned_data["ciclo"]
    bateria.drone_id = cleaned_data["drone_id"]
    bateria.ano_fabricacao = cleaned_data["ano_fabricacao"]
    bateria.ultima_manutencao = cleaned_data["ultima_manutencao"]
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
        "ciclo": bateria.ciclo,
        "drone_id": bateria.drone_id,
        "ultima_manutencao": bateria.ultima_manutencao.strftime("%Y-%m-%d") if bateria.ultima_manutencao else "",
    }


def delete_bateria(bateria):
    bateria.drone_id = None
    db.session.flush()
    db.session.delete(bateria)
    db.session.commit()


def update_bateria_ciclos(bateria, payload):
    quantidade = payload.get("quantidade", 1)
    operacao = payload.get("operacao", "add")

    try:
        quantidade_int = int(quantidade)
    except (TypeError, ValueError):
        quantidade_int = 1

    if operacao == "add":
        bateria.ciclo += quantidade_int
    else:
        bateria.ciclo = max(0, bateria.ciclo - quantidade_int)

    db.session.commit()

    return {
        "novo_ciclo": bateria.ciclo,
        "cor": "bg-danger" if bateria.ciclo > 200 else "bg-success",
    }
