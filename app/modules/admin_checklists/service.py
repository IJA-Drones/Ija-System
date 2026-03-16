from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ChecklistSemanalDrone, ChecklistSemanalVeiculo, Drones, Pilotos, Veiculos


CHECKLIST_VEICULO_BOOL_LABELS = [
    ("farois_funcionando", "Farois"),
    ("setas_funcionando", "Setas"),
    ("lanternas_funcionando", "Lanternas"),
    ("piscaalerta_funcionando", "Pisca-alerta"),
    ("luz_painel", "Luz do painel"),
    ("limpador_parabrisa", "Limpador de parabrisa"),
    ("agua_radiador", "Agua do radiador"),
    ("fluido_freio", "Fluido de freio"),
    ("oleo_motor", "Oleo do motor"),
    ("vidros", "Vidros"),
    ("retrovisores", "Retrovisores"),
    ("pneus", "Pneus"),
    ("estepe", "Estepe"),
    ("macaco", "Macaco"),
    ("triangulo", "Triangulo"),
    ("chave_roda", "Chave de roda"),
    ("extintor", "Extintor"),
    ("cinto_seguranca", "Cinto de seguranca"),
    ("alarme", "Alarme"),
    ("ar_condicionado", "Ar-condicionado"),
    ("radio", "Radio"),
    ("giroflex", "Giroflex"),
    ("isqueiro", "Isqueiro"),
    ("carregador", "Carregador"),
    ("lataria_frontal", "Lataria frontal"),
    ("lataria_lateral", "Lataria lateral"),
    ("lataria_traseira", "Lataria traseira"),
    ("lataria_porta_frontal", "Porta frontal"),
    ("lataria_porta_traseira", "Porta traseira"),
    ("lataria_porta_lateral", "Porta lateral"),
    ("parachoque_frontal", "Parachoque frontal"),
    ("parachoque_traseiro", "Parachoque traseiro"),
]

CHECKLIST_VEICULO_TEXT_LABELS = [
    ("condicao_luzes_direcao", "Condicao luzes / direcao"),
    ("condicao_luz_painel", "Condicao luz do painel"),
    ("condicao_itens_manutencao", "Condicao manutencao preventiva"),
    ("condicao_vidros_retrovisores", "Condicao vidros / retrovisores"),
    ("condicao_pneus_estepe", "Condicao pneus / estepe"),
    ("condicao_itens_seguranca", "Condicao itens de seguranca"),
    ("condicao_itens_carro_interno", "Condicao itens internos"),
    ("condicao_giroflex_isqueiro_carregador", "Condicao giroflex / isqueiro / carregador"),
    ("condicao_lataria", "Condicao lataria"),
    ("condicao_lataria_portas", "Condicao lataria portas"),
    ("condicao_itens_carro_externo", "Condicao itens externos"),
]

CHECKLIST_DRONE_BOOL_LABELS = [
    ("helices_status", "Helices"),
    ("tanque", "Tanque"),
    ("trem_pouso", "Trem de pouso"),
    ("cameras", "Cameras"),
    ("carregador_controle", "Carregador do controle"),
    ("baterias", "Baterias"),
    ("cabos_carregador", "Cabos do carregador"),
    ("correia_pescoco", "Correia de pescoco"),
]

CHECKLIST_DRONE_TEXT_LABELS = [
    ("condicao_helices", "Condicao helices"),
    ("condicao_estrutura", "Condicao estrutura"),
    ("condicao_carregador_bateria", "Condicao carregador / bateria"),
    ("condicao_cabos_correia", "Condicao cabos / correia"),
    ("observacoes_equipamento", "Observacoes do equipamento"),
]


def _clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _format_km_admin(value):
    try:
        return f"{float(value or 0):.0f} km"
    except Exception:
        return "-"


def _checklist_status_items(checklist, labels):
    items = []
    failures = 0

    for field, label in labels:
        ok = bool(getattr(checklist, field))
        if not ok:
            failures += 1
        items.append({"label": label, "ok": ok})

    return items, failures


def _checklist_notes_items(checklist, labels):
    notes = []

    for field, label in labels:
        value = _clean_str(getattr(checklist, field))
        if value:
            notes.append({"label": label, "value": value})

    return notes


def normalize_checklist_veiculo_admin(checklist):
    items, failures = _checklist_status_items(checklist, CHECKLIST_VEICULO_BOOL_LABELS)
    notes = _checklist_notes_items(checklist, CHECKLIST_VEICULO_TEXT_LABELS)
    veiculo = checklist.veiculo
    piloto = checklist.piloto

    meta = [
        {"label": "Placa", "value": (veiculo.placa if veiculo else "") or "-"},
        {"label": "Operacao", "value": (veiculo.operacao if veiculo else "") or "-"},
        {"label": "Responsavel", "value": (veiculo.responsavel if veiculo else "") or "-"},
        {"label": "KM lido", "value": _format_km_admin(checklist.km_leitura)},
    ]

    total_items = len(CHECKLIST_VEICULO_BOOL_LABELS)
    return {
        "id": checklist.id,
        "tipo": "veiculo",
        "tipo_label": "Veiculo",
        "data_registro": checklist.data_registro,
        "piloto_id": checklist.piloto_id,
        "titulo": (veiculo.modelo if veiculo else "") or "Veiculo sem identificacao",
        "subtitulo": (veiculo.placa if veiculo else "") or "-",
        "complemento": (veiculo.responsavel if veiculo else "") or "",
        "piloto_nome": (piloto.nome_piloto if piloto else "") or "-",
        "status_label": "Conforme" if failures == 0 else f"{failures} pendencia(s)",
        "status_class": "success" if failures == 0 else "warning",
        "falhas": failures,
        "itens_ok": total_items - failures,
        "itens_total": total_items,
        "observacoes_total": len(notes),
        "meta": meta,
        "detalhes_itens": items,
        "observacoes": notes,
        "assinatura": checklist.assinatura_piloto or "",
    }


def normalize_checklist_drone_admin(checklist):
    items, failures = _checklist_status_items(checklist, CHECKLIST_DRONE_BOOL_LABELS)
    notes = _checklist_notes_items(checklist, CHECKLIST_DRONE_TEXT_LABELS)
    drone = checklist.drone
    piloto = checklist.piloto

    meta = [
        {"label": "Renomacao", "value": (drone.renomacao if drone else "") or "-"},
        {"label": "Modelo", "value": (drone.modelo if drone else "") or "-"},
        {"label": "Serie", "value": (drone.numero_serie if drone else "") or "-"},
        {"label": "Baterias", "value": str(int(checklist.num_baterias or 0))},
        {"label": "Baterias WB", "value": str(int(checklist.num_baterias_wb or 0))},
        {"label": "Responsavel informado", "value": checklist.nome_responsavel or "-"},
    ]

    total_items = len(CHECKLIST_DRONE_BOOL_LABELS)
    return {
        "id": checklist.id,
        "tipo": "drone",
        "tipo_label": "Drone",
        "data_registro": checklist.data_registro,
        "piloto_id": checklist.piloto_id,
        "titulo": (drone.renomacao if drone else "") or "Drone sem identificacao",
        "subtitulo": (drone.modelo if drone else "") or "-",
        "complemento": (drone.numero_serie if drone else "") or "",
        "piloto_nome": (piloto.nome_piloto if piloto else "") or "-",
        "status_label": "Conforme" if failures == 0 else f"{failures} pendencia(s)",
        "status_class": "success" if failures == 0 else "warning",
        "falhas": failures,
        "itens_ok": total_items - failures,
        "itens_total": total_items,
        "observacoes_total": len(notes),
        "meta": meta,
        "detalhes_itens": items,
        "observacoes": notes,
        "assinatura": checklist.assinatura_piloto or "",
    }


def group_admin_checklists_by_week(records):
    groups = {}

    for item in records:
        registered_at = item.get("data_registro")
        if not registered_at:
            continue

        base_date = registered_at.date()
        week_start = base_date - timedelta(days=base_date.weekday())
        week_end = week_start + timedelta(days=6)
        group_key = (item.get("piloto_id"), week_start.isoformat())

        group = groups.setdefault(
            group_key,
            {
                "piloto_id": item.get("piloto_id"),
                "piloto_nome": item.get("piloto_nome") or "-",
                "semana_inicio": week_start,
                "semana_fim": week_end,
                "ultima_movimentacao": registered_at,
                "veiculos": [],
                "drones": [],
                "falhas": 0,
                "itens_ok": 0,
                "itens_total": 0,
                "observacoes_total": 0,
            },
        )

        if registered_at > (group["ultima_movimentacao"] or datetime.min):
            group["ultima_movimentacao"] = registered_at

        if item.get("tipo") == "veiculo":
            group["veiculos"].append(item)
        elif item.get("tipo") == "drone":
            group["drones"].append(item)

        group["falhas"] += int(item.get("falhas") or 0)
        group["itens_ok"] += int(item.get("itens_ok") or 0)
        group["itens_total"] += int(item.get("itens_total") or 0)
        group["observacoes_total"] += int(item.get("observacoes_total") or 0)

    grouped = []
    for group in groups.values():
        group["veiculos"].sort(key=lambda item: item.get("data_registro") or datetime.min, reverse=True)
        group["drones"].sort(key=lambda item: item.get("data_registro") or datetime.min, reverse=True)
        group["status_label"] = "Conforme" if group["falhas"] == 0 else f"{group['falhas']} pendencia(s)"
        group["resumo_label"] = f"{len(group['veiculos'])} veiculo(s) • {len(group['drones'])} drone(s)"
        grouped.append(group)

    grouped.sort(key=lambda item: item["ultima_movimentacao"] or datetime.min, reverse=True)
    return grouped


def build_admin_checklists_weekly_groups(q: str, data_inicio: str, data_fim: str):
    records = []

    query_veiculos = (
        ChecklistSemanalVeiculo.query
        .options(
            joinedload(ChecklistSemanalVeiculo.veiculo),
            joinedload(ChecklistSemanalVeiculo.piloto),
        )
        .join(Veiculos, ChecklistSemanalVeiculo.veiculo_id == Veiculos.id)
        .join(Pilotos, ChecklistSemanalVeiculo.piloto_id == Pilotos.id)
    )

    if q:
        like = f"%{q}%"
        query_veiculos = query_veiculos.filter(
            db.or_(
                Veiculos.modelo.ilike(like),
                Veiculos.placa.ilike(like),
                Veiculos.responsavel.ilike(like),
                Pilotos.nome_piloto.ilike(like),
            )
        )

    if data_inicio:
        try:
            dt_ini = datetime.strptime(data_inicio, "%Y-%m-%d")
            query_veiculos = query_veiculos.filter(ChecklistSemanalVeiculo.data_registro >= dt_ini)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query_veiculos = query_veiculos.filter(ChecklistSemanalVeiculo.data_registro <= dt_fim)
        except ValueError:
            pass

    records.extend(
        normalize_checklist_veiculo_admin(item)
        for item in query_veiculos.order_by(ChecklistSemanalVeiculo.data_registro.desc()).all()
    )

    query_drones = (
        ChecklistSemanalDrone.query
        .options(
            joinedload(ChecklistSemanalDrone.drone),
            joinedload(ChecklistSemanalDrone.piloto),
        )
        .join(Drones, ChecklistSemanalDrone.drone_id == Drones.id)
        .join(Pilotos, ChecklistSemanalDrone.piloto_id == Pilotos.id)
    )

    if q:
        like = f"%{q}%"
        query_drones = query_drones.filter(
            db.or_(
                Drones.renomacao.ilike(like),
                Drones.modelo.ilike(like),
                Drones.numero_serie.ilike(like),
                Pilotos.nome_piloto.ilike(like),
            )
        )

    if data_inicio:
        try:
            dt_ini = datetime.strptime(data_inicio, "%Y-%m-%d")
            query_drones = query_drones.filter(ChecklistSemanalDrone.data_registro >= dt_ini)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query_drones = query_drones.filter(ChecklistSemanalDrone.data_registro <= dt_fim)
        except ValueError:
            pass

    records.extend(
        normalize_checklist_drone_admin(item)
        for item in query_drones.order_by(ChecklistSemanalDrone.data_registro.desc()).all()
    )

    return group_admin_checklists_by_week(records)


def build_admin_checklists_totals(groups):
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    return {
        "geral": len(groups),
        "veiculo": sum(len(item["veiculos"]) for item in groups),
        "drone": sum(len(item["drones"]) for item in groups),
        "pendencias": sum(1 for item in groups if item["falhas"] > 0),
        "semana_atual": sum(1 for item in groups if item["semana_inicio"] == week_start),
    }


def build_admin_checklist_detail(piloto_id: int, semana_inicio: str):
    semana_inicio_date = datetime.strptime(semana_inicio, "%Y-%m-%d").date()
    semana_inicio_dt = datetime.combine(semana_inicio_date, datetime.min.time())
    semana_fim_dt = semana_inicio_dt + timedelta(days=7)

    veiculos = [
        normalize_checklist_veiculo_admin(item)
        for item in (
            ChecklistSemanalVeiculo.query
            .options(
                joinedload(ChecklistSemanalVeiculo.veiculo),
                joinedload(ChecklistSemanalVeiculo.piloto),
            )
            .filter(
                ChecklistSemanalVeiculo.piloto_id == piloto_id,
                ChecklistSemanalVeiculo.data_registro >= semana_inicio_dt,
                ChecklistSemanalVeiculo.data_registro < semana_fim_dt,
            )
            .order_by(ChecklistSemanalVeiculo.data_registro.desc())
            .all()
        )
    ]

    drones = [
        normalize_checklist_drone_admin(item)
        for item in (
            ChecklistSemanalDrone.query
            .options(
                joinedload(ChecklistSemanalDrone.drone),
                joinedload(ChecklistSemanalDrone.piloto),
            )
            .filter(
                ChecklistSemanalDrone.piloto_id == piloto_id,
                ChecklistSemanalDrone.data_registro >= semana_inicio_dt,
                ChecklistSemanalDrone.data_registro < semana_fim_dt,
            )
            .order_by(ChecklistSemanalDrone.data_registro.desc())
            .all()
        )
    ]

    if not veiculos and not drones:
        return None

    piloto_nome = "-"
    if veiculos:
        piloto_nome = veiculos[0]["piloto_nome"]
    elif drones:
        piloto_nome = drones[0]["piloto_nome"]

    ultima_movimentacao = max(
        [item["data_registro"] for item in (veiculos + drones) if item.get("data_registro")],
        default=None,
    )

    totais = {
        "veiculo": len(veiculos),
        "drone": len(drones),
        "pendencias": sum(item["falhas"] for item in (veiculos + drones)),
        "itens_ok": sum(item["itens_ok"] for item in (veiculos + drones)),
        "itens_total": sum(item["itens_total"] for item in (veiculos + drones)),
    }

    return {
        "piloto_id": piloto_id,
        "piloto_nome": piloto_nome,
        "semana_inicio": semana_inicio_date,
        "semana_fim": semana_inicio_date + timedelta(days=6),
        "ultima_movimentacao": ultima_movimentacao,
        "veiculos": veiculos,
        "drones": drones,
        "totais": totais,
    }
