from app.extensions import db
from app.models import Drones, EstoquePeca
from app.shared.access import apply_prefeitura_scope


ESTOQUE_STATUS = {
    "disponivel_manutencao": "Disponivel para manutencao",
    "reservada": "Reservada",
    "baixada": "Baixada",
    "indisponivel": "Indisponivel",
}


def list_pecas(user=None):
    query = EstoquePeca.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, EstoquePeca.prefeitura_id)
    return query.order_by(EstoquePeca.criado_em.desc()).all()


def list_drones_for_estoque(user=None):
    query = Drones.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
    return query.order_by(Drones.renomacao.asc()).all()


def get_peca_scoped_or_404(peca_id, user):
    query = apply_prefeitura_scope(EstoquePeca.query, user, EstoquePeca.prefeitura_id)
    return query.filter(EstoquePeca.id == peca_id).first_or_404()


def build_peca_form(peca):
    return {
        "numero_serie": peca.numero_serie or "",
        "modelo_peca": peca.modelo_peca or "",
        "quantidade": str(peca.quantidade if peca.quantidade is not None else 1),
        "drone_id": str(peca.drone_id or ""),
        "status": peca.status or "disponivel_manutencao",
        "observacoes": peca.observacoes or "",
    }


def validate_peca_form(form_data, *, existing_peca=None, user=None):
    errors = {}

    numero_serie = (form_data.get("numero_serie") or "").strip()
    modelo_peca = (form_data.get("modelo_peca") or "").strip()
    quantidade_raw = (form_data.get("quantidade") or "1").strip()
    drone_id_raw = (form_data.get("drone_id") or "").strip()
    status = (form_data.get("status") or "disponivel_manutencao").strip()
    observacoes = (form_data.get("observacoes") or "").strip()

    form = {
        "numero_serie": numero_serie,
        "modelo_peca": modelo_peca,
        "quantidade": quantidade_raw,
        "drone_id": drone_id_raw,
        "status": status,
        "observacoes": observacoes,
    }

    if not modelo_peca:
        errors["modelo_peca"] = "Informe o modelo da peca."

    try:
        quantidade = int(quantidade_raw)
        if quantidade < 0:
            raise ValueError
    except ValueError:
        quantidade = None
        errors["quantidade"] = "Informe uma quantidade valida."

    if status not in ESTOQUE_STATUS:
        errors["status"] = "Status invalido."

    drone_id = None
    if drone_id_raw:
        try:
            drone_id = int(drone_id_raw)
        except ValueError:
            errors["drone_id"] = "Drone invalido."
        else:
            query = Drones.query.filter(Drones.id == drone_id)
            if user is not None:
                query = apply_prefeitura_scope(query, user, Drones.prefeitura_id)
            if not query.first():
                errors["drone_id"] = "Drone invalido."

    if numero_serie:
        query = EstoquePeca.query.filter(EstoquePeca.numero_serie == numero_serie)
        if existing_peca is not None:
            query = query.filter(EstoquePeca.id != existing_peca.id)
        if query.first():
            errors["numero_serie"] = "Ja existe uma peca com esse numero de serie."

    cleaned = {
        "numero_serie": numero_serie or None,
        "modelo_peca": modelo_peca,
        "quantidade": quantidade,
        "drone_id": drone_id,
        "status": status,
        "observacoes": observacoes or None,
    }
    return form, cleaned, errors


def create_peca(cleaned_data, *, prefeitura_id=None):
    peca = EstoquePeca(prefeitura_id=prefeitura_id, **cleaned_data)
    db.session.add(peca)
    db.session.commit()
    return peca


def update_peca(peca, cleaned_data):
    for key, value in cleaned_data.items():
        setattr(peca, key, value)
    db.session.commit()
    return peca


def delete_peca(peca):
    db.session.delete(peca)
    db.session.commit()
