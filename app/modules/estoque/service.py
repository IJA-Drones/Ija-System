from app.extensions import db
from app.models import Drones, Equipamentos, EstoquePeca, Prefeitura
from app.shared.access import apply_prefeitura_scope, can_access_prefeitura, is_admin_global_user, resolve_linked_prefeitura
from sqlalchemy import or_


ESTOQUE_STATUS = {
    "disponivel_manutencao": "Disponivel para manutencao",
    "reservada": "Reservada",
    "baixada": "Baixada",
    "indisponivel": "Indisponivel",
}


def list_pecas(user=None, local=None, q=None, status=None):
    query = EstoquePeca.query.filter(EstoquePeca.arquivada_em.is_(None))
    local = (local or "").strip()
    if local:
        query = query.filter(EstoquePeca.prateleira_local.ilike(f"%{local}%"))
    if status in ESTOQUE_STATUS:
        query = query.filter(EstoquePeca.status == status)
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        equipment_match = or_(Equipamentos.renomacao.ilike(like), Equipamentos.modelo.ilike(like), Equipamentos.numero_serie.ilike(like))
        query = query.filter(or_(
            EstoquePeca.modelo_peca.ilike(like), EstoquePeca.numero_serie.ilike(like),
            EstoquePeca.modelos_compativeis.ilike(like),
            EstoquePeca.equipamentos_compativeis.any(equipment_match),
            EstoquePeca.equipamento.has(equipment_match),
            EstoquePeca.drone.has(or_(Drones.renomacao.ilike(like), Drones.modelo.ilike(like), Drones.numero_serie.ilike(like))),
        ))
    if user is not None:
        query = apply_prefeitura_scope(query, user, EstoquePeca.prefeitura_id)
    return query.order_by(EstoquePeca.criado_em.desc()).all()


def list_equipamentos_for_estoque(user=None):
    query = Equipamentos.query
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipamentos.prefeitura_id)
    return query.order_by(Equipamentos.tipo_equipamento.asc(), Equipamentos.renomacao.asc()).all()


def modelos_para_estoque(equipamentos, peca=None):
    modelos = {}
    for equipamento in equipamentos:
        nome = (equipamento.modelo or "").strip()
        if nome:
            modelos.setdefault(nome.casefold(), nome)
    for nome in ((peca.modelos_compativeis or "").split(",") if peca else []):
        nome = nome.strip()
        if nome:
            modelos.setdefault(nome.casefold(), nome)
    return sorted(modelos.values(), key=str.casefold)


def get_peca_scoped_or_404(peca_id, user):
    query = apply_prefeitura_scope(EstoquePeca.query.filter(EstoquePeca.arquivada_em.is_(None)), user, EstoquePeca.prefeitura_id)
    return query.filter(EstoquePeca.id == peca_id).first_or_404()


def build_peca_form(peca):
    return {
        "numero_serie": peca.numero_serie or "",
        "modelo_peca": peca.modelo_peca or "",
        "prateleira_local": peca.prateleira_local or "",
        "modelos_compativeis": [m.strip() for m in (peca.modelos_compativeis or "").split(",") if m.strip()],
        "quantidade": str(peca.quantidade if peca.quantidade is not None else 1),
        "equipamento_ids": [str(e.id) for e in peca.equipamentos_compativeis_exibicao],
        "prefeitura_id": str(peca.prefeitura_id or ""),
        "status": peca.status or "disponivel_manutencao",
        "observacoes": peca.observacoes or "",
    }


def _form_values(form, key):
    if hasattr(form, "getlist"):
        return form.getlist(key)
    value = form.get(key, [])
    return value if isinstance(value, (list, tuple)) else [value]


def validate_peca_form(form_data, *, existing_peca=None, user=None, equipamentos_disponiveis=None, series_em_uso=None):
    errors = {}
    numero_serie = (form_data.get("numero_serie") or "").strip()
    modelo_peca = (form_data.get("modelo_peca") or "").strip()
    prateleira_local = (form_data.get("prateleira_local") or "").strip()
    modelos = list(dict.fromkeys(m.strip() for value in _form_values(form_data, "modelos_compativeis")
                                for m in str(value).split(",") if m.strip()))
    ids = _form_values(form_data, "equipamento_ids")
    # Preserve older clients that still send the single equipment field.
    if "equipamento_ids" not in form_data and form_data.get("compatibilidade_multipla") != "1":
        ids = [form_data.get("equipamento_id") or form_data.get("drone_id") or ""]
    ids = list(dict.fromkeys(str(value).strip() for value in ids if str(value).strip()))
    quantidade_raw = str(form_data.get("quantidade") or "1").strip()
    status = (form_data.get("status") or "disponivel_manutencao").strip()
    observacoes = (form_data.get("observacoes") or "").strip()
    prefeitura_raw = str(form_data.get("prefeitura_id") or "").strip()
    form = dict(numero_serie=numero_serie, modelo_peca=modelo_peca, prateleira_local=prateleira_local,
                modelos_compativeis=modelos, quantidade=quantidade_raw, equipamento_ids=ids,
                prefeitura_id=prefeitura_raw, status=status, observacoes=observacoes)
    if not modelo_peca:
        errors["modelo_peca"] = "Informe o modelo da peça."
    for field, value, limit in (("modelo_peca", modelo_peca, 120), ("numero_serie", numero_serie, 100),
                                ("prateleira_local", prateleira_local, 120)):
        if len(value) > limit:
            errors[field] = f"Use até {limit} caracteres."
    try:
        quantidade = int(quantidade_raw)
        if quantidade < 0:
            raise ValueError
    except ValueError:
        quantidade = None
        errors["quantidade"] = "Informe uma quantidade válida."
    if status not in ESTOQUE_STATUS:
        errors["status"] = "Status inválido."

    if equipamentos_disponiveis is None:
        equipamentos_disponiveis = list_equipamentos_for_estoque(user=user)
    por_id = {str(e.id): e for e in equipamentos_disponiveis}
    equipamentos = [por_id[i] for i in ids if i in por_id]
    if len(equipamentos) != len(ids):
        errors["equipamento_ids"] = "Selecione equipamentos válidos e autorizados."
    prefeitura_id = existing_peca.prefeitura_id if existing_peca is not None else getattr(user, "prefeitura_id", None)
    if prefeitura_raw:
        try:
            requested = int(prefeitura_raw)
            if user is not None and not can_access_prefeitura(user, requested):
                raise ValueError
            if prefeitura_id is not None and requested != prefeitura_id and (existing_peca is not None or not is_admin_global_user(user)):
                raise ValueError
            prefeitura_id = requested
        except ValueError:
            errors["prefeitura_id"] = "Selecione a prefeitura do estoque. Os vínculos devem pertencer à mesma prefeitura."
    for equipamento in equipamentos:
        try:
            prefeitura_id = resolve_linked_prefeitura(prefeitura_id, equipamento)
        except ValueError:
            errors["equipamento_ids"] = "Todos os equipamentos devem pertencer à prefeitura deste estoque."
    if prefeitura_id is None or (user is not None and not can_access_prefeitura(user, prefeitura_id)):
        errors["prefeitura_id"] = "Selecione a prefeitura do estoque."
    elif not db.session.get(Prefeitura, prefeitura_id):
        errors["prefeitura_id"] = "Prefeitura inválida."
    form["prefeitura_id"] = str(prefeitura_id or prefeitura_raw)
    modelos_disponiveis = modelos_para_estoque([e for e in equipamentos_disponiveis if e.prefeitura_id == prefeitura_id], existing_peca)
    canonicos = {m.casefold(): m for m in modelos_disponiveis}
    if any(m.casefold() not in canonicos for m in modelos):
        errors["modelos_compativeis"] = "Selecione modelos disponíveis na prefeitura deste estoque."
    modelos = list(dict.fromkeys(canonicos.get(m.casefold(), m) for m in modelos))
    form["modelos_compativeis"] = modelos
    if numero_serie:
        if series_em_uso is None:
            query = EstoquePeca.query.filter(EstoquePeca.numero_serie == numero_serie, EstoquePeca.arquivada_em.is_(None))
            if existing_peca is not None:
                query = query.filter(EstoquePeca.id != existing_peca.id)
            em_uso = query.first() is not None
        else:
            em_uso = numero_serie.casefold() in series_em_uso
        if em_uso:
            errors["numero_serie"] = "Já existe uma peça com esse número de série."
    if "equipamento_ids" in errors:
        for legacy_field in ("equipamento_id", "drone_id"):
            if form_data.get(legacy_field):
                errors[legacy_field] = errors["equipamento_ids"]
    cleaned = dict(numero_serie=numero_serie or None, modelo_peca=modelo_peca,
                   prateleira_local=prateleira_local or None, modelos_compativeis=", ".join(modelos) or None,
                   quantidade=quantidade, status=status, observacoes=observacoes or None,
                   equipamentos_compativeis=equipamentos, prefeitura_id=prefeitura_id)
    return form, cleaned, errors


def _apply_peca(peca, cleaned_data, prefeitura_id=None):
    data = dict(cleaned_data)
    equipamentos = data.pop("equipamentos_compativeis", [])
    tenant = data.pop("prefeitura_id", prefeitura_id)
    for equipamento in equipamentos:
        tenant = resolve_linked_prefeitura(tenant, equipamento)
    peca.prefeitura_id = tenant
    peca.equipamentos_compativeis = equipamentos
    # Legacy references remain available to integrations; this is compatibility, not installation.
    peca.equipamento = equipamentos[0] if equipamentos else None
    peca.drone = next((e for e in equipamentos if isinstance(e, Drones)), None)
    for key, value in data.items():
        setattr(peca, key, value)


def create_peca(cleaned_data, *, prefeitura_id=None):
    peca = EstoquePeca()
    _apply_peca(peca, cleaned_data, prefeitura_id)
    db.session.add(peca)
    db.session.commit()
    return peca


def update_peca(peca, cleaned_data):
    _apply_peca(peca, cleaned_data, peca.prefeitura_id)
    db.session.commit()
    return peca


def delete_peca(peca):
    db.session.delete(peca)
    db.session.commit()
