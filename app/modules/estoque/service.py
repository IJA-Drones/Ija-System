from app.extensions import db
from app.models import Drones, Equipamentos, EstoquePeca
from app.shared.access import apply_prefeitura_scope, resolve_linked_prefeitura


ESTOQUE_STATUS = {
    "disponivel_manutencao": "Disponivel para manutencao",
    "reservada": "Reservada",
    "baixada": "Baixada",
    "indisponivel": "Indisponivel",
}


def list_pecas(user=None, local=None):
    query = EstoquePeca.query
    local = (local or "").strip()
    if local:
        query = query.filter(EstoquePeca.prateleira_local.ilike(f"%{local}%"))
    if user is not None:
        query = apply_prefeitura_scope(query, user, EstoquePeca.prefeitura_id)
    return query.order_by(EstoquePeca.criado_em.desc()).all()


def list_equipamentos_for_estoque(user=None):
    query = Equipamentos.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
    return query.order_by(Equipamentos.tipo_equipamento.asc(), Equipamentos.renomacao.asc()).all()


def get_peca_scoped_or_404(peca_id, user):
    query = apply_prefeitura_scope(EstoquePeca.query, user, EstoquePeca.prefeitura_id)
    return query.filter(EstoquePeca.id == peca_id).first_or_404()


def build_peca_form(peca):
    return {
        "numero_serie": peca.numero_serie or "",
        "modelo_peca": peca.modelo_peca or "",
        "prateleira_local": peca.prateleira_local or "",
        "modelos_compativeis": peca.modelos_compativeis or "",
        "quantidade": str(peca.quantidade if peca.quantidade is not None else 1),
        "equipamento_id": str(peca.equipamento_id or peca.drone_id or ""),
        "status": peca.status or "disponivel_manutencao",
        "observacoes": peca.observacoes or "",
    }


def validate_peca_form(form_data, *, existing_peca=None, user=None):
    errors = {}

    numero_serie = (form_data.get("numero_serie") or "").strip()
    modelo_peca = (form_data.get("modelo_peca") or "").strip()
    prateleira_local = (form_data.get("prateleira_local") or "").strip()
    modelos_compativeis = (form_data.get("modelos_compativeis") or "").strip()
    quantidade_raw = (form_data.get("quantidade") or "1").strip()
    equipamento_id_raw = (form_data.get("equipamento_id") or form_data.get("drone_id") or "").strip()
    status = (form_data.get("status") or "disponivel_manutencao").strip()
    observacoes = (form_data.get("observacoes") or "").strip()

    form = {
        "numero_serie": numero_serie,
        "modelo_peca": modelo_peca,
        "prateleira_local": prateleira_local,
        "modelos_compativeis": modelos_compativeis,
        "quantidade": quantidade_raw,
        "equipamento_id": equipamento_id_raw,
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

    equipamento_id = None
    drone_id = None
    if equipamento_id_raw:
        try:
            equipamento_id = int(equipamento_id_raw)
        except ValueError:
            errors["equipamento_id"] = "Equipamento inválido."
        else:
            query = Equipamentos.query.filter(Equipamentos.id == equipamento_id)
            if user is not None:
                query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
            equipamento = query.first()
            if not equipamento:
                errors["equipamento_id"] = "Equipamento inválido."
            elif existing_peca is not None:
                try:
                    resolve_linked_prefeitura(existing_peca.prefeitura_id, equipamento)
                except ValueError as exc:
                    errors["equipamento_id"] = str(exc)
            if equipamento is not None and isinstance(equipamento, Drones):
                drone_id = equipamento.id

    if numero_serie:
        query = EstoquePeca.query.filter(EstoquePeca.numero_serie == numero_serie)
        if existing_peca is not None:
            query = query.filter(EstoquePeca.id != existing_peca.id)
        if query.first():
            errors["numero_serie"] = "Ja existe uma peca com esse numero de serie."

    cleaned = {
        "numero_serie": numero_serie or None,
        "modelo_peca": modelo_peca,
        "prateleira_local": prateleira_local or None,
        "modelos_compativeis": modelos_compativeis or None,
        "quantidade": quantidade,
        "equipamento_id": equipamento_id,
        "drone_id": drone_id,
        "status": status,
        "observacoes": observacoes or None,
    }
    return form, cleaned, errors


def create_peca(cleaned_data, *, prefeitura_id=None):
    if cleaned_data.get("equipamento_id"):
        prefeitura_id = resolve_linked_prefeitura(prefeitura_id, db.session.get(Equipamentos, cleaned_data["equipamento_id"]))
    peca = EstoquePeca(prefeitura_id=prefeitura_id, **cleaned_data)
    db.session.add(peca)
    db.session.commit()
    return peca


def update_peca(peca, cleaned_data):
    if cleaned_data.get("equipamento_id"):
        peca.prefeitura_id = resolve_linked_prefeitura(peca.prefeitura_id, db.session.get(Equipamentos, cleaned_data["equipamento_id"]))
    for key, value in cleaned_data.items():
        setattr(peca, key, value)
    db.session.commit()
    return peca


def delete_peca(peca):
    db.session.delete(peca)
    db.session.commit()
