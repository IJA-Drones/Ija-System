from datetime import date, datetime, timedelta

from flask import url_for
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Baterias,
    ChecklistSemanalDrone,
    ChecklistSemanalVeiculo,
    Drones,
    Equipe,
    EquipePiloto,
    Notificacao,
    Usuario,
    Veiculos,
)
from app.modules.agenda_notificacoes import agora_brasilia_naive, criar_notificacao


EQUIPE_OCEANO_USER_TYPE = "equipe_oceano"

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

CHECKLIST_VEICULO_BOOL_FIELDS = [field for field, _ in CHECKLIST_VEICULO_BOOL_LABELS]
CHECKLIST_VEICULO_TEXT_FIELDS = [field for field, _ in CHECKLIST_VEICULO_TEXT_LABELS]
CHECKLIST_DRONE_BOOL_FIELDS = [field for field, _ in CHECKLIST_DRONE_BOOL_LABELS]
CHECKLIST_DRONE_TEXT_FIELDS = [field for field, _ in CHECKLIST_DRONE_TEXT_LABELS]


class PilotoChecklistError(Exception):
    def __init__(self, message, category="warning", *, redirect_endpoint="main.piloto_checklist_semanal"):
        super().__init__(message)
        self.category = category
        self.redirect_endpoint = redirect_endpoint


def build_piloto_checklist_context(user, args):
    state = _build_equipment_state(user, args)
    week_bounds = _week_bounds()

    veiculo_ids = [item.id for item in state["veiculos_equipe"]]
    drone_ids = [item.id for item in state["drones_equipe"]]

    veiculo_padrao_id = args.get("veiculo_id", type=int)
    if veiculo_padrao_id not in veiculo_ids:
        veiculo_padrao_id = state["veiculos_equipe"][0].id if len(state["veiculos_equipe"]) == 1 else None

    drone_padrao_id = args.get("drone_id", type=int)
    if drone_padrao_id not in drone_ids:
        drone_padrao_id = state["drones_equipe"][0].id if len(state["drones_equipe"]) == 1 else None

    return {
        "equipe": state["equipe"],
        "piloto_nome": state["piloto_nome"],
        "papel_equipe": state["papel_equipe"],
        "veiculos_equipe": state["veiculos_equipe"],
        "drones_equipe": state["drones_equipe"],
        "veiculo_padrao_id": veiculo_padrao_id,
        "drone_padrao_id": drone_padrao_id,
        "veiculo_meta": state["veiculo_meta"],
        "drone_meta": state["drone_meta"],
        "veiculo_prefill": state["veiculo_prefill"],
        "drone_prefill": state["drone_prefill"],
        "semana_inicio": week_bounds["inicio"].strftime("%d/%m/%Y"),
        "semana_fim": week_bounds["fim"].strftime("%d/%m/%Y"),
        "agora": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def save_piloto_checklist(user, form_data):
    state = _build_equipment_state(user, include_prefill=False)
    week_bounds = _week_bounds()
    actor_filter = _checklist_actor_filter(user, state["equipe"])

    veiculo_ids = [item.id for item in state["veiculos_equipe"]]
    drone_ids = [item.id for item in state["drones_equipe"]]

    veiculo_id = form_data.get("veiculo_id", type=int)
    drone_id = form_data.get("drone_id", type=int)
    assinatura_piloto = _clean_str(form_data.get("assinatura_piloto"))
    nome_responsavel = _clean_str(form_data.get("nome_responsavel")) or state["piloto_nome"]

    if state["veiculos_equipe"] and veiculo_id and veiculo_id not in veiculo_ids:
        raise PilotoChecklistError("Selecione um veiculo valido da sua equipe.")

    if state["drones_equipe"] and drone_id and drone_id not in drone_ids:
        raise PilotoChecklistError("Selecione um drone valido da sua equipe.")

    if not veiculo_id and not drone_id:
        raise PilotoChecklistError("Selecione ao menos um veiculo ou um drone para registrar o checklist.")

    if not assinatura_piloto:
        raise PilotoChecklistError("A assinatura do responsavel e obrigatoria.")

    try:
        if veiculo_id:
            _save_vehicle_checklist(
                user=user,
                veiculo_id=veiculo_id,
                veiculos_equipe=state["veiculos_equipe"],
                form_data=form_data,
                assinatura_piloto=assinatura_piloto,
                actor_filter=actor_filter,
                week_bounds=week_bounds,
            )

        if drone_id:
            _save_drone_checklist(
                user=user,
                drone_id=drone_id,
                baterias_por_drone=state["baterias_por_drone"],
                form_data=form_data,
                assinatura_piloto=assinatura_piloto,
                nome_responsavel=nome_responsavel,
                actor_filter=actor_filter,
                week_bounds=week_bounds,
            )

        db.session.flush()

        pendencias_semanais = _coletar_pendencias_checklists_semanais(
            actor_filter,
            week_bounds["inicio_dt"],
            week_bounds["proxima_dt"],
        )
        _sincronizar_pendencias(user, state["piloto_nome"], pendencias_semanais, week_bounds["inicio"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "veiculo_id": veiculo_id,
        "drone_id": drone_id,
        "pendencias_semanais": pendencias_semanais,
    }


def _build_equipment_state(user, args=None, include_prefill=True):
    vinculo = _piloto_vinculo_ativo(user)
    equipe = _equipe_operacional_ativa(user)
    if not equipe:
        raise PilotoChecklistError(
            "Voce ainda nao esta vinculado a nenhuma equipe ativa.",
            redirect_endpoint="main.piloto_os",
        )

    piloto_nome = _piloto_nome(user)

    veiculos_equipe = (
        Veiculos.query
        .filter(
            db.or_(
                Veiculos.equipe_id == equipe.id,
                db.func.lower(Veiculos.responsavel) == piloto_nome.lower(),
                db.func.lower(Veiculos.responsavel) == equipe.nome_equipe.lower(),
            )
        )
        .distinct()
        .order_by(Veiculos.operacao.asc(), Veiculos.modelo.asc(), Veiculos.placa.asc())
        .all()
    )

    drones_equipe = (
        Drones.query
        .filter(
            Drones.equipe_id == equipe.id,
            Drones.status == "Ativo",
        )
        .order_by(Drones.renomacao.asc())
        .all()
    )

    veiculo_ids = [item.id for item in veiculos_equipe]
    drone_ids = [item.id for item in drones_equipe]

    veiculo_meta = {
        str(item.id): {
            "id": item.id,
            "label": f"{item.modelo} - {item.placa}",
            "km_atual": float(item.km_atual or 0),
            "operacao": item.operacao or "",
            "responsavel": item.responsavel or "",
        }
        for item in veiculos_equipe
    }

    baterias_por_drone = {}
    if drone_ids:
        baterias_por_drone = {
            int(drone_id): total
            for drone_id, total in (
                db.session.query(Baterias.drone_id, db.func.count(Baterias.id))
                .filter(Baterias.drone_id.in_(drone_ids))
                .group_by(Baterias.drone_id)
                .all()
            )
        }

    drone_meta = {
        str(item.id): {
            "id": item.id,
            "label": f"{item.renomacao} - {item.modelo}",
            "renomacao": item.renomacao or "",
            "modelo": item.modelo or "",
            "numero_serie": item.numero_serie or "",
            "registro_anatel": item.registro_anatel or "",
            "registro_anac": item.registro_anac or "",
            "num_baterias": int(baterias_por_drone.get(item.id, 0) or 0),
        }
        for item in drones_equipe
    }

    veiculo_prefill = {}
    drone_prefill = {}
    if include_prefill:
        veiculo_prefill = _build_veiculo_prefill(veiculo_ids)
        drone_prefill = _build_drone_prefill(drone_ids)

    return {
        "vinculo": vinculo,
        "equipe": equipe,
        "papel_equipe": "equipe" if _is_equipe_oceano(user) else ((vinculo.papel or "").lower() if vinculo else ""),
        "piloto_nome": piloto_nome,
        "veiculos_equipe": veiculos_equipe,
        "drones_equipe": drones_equipe,
        "veiculo_meta": veiculo_meta,
        "drone_meta": drone_meta,
        "baterias_por_drone": baterias_por_drone,
        "veiculo_prefill": veiculo_prefill,
        "drone_prefill": drone_prefill,
    }


def _build_veiculo_prefill(veiculo_ids):
    if not veiculo_ids:
        return {}

    prefill = {}
    ultimos = (
        ChecklistSemanalVeiculo.query
        .filter(ChecklistSemanalVeiculo.veiculo_id.in_(veiculo_ids))
        .order_by(
            ChecklistSemanalVeiculo.veiculo_id.asc(),
            ChecklistSemanalVeiculo.data_registro.desc(),
        )
        .all()
    )
    for item in ultimos:
        key = str(item.veiculo_id)
        if key not in prefill:
            prefill[key] = _serialize_checklist_veiculo(item)
    return prefill


def _build_drone_prefill(drone_ids):
    if not drone_ids:
        return {}

    prefill = {}
    ultimos = (
        ChecklistSemanalDrone.query
        .filter(ChecklistSemanalDrone.drone_id.in_(drone_ids))
        .order_by(
            ChecklistSemanalDrone.drone_id.asc(),
            ChecklistSemanalDrone.data_registro.desc(),
        )
        .all()
    )
    for item in ultimos:
        key = str(item.drone_id)
        if key not in prefill:
            prefill[key] = _serialize_checklist_drone(item)
    return prefill


def _save_vehicle_checklist(user, veiculo_id, veiculos_equipe, form_data, assinatura_piloto, actor_filter, week_bounds):
    veiculo = next((item for item in veiculos_equipe if item.id == veiculo_id), None)
    if not veiculo:
        raise PilotoChecklistError("Selecione um veiculo valido da sua equipe.")

    checklist = (
        ChecklistSemanalVeiculo.query
        .filter(
            ChecklistSemanalVeiculo.veiculo_id == veiculo_id,
            actor_filter["veiculo"],
            ChecklistSemanalVeiculo.data_registro >= week_bounds["inicio_dt"],
            ChecklistSemanalVeiculo.data_registro < week_bounds["proxima_dt"],
        )
        .first()
    )
    if not checklist:
        checklist = ChecklistSemanalVeiculo(
            veiculo_id=veiculo_id,
            piloto_id=actor_filter["piloto_id"],
            equipe_id=actor_filter["equipe_id"],
        )
        db.session.add(checklist)

    checklist.data_registro = datetime.now()
    checklist.km_leitura = float(veiculo.km_atual or 0)

    for field in CHECKLIST_VEICULO_BOOL_FIELDS:
        setattr(checklist, field, _bool_from_form(form_data.get(field), default=True))
    for field in CHECKLIST_VEICULO_TEXT_FIELDS:
        setattr(checklist, field, _clean_str(form_data.get(field)))

    checklist.assinatura_piloto = assinatura_piloto


def _save_drone_checklist(user, drone_id, baterias_por_drone, form_data, assinatura_piloto, nome_responsavel, actor_filter, week_bounds):
    checklist = (
        ChecklistSemanalDrone.query
        .filter(
            ChecklistSemanalDrone.drone_id == drone_id,
            actor_filter["drone"],
            ChecklistSemanalDrone.data_registro >= week_bounds["inicio_dt"],
            ChecklistSemanalDrone.data_registro < week_bounds["proxima_dt"],
        )
        .first()
    )
    if not checklist:
        checklist = ChecklistSemanalDrone(
            drone_id=drone_id,
            piloto_id=actor_filter["piloto_id"],
            equipe_id=actor_filter["equipe_id"],
        )
        db.session.add(checklist)

    checklist.data_registro = datetime.now()

    for field in CHECKLIST_DRONE_BOOL_FIELDS:
        setattr(checklist, field, _bool_from_form(form_data.get(field), default=True))
    for field in CHECKLIST_DRONE_TEXT_FIELDS:
        setattr(checklist, field, _clean_str(form_data.get(field)))

    default_baterias = baterias_por_drone.get(drone_id, 0)
    checklist.num_baterias = _to_int(form_data.get("num_baterias")) or int(default_baterias or 0)
    checklist.num_baterias_wb = _to_int(form_data.get("num_baterias_wb")) or 0
    checklist.assinatura_piloto = assinatura_piloto
    checklist.nome_responsavel = nome_responsavel
    checklist.assinatura_piloto_responsavel = assinatura_piloto


def _sincronizar_pendencias(user, piloto_nome, pendencias_semanais, semana_inicio):
    if getattr(user, "piloto_id", None):
        detalhe_link = url_for(
            "main.admin_checklist_semanal_detalhe",
            piloto_id=user.piloto_id,
            semana_inicio=semana_inicio.isoformat(),
        )
    else:
        detalhe_link = url_for("main.admin_checklists_semanais", q=piloto_nome)
    titulo = f"Pendencias no checklist semanal de {piloto_nome}"
    admin_ids = [row[0] for row in db.session.query(Usuario.id).filter(Usuario.tipo_usuario == "admin").all()]
    _sincronizar_notificacoes_pendencia_checklist(
        admin_ids=admin_ids,
        link=detalhe_link,
        titulo=titulo,
        mensagem=" | ".join(pendencias_semanais) if pendencias_semanais else None,
    )


def _sincronizar_notificacoes_pendencia_checklist(admin_ids, link, titulo, mensagem=None):
    if not admin_ids or not link:
        return

    existentes = {}
    for notificacao in (
        Notificacao.query
        .filter(
            Notificacao.usuario_id.in_(admin_ids),
            Notificacao.link == link,
        )
        .order_by(Notificacao.id.desc())
        .all()
    ):
        if notificacao.usuario_id not in existentes:
            existentes[notificacao.usuario_id] = notificacao

    agora = agora_brasilia_naive()
    if mensagem:
        for admin_id in admin_ids:
            notificacao = existentes.get(admin_id)
            if notificacao:
                notificacao.titulo = titulo
                notificacao.mensagem = mensagem
                notificacao.criada_em = agora
                notificacao.lida_em = None
                notificacao.apagada_em = None
            else:
                criar_notificacao(
                    usuario_id=admin_id,
                    titulo=titulo,
                    mensagem=mensagem,
                    link=link,
                    commit=False,
                )
        return

    for notificacao in existentes.values():
        if notificacao.apagada_em is None:
            notificacao.apagada_em = agora


def _coletar_pendencias_checklists_semanais(actor_filter, inicio_semana_dt, proxima_semana_dt):
    pendencias = []

    checklists_veiculo = (
        ChecklistSemanalVeiculo.query
        .options(joinedload(ChecklistSemanalVeiculo.veiculo))
        .filter(
            actor_filter["veiculo"],
            ChecklistSemanalVeiculo.data_registro >= inicio_semana_dt,
            ChecklistSemanalVeiculo.data_registro < proxima_semana_dt,
        )
        .order_by(ChecklistSemanalVeiculo.data_registro.desc())
        .all()
    )
    for checklist in checklists_veiculo:
        defeitos = _campos_defeituosos_checklist(checklist, CHECKLIST_VEICULO_BOOL_LABELS)
        if defeitos:
            pendencias.append(f"Veiculo {_identificacao_checklist_veiculo(checklist)}: {', '.join(defeitos)}")

    checklists_drone = (
        ChecklistSemanalDrone.query
        .options(joinedload(ChecklistSemanalDrone.drone))
        .filter(
            actor_filter["drone"],
            ChecklistSemanalDrone.data_registro >= inicio_semana_dt,
            ChecklistSemanalDrone.data_registro < proxima_semana_dt,
        )
        .order_by(ChecklistSemanalDrone.data_registro.desc())
        .all()
    )
    for checklist in checklists_drone:
        defeitos = _campos_defeituosos_checklist(checklist, CHECKLIST_DRONE_BOOL_LABELS)
        if defeitos:
            pendencias.append(f"Drone {_identificacao_checklist_drone(checklist)}: {', '.join(defeitos)}")

    return pendencias


def _campos_defeituosos_checklist(checklist, labels):
    defeitos = []
    for field, label in labels:
        if not bool(getattr(checklist, field)):
            defeitos.append(label)
    return defeitos


def _identificacao_checklist_veiculo(checklist):
    veiculo = checklist.veiculo
    if veiculo and veiculo.placa:
        return veiculo.placa
    if veiculo and veiculo.modelo:
        return veiculo.modelo
    return f"ID {checklist.veiculo_id}"


def _identificacao_checklist_drone(checklist):
    drone = checklist.drone
    if drone and drone.renomacao:
        return drone.renomacao
    if drone and drone.modelo:
        return drone.modelo
    return f"ID {checklist.drone_id}"


def _piloto_vinculo_ativo(user):
    if not getattr(user, "piloto_id", None):
        return None

    return (
        EquipePiloto.query
        .join(Equipe, Equipe.id == EquipePiloto.equipe_id)
        .options(joinedload(EquipePiloto.equipe))
        .filter(
            EquipePiloto.piloto_id == user.piloto_id,
            Equipe.ativa.is_(True),
        )
        .order_by(
            db.case((EquipePiloto.papel == "piloto", 0), else_=1),
            EquipePiloto.criado_em.desc(),
        )
        .first()
    )


def _is_equipe_oceano(user):
    return getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE


def _parse_equipe_oceano_id(user):
    raw = (getattr(user, "codigo_setor", None) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _equipe_operacional_ativa(user):
    if _is_equipe_oceano(user):
        equipe_id = _parse_equipe_oceano_id(user)
        if not equipe_id:
            return None
        query = Equipe.query.filter(Equipe.id == equipe_id, Equipe.ativa.is_(True))
        prefeitura_id = getattr(user, "prefeitura_id", None)
        if prefeitura_id is not None:
            query = query.filter(Equipe.prefeitura_id == prefeitura_id)
        return query.first()

    vinculo = _piloto_vinculo_ativo(user)
    if not vinculo or not vinculo.equipe_id:
        return None
    return vinculo.equipe


def _checklist_actor_filter(user, equipe):
    if _is_equipe_oceano(user):
        equipe_id = equipe.id if equipe else _parse_equipe_oceano_id(user)
        return {
            "piloto_id": None,
            "equipe_id": equipe_id,
            "veiculo": ChecklistSemanalVeiculo.equipe_id == equipe_id,
            "drone": ChecklistSemanalDrone.equipe_id == equipe_id,
        }

    piloto_id = getattr(user, "piloto_id", None)
    return {
        "piloto_id": piloto_id,
        "equipe_id": None,
        "veiculo": ChecklistSemanalVeiculo.piloto_id == piloto_id,
        "drone": ChecklistSemanalDrone.piloto_id == piloto_id,
    }


def _piloto_nome(user):
    if _is_equipe_oceano(user):
        equipe = _equipe_operacional_ativa(user)
        if equipe:
            return equipe.nome_equipe

    if getattr(user, "piloto", None) and user.piloto:
        return user.piloto.nome_piloto
    return getattr(user, "nome_uvis", "") or ""


def _serialize_checklist_veiculo(checklist):
    data = {}
    for field in CHECKLIST_VEICULO_BOOL_FIELDS + CHECKLIST_VEICULO_TEXT_FIELDS:
        data[field] = getattr(checklist, field)
    data["km_leitura"] = checklist.km_leitura
    data["assinatura_piloto"] = checklist.assinatura_piloto or ""
    return data


def _serialize_checklist_drone(checklist):
    data = {}
    for field in CHECKLIST_DRONE_BOOL_FIELDS + CHECKLIST_DRONE_TEXT_FIELDS:
        data[field] = getattr(checklist, field)
    data["num_baterias"] = checklist.num_baterias
    data["num_baterias_wb"] = checklist.num_baterias_wb
    data["assinatura_piloto"] = checklist.assinatura_piloto or ""
    data["nome_responsavel"] = checklist.nome_responsavel or ""
    return data


def _bool_from_form(value, default=True):
    value = _clean(value)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "sim", "ok", "bom"}


def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value != "" else None


def _clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _week_bounds():
    hoje = date.today()
    inicio = hoje - timedelta(days=hoje.weekday())
    fim = inicio + timedelta(days=6)
    inicio_dt = datetime.combine(inicio, datetime.min.time())
    proxima_dt = inicio_dt + timedelta(days=7)
    return {
        "inicio": inicio,
        "fim": fim,
        "inicio_dt": inicio_dt,
        "proxima_dt": proxima_dt,
    }
