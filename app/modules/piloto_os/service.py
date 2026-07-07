import json
import os
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, lazyload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    Baterias,
    DjiFlightKmlRoute,
    Drones,
    Equipe,
    EquipePiloto,
    OrdemServico,
    Solicitacao,
    Usuario,
    Veiculos,
)
from app.shared.access import (
    ADMIN_PANEL_EDIT_TYPES,
    ADMIN_PANEL_VIEW_TYPES,
    apply_solicitacao_prefeitura_scope,
    can_access_regiao,
)
from app.shared.query_filters import aplicar_filtros_base, id_search_clause
from app.shared.os_history_filters import (
    apply_os_history_filters,
    apply_retorno_automatico_filter,
    get_os_history_filters,
)
from app.shared.retorno_ciclo import (
    build_retorno_ciclo_context,
    build_retorno_ciclo_summaries,
    get_accessible_solicitacao_for_retorno_ciclo,
)
from app.shared.skybox import (
    SkyboxError,
    build_os_media_remote_path,
    build_os_video_remote_path,
    delete_skybox_file,
    is_skybox_path,
    skybox_enabled,
    upload_file_to_skybox,
)


STATUS_OS_APROVADAS = [
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADA",
    "APROVADA COM RECOMENDACOES",
]
STATUS_OS_APROVADAS_COM_ACENTO = [
    "APROVADO",
    "APROVADO COM RECOMENDACOES",
    "APROVADA",
    "APROVADA COM RECOMENDACOES",
    "APROVADO COM RECOMENDA\u00c7\u00d5ES",
    "APROVADA COM RECOMENDA\u00c7\u00d5ES",
]
STATUS_OS_CONCLUIDAS = ["CONCLUIDO", "CONCLU\u00cdDO"]
OS_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
OS_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "m4v", "lrf"}
EQUIPE_OCEANO_USER_TYPE = "equipe_oceano"
UVIS_MEDIA_VIEW_TYPES = {"uvis", "equipe_uvis"}
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
DRONE_CATEGORY_PULVERIZACAO = "pulverizacao"
DRONE_CATEGORY_MONITORAMENTO = "monitoramento"
WEBDAV_MARKER_PREFIX = "webdav://"
WEBDAV_DELETE_TIMEOUT = (30, 300)


OS_APLICACAO_REQUIRED_FIELDS = (
    ("situacao_aplicacao", "Situacao da aplicacao"),
    ("larva_visualizada", "Larva visualizada"),
    ("distrito_administrativo", "DA (Distrito)"),
    ("nome_rf_ace_responsavel_os", "Nome/RF do ACE responsavel"),
    ("criadouro_os_tipo_volume", "Criadouro OS (tipo/volume)"),
    ("data_aplicacao", "Data aplicacao"),
    ("hora_inicio_aplicacao", "Hora inicio"),
    ("hora_termino_aplicacao", "Hora termino"),
    ("tratamento_adicional_realizado", "Tratamento adicional"),
    ("descricao_produto", "Descricao produto"),
    ("formulacao_produto", "Formulacao"),
    ("dosagem_g_10l", "Dosagem (g/10L)"),
    ("tipo_aplicacao", "Tipo aplicacao"),
    ("quantidade_produto_administrada_ml", "Qtd administrada (ml)"),
    ("pulverizacao_area_l_ha", "Pulverizacao area (l/ha)"),
    ("ponta_pulverizacao", "Ponta de pulverizacao"),
)


class PilotoOsError(Exception):
    def __init__(self, message, category="warning", *, redirect_endpoint="main.piloto_os"):
        super().__init__(message)
        self.category = category
        self.redirect_endpoint = redirect_endpoint


def _normalize_drone_category(value):
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _split_drones_by_category(drones):
    pulverizacao = []
    monitoramento = []
    for drone in drones:
        category = _normalize_drone_category(drone.categoria)
        if category == DRONE_CATEGORY_PULVERIZACAO:
            pulverizacao.append(drone)
        elif category == DRONE_CATEGORY_MONITORAMENTO:
            monitoramento.append(drone)
    return pulverizacao, monitoramento


def _is_blank_os_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _validar_campos_aplicacao_para_conclusao(ordem):
    if ordem is None:
        raise PilotoOsError(
            "Preencha e salve o formulario antes de concluir a OS.",
            "conclusao_bloqueada",
            redirect_endpoint="main.piloto_os_formulario_view",
        )

    campos_faltando = [
        label
        for field_name, label in OS_APLICACAO_REQUIRED_FIELDS
        if _is_blank_os_value(getattr(ordem, field_name, None))
    ]

    if (
        (ordem.tratamento_adicional_realizado or "").strip().upper() == "SIM"
        and _is_blank_os_value(ordem.quantos_quais)
    ):
        campos_faltando.append("Quantos? Quais?")

    if campos_faltando:
        preview = ", ".join(campos_faltando[:6])
        if len(campos_faltando) > 6:
            preview = f"{preview} e mais {len(campos_faltando) - 6} campo(s)"
        raise PilotoOsError(
            f"Para concluir a OS, preencha e salve os campos de aplicacao pendentes: {preview}.",
            "conclusao_bloqueada",
            redirect_endpoint="main.piloto_os_formulario_view",
        )


def _dji_kml_date_window(solicitacao, ordem):
    reference_date = (
        getattr(ordem, "data_aplicacao", None)
        or getattr(solicitacao, "data_agendamento", None)
    )
    if not reference_date and getattr(ordem, "respondido_em", None):
        reference_date = ordem.respondido_em.date()
    if not reference_date:
        return None, None

    start_dt = datetime.combine(reference_date, datetime.min.time()) - timedelta(days=7)
    end_dt = datetime.combine(reference_date, datetime.max.time()) + timedelta(days=7)
    return start_dt, end_dt


def _build_dji_kml_route_options(solicitacao, ordem):
    query = (
        DjiFlightKmlRoute.query
        .options(joinedload(DjiFlightKmlRoute.flight_record))
    )

    start_dt, end_dt = _dji_kml_date_window(solicitacao, ordem)
    if start_dt and end_dt:
        query = query.filter(
            or_(
                DjiFlightKmlRoute.route_timestamp.is_(None),
                DjiFlightKmlRoute.route_timestamp.between(start_dt, end_dt),
            )
        )

    routes = (
        query
        .order_by(
            DjiFlightKmlRoute.route_timestamp.is_(None).asc(),
            DjiFlightKmlRoute.route_timestamp.desc(),
            DjiFlightKmlRoute.id.desc(),
        )
        .limit(120)
        .all()
    )

    selected_id = getattr(ordem, "dji_kml_route_id", None) if ordem else None
    if selected_id and all(route.id != selected_id for route in routes):
        selected = (
            DjiFlightKmlRoute.query
            .options(joinedload(DjiFlightKmlRoute.flight_record))
            .get(selected_id)
        )
        if selected:
            routes.insert(0, selected)

    return routes


def _get_selected_dji_route(ordem):
    return getattr(ordem, "dji_kml_route", None) if ordem else None


def _get_valid_dji_kml_route(user, route_id):
    if not route_id:
        return None
    route = (
        DjiFlightKmlRoute.query
        .options(joinedload(DjiFlightKmlRoute.flight_record))
        .get(route_id)
    )
    if not route:
        raise PilotoOsError(
            "Selecione uma rota KML importada valida para vincular a OS.",
            "danger",
            redirect_endpoint=_drone_form_error_redirect(user),
        )
    return route


def _drone_form_error_redirect(user):
    if getattr(user, "tipo_usuario", None) in ADMIN_PANEL_VIEW_TYPES:
        return "main.admin_os_formulario_view"
    return "main.piloto_os_formulario_view"


def _get_valid_os_drone(user, solicitacao, drone_id, expected_category, field_label):
    drone = Drones.query.get(drone_id)
    redirect_endpoint = _drone_form_error_redirect(user)
    if not drone or drone.equipe_id != solicitacao.equipe_id:
        raise PilotoOsError(
            f"Selecione um {field_label} pertencente a equipe desta OS.",
            "danger",
            redirect_endpoint=redirect_endpoint,
        )
    if (drone.status or "").strip().lower() != "ativo":
        raise PilotoOsError(
            f"O {field_label} selecionado nao esta ativo.",
            "danger",
            redirect_endpoint=redirect_endpoint,
        )
    if _normalize_drone_category(drone.categoria) != expected_category:
        raise PilotoOsError(
            f"O equipamento selecionado nao esta cadastrado como {field_label}.",
            "danger",
            redirect_endpoint=redirect_endpoint,
        )
    return drone


def is_piloto_os_user(user):
    return getattr(user, "tipo_usuario", None) in {"piloto", EQUIPE_OCEANO_USER_TYPE}


def _parse_equipe_id_from_user(user):
    try:
        return int((getattr(user, "codigo_setor", None) or "").strip())
    except (TypeError, ValueError):
        return None


def _buscar_equipe_operacional_usuario(user):
    equipe_id = _parse_equipe_id_from_user(user)
    if not equipe_id:
        raise PilotoOsError("Conta de equipe sem vinculo operacional.", "danger", redirect_endpoint="main.piloto_os")

    equipe = (
        Equipe.query
        .filter(
            Equipe.id == equipe_id,
            Equipe.ativa.is_(True),
        )
        .first()
    )
    if not equipe:
        raise PilotoOsError("Equipe operacional inativa ou nao encontrada.", "danger", redirect_endpoint="main.piloto_os")
    return equipe


def _buscar_equipe_do_usuario_na_os(user, equipe_id):
    if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe = _buscar_equipe_operacional_usuario(user)
        return equipe if equipe.id == equipe_id else None

    vinculo = _buscar_vinculo_piloto_na_equipe(getattr(user, "piloto_id", None), equipe_id)
    return vinculo.equipe if vinculo else None


def current_piloto_dashboard_date():
    return datetime.now(BRAZIL_TZ).date()


def build_piloto_os_context(user, args, google_maps_key):
    hoje = current_piloto_dashboard_date()
    busca = (args.get("q") or "").strip()

    is_equipe_oceano = getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE
    if not is_equipe_oceano and not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.piloto_os")

    piloto = getattr(user, "piloto", None)
    vinculo = None
    equipe = None
    if is_equipe_oceano:
        equipe = _buscar_equipe_operacional_usuario(user)
    else:
        vinculo = _buscar_vinculo_ativo_piloto(user.piloto_id)
        equipe = vinculo.equipe if vinculo else None

    if not equipe:
        return {
            "sem_equipe_ativa": True,
            "pedidos": [],
            "paginacao": None,
            "status_ok": STATUS_OS_APROVADAS_COM_ACENTO,
            "pilot_team_nome": None,
            "pilot_team_regiao": None,
            "pilot_team_papel": None,
            "pilot_regiao_principal": getattr(piloto, "regiao", None),
            "pilot_regiao_alternativa": getattr(piloto, "regiao_alternativa", None),
            "google_maps_key": google_maps_key,
            "drones_equipe": [],
            "baterias_equipe": [],
            "veiculos_equipe": [],
            "busca": busca,
            "data_hoje": hoje,
        }

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(
            Solicitacao.equipe_id == equipe.id,
            Solicitacao.status.in_(STATUS_OS_APROVADAS_COM_ACENTO),
            Solicitacao.data_agendamento == hoje,
        )
    )

    if busca:
        termo = f"%{busca}%"
        criterios_busca = [
            Solicitacao.protocolo.ilike(termo),
            Solicitacao.logradouro.ilike(termo),
            Solicitacao.numero.ilike(termo),
            Solicitacao.complemento.ilike(termo),
            Solicitacao.bairro.ilike(termo),
            Solicitacao.cidade.ilike(termo),
            Solicitacao.foco.ilike(termo),
            Solicitacao.equipe_uvis_nome.ilike(termo),
            Solicitacao.usuario.has(Usuario.nome_uvis.ilike(termo)),
            id_search_clause(Solicitacao.id, busca, prefixes=("id", "os")),
        ]
        query = query.filter(or_(*criterios_busca))

    query = apply_retorno_automatico_filter(query, args.get("retorno_automatico"))

    filtro_data = args.get("data")
    uvis_id = args.get("uvis_id")
    query = aplicar_filtros_base(query, filtro_data, uvis_id)

    page = args.get("page", 1, type=int)
    paginacao = (
        query.order_by(
            Solicitacao.data_agendamento.asc(),
            Solicitacao.hora_agendamento.asc(),
        )
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {
        "sem_equipe_ativa": False,
        "pedidos": paginacao.items,
        "paginacao": paginacao,
        "status_ok": STATUS_OS_APROVADAS_COM_ACENTO,
        "pilot_team_nome": equipe.nome_equipe,
        "pilot_team_regiao": equipe.regiao,
        "pilot_team_papel": "equipe" if is_equipe_oceano else (vinculo.papel or "").lower(),
        "pilot_regiao_principal": getattr(piloto, "regiao", None),
        "pilot_regiao_alternativa": getattr(piloto, "regiao_alternativa", None),
        "google_maps_key": google_maps_key,
        "drones_equipe": (
            Drones.query
            .options(joinedload(Drones.equipe))
            .filter(Drones.equipe_id == equipe.id)
            .order_by(Drones.renomacao.asc())
            .all()
        ),
        "baterias_equipe": (
            Baterias.query
            .join(Drones, Baterias.drone_id == Drones.id)
            .filter(Drones.equipe_id == equipe.id)
            .order_by(Baterias.renomacao.asc())
            .all()
        ),
        "retorno_ciclos": build_retorno_ciclo_summaries(user, paginacao.items),
        "busca": busca,
        "data_hoje": hoje,
        "veiculos_equipe": (
            Veiculos.query
            .filter(Veiculos.equipe_id == equipe.id)
            .order_by(Veiculos.operacao.asc(), Veiculos.modelo.asc())
            .all()
        ),
    }


def build_piloto_os_historico_context(user, args):
    if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe = _buscar_equipe_operacional_usuario(user)
        equipes_filter = Solicitacao.equipe_id == equipe.id
    elif not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.piloto_os")
    else:
        equipes_vinculadas = (
            db.session.query(EquipePiloto.equipe_id)
            .filter(
                EquipePiloto.piloto_id == user.piloto_id,
                EquipePiloto.equipe_id.isnot(None),
            )
            .distinct()
        )
        equipes_filter = Solicitacao.equipe_id.in_(equipes_vinculadas)

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(
            equipes_filter,
            Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
        )
    )

    filtros = get_os_history_filters(args)
    query = apply_os_history_filters(query, filtros)

    unidades_select = (
        Usuario.query
        .join(Solicitacao, Solicitacao.usuario_id == Usuario.id)
        .filter(equipes_filter, Solicitacao.status.in_(STATUS_OS_CONCLUIDAS))
        .distinct()
        .order_by(Usuario.nome_uvis.asc())
        .all()
    )

    page = args.get("page", 1, type=int)
    paginacao = (
        query
        .order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {
        "pedidos": paginacao.items,
        "paginacao": paginacao,
        "filtros": filtros,
        "unidades_select": unidades_select,
        "pagination_args": {key: value for key, value in filtros.items() if value},
        "retorno_ciclos": build_retorno_ciclo_summaries(user, paginacao.items),
    }


def concluir_os_piloto(user, os_id):
    if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE and not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.piloto_os")

    solicitacao = Solicitacao.query.get_or_404(os_id)

    if solicitacao.status not in STATUS_OS_APROVADAS_COM_ACENTO:
        raise PilotoOsError("A OS nao esta aprovada.", "warning")

    if not solicitacao.equipe_id:
        raise PilotoOsError("Esta OS nao possui equipe atribuida.", "danger")

    equipe = _buscar_equipe_do_usuario_na_os(user, solicitacao.equipe_id)
    if not equipe:
        raise PilotoOsError("Voce nao faz parte da equipe atribuida a esta OS.", "danger")

    _validar_campos_aplicacao_para_conclusao(solicitacao.ordem_servico)

    solicitacao.status = "CONCLU\u00cdDO"
    db.session.commit()

    equipe_nome = equipe.nome_equipe if equipe else None
    papel = "equipe" if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE else None

    if equipe_nome and papel:
        return f"OS #{solicitacao.id} concluida! Equipe: {equipe_nome} | Papel: {papel}."
    if equipe_nome:
        return f"OS #{solicitacao.id} concluida! Equipe: {equipe_nome}."
    return f"OS #{solicitacao.id} concluida com sucesso!"


def build_piloto_os_form_context(user, os_id):
    if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE and not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.piloto_os")

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .filter(Solicitacao.id == os_id)
    )
    solicitacao = apply_solicitacao_prefeitura_scope(query, user).first_or_404()

    status_permitidos = set(STATUS_OS_APROVADAS_COM_ACENTO + STATUS_OS_CONCLUIDAS)
    if solicitacao.status not in status_permitidos:
        raise PilotoOsError("Esta OS nao esta liberada para preenchimento do formulario.", "warning")

    if not solicitacao.equipe_id:
        raise PilotoOsError("Esta OS nao possui equipe atribuida.", "danger")

    equipe = _buscar_equipe_do_usuario_na_os(user, solicitacao.equipe_id)
    if not equipe:
        raise PilotoOsError("Voce nao tem permissao para acessar esta OS.", "danger")

    ordem = solicitacao.ordem_servico
    calculo_dosagem_planejado = _parse_json_object(
        getattr(ordem, "calculo_dosagem_planejado", None) if ordem else None
    )
    drones_equipe = (
        Drones.query
        .filter(
            Drones.equipe_id == solicitacao.equipe_id,
            Drones.status == "Ativo",
        )
        .order_by(Drones.renomacao.asc())
        .all()
    )
    drones_pulverizacao, drones_monitoramento = _split_drones_by_category(drones_equipe)
    dji_kml_routes = _build_dji_kml_route_options(solicitacao, ordem)
    selected_dji_route = _get_selected_dji_route(ordem)

    respondido_por_padrao = ""
    if getattr(user, "piloto", None):
        respondido_por_padrao = user.piloto.nome_piloto or ""
    else:
        respondido_por_padrao = getattr(user, "nome_uvis", "") or ""

    return {
        "solicitacao": solicitacao,
        "equipe": equipe,
        "ordem": ordem,
        "modo_visualizacao": (solicitacao.status or "").strip().upper() in {"CONCLUIDO", "CONCLU\u00cdDO"},
        "uvis_nome": solicitacao.usuario.nome_uvis if solicitacao.usuario else "",
        "regiao_nome": (
            getattr(solicitacao.usuario, "regiao", None)
            or getattr(equipe, "regiao", None)
            or ""
        ),
        "endereco_os": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ),
        "data_coleta_imagem_label": _build_data_coleta_imagem_label(solicitacao, ordem),
        "piloto_padrao": (
            equipe.piloto_titular.nome_piloto if equipe and equipe.piloto_titular else ""
        ) if equipe else "",
        "auxiliar_padrao": (
            equipe.piloto_auxiliar.nome_piloto if equipe and equipe.piloto_auxiliar else ""
        ) if equipe else "",
        "respondido_por_padrao": respondido_por_padrao,
        "respondido_em_value": (
            ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
            if ordem and ordem.respondido_em else datetime.now().strftime("%Y-%m-%dT%H:%M")
        ),
        "calculo_dosagem_planejado": calculo_dosagem_planejado,
        "calculo_dosagem_planejado_json": (
            json.dumps(calculo_dosagem_planejado, ensure_ascii=False)
            if calculo_dosagem_planejado else ""
        ),
        "drones_equipe": drones_equipe,
        "drones_pulverizacao": drones_pulverizacao,
        "drones_monitoramento": drones_monitoramento,
        "dji_kml_routes": dji_kml_routes,
        "selected_dji_route": selected_dji_route,
        "retorno_ciclo": build_retorno_ciclo_context(user, os_id),
        **_build_os_media_context(ordem),
    }


def salvar_piloto_os_form(user, os_id, form_data, files_data, root_path):
    context = build_piloto_os_form_context(user, os_id)

    if context["modo_visualizacao"]:
        raise PilotoOsError(
            "Esta OS ja foi concluida e nao pode mais ser editada pelo piloto.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )

    solicitacao = context["solicitacao"]
    ordem = context["ordem"]

    if ordem is None:
        ordem = _get_or_create_ordem_servico_for_solicitacao(solicitacao)

    _aplicar_campos_formulario(
        user=user,
        solicitacao=solicitacao,
        ordem=ordem,
        form_data=form_data,
        files_data=files_data,
        root_path=root_path,
        piloto_padrao=context["piloto_padrao"],
        auxiliar_padrao=context["auxiliar_padrao"],
        respondido_por_padrao=context["respondido_por_padrao"],
    )

    gerar_retorno = ((ordem.retornar_proxima_semana_monitorar_larvas or "").strip().upper() == "SIM")
    if gerar_retorno:
        retorno_existente = Solicitacao.query.filter_by(origem_retorno_id=solicitacao.id).first()
        if not retorno_existente:
            criar_solicitacao_retorno_monitoramento(solicitacao, ordem)

    db.session.commit()

    if gerar_retorno:
        return "Formulario salvo com sucesso! Uma nova OS de retorno foi criada para 7 dias depois."
    return "Formulario salvo com sucesso!"


def get_piloto_drone_payload(user, drone_id):
    if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE and not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo.", "danger")

    drone = Drones.query.get_or_404(drone_id)
    if not drone.equipe_id:
        raise PilotoOsError("Drone sem equipe.", "danger")

    equipe = _buscar_equipe_do_usuario_na_os(user, drone.equipe_id)
    if not equipe:
        raise PilotoOsError("Sem permissao.", "danger")

    return {
        "id": drone.id,
        "renomacao": drone.renomacao,
        "modelo": drone.modelo,
        "numero_serie": drone.numero_serie,
        "registro_anatel": drone.registro_anatel,
        "registro_anac": drone.registro_anac,
        "status": drone.status,
        "categoria": drone.categoria,
        "pmd_kg": drone.pmd_kg,
        "ano_fabricacao": drone.ano_fabricacao,
    }


def build_admin_os_form_context(user, os_id):
    if getattr(user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
        raise PilotoOsError("Acesso restrito.", "danger", redirect_endpoint="main.dashboard")

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .filter(Solicitacao.id == os_id)
    )
    solicitacao = apply_solicitacao_prefeitura_scope(query, user).first_or_404()
    pedido_regiao = getattr(getattr(solicitacao, "usuario", None), "regiao", None)
    if not can_access_regiao(user, pedido_regiao):
        raise PilotoOsError("Voce nao tem permissao para acessar esta OS.", "danger", redirect_endpoint="main.dashboard")

    pode_editar_formulario = _admin_can_edit_os_form(user, solicitacao)
    equipe = solicitacao.equipe
    ordem = solicitacao.ordem_servico
    calculo_dosagem_planejado = _parse_json_object(
        getattr(ordem, "calculo_dosagem_planejado", None) if ordem else None
    )
    drones_equipe = []
    if solicitacao.equipe_id:
        drones_equipe = (
            Drones.query
            .filter(
                Drones.equipe_id == solicitacao.equipe_id,
                Drones.status == "Ativo",
            )
            .order_by(Drones.renomacao.asc())
            .all()
        )
    drones_pulverizacao, drones_monitoramento = _split_drones_by_category(drones_equipe)
    dji_kml_routes = _build_dji_kml_route_options(solicitacao, ordem)
    selected_dji_route = _get_selected_dji_route(ordem)

    return {
        "solicitacao": solicitacao,
        "equipe": equipe,
        "ordem": ordem,
        "modo_visualizacao": not pode_editar_formulario,
        "alerta_edicao_concluida": (
            pode_editar_formulario
            and (solicitacao.status or "").strip().upper() in {"CONCLUIDO", "CONCLUÍDO"}
        ),
        "uvis_nome": solicitacao.usuario.nome_uvis if solicitacao.usuario else "",
        "regiao_nome": (
            getattr(solicitacao.usuario, "regiao", None)
            or getattr(equipe, "regiao", None)
            or ""
        ),
        "endereco_os": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ),
        "data_coleta_imagem_label": _build_data_coleta_imagem_label(solicitacao, ordem),
        "piloto_padrao": (
            equipe.piloto_titular.nome_piloto if equipe and equipe.piloto_titular else ""
        ) if equipe else "",
        "auxiliar_padrao": (
            equipe.piloto_auxiliar.nome_piloto if equipe and equipe.piloto_auxiliar else ""
        ) if equipe else "",
        "respondido_por_padrao": getattr(user, "nome_uvis", "") or "",
        "respondido_em_value": (
            ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
            if ordem and ordem.respondido_em else datetime.now().strftime("%Y-%m-%dT%H:%M")
        ),
        "calculo_dosagem_planejado": calculo_dosagem_planejado,
        "calculo_dosagem_planejado_json": (
            json.dumps(calculo_dosagem_planejado, ensure_ascii=False)
            if calculo_dosagem_planejado else ""
        ),
        "drones_equipe": drones_equipe,
        "drones_pulverizacao": drones_pulverizacao,
        "drones_monitoramento": drones_monitoramento,
        "dji_kml_routes": dji_kml_routes,
        "selected_dji_route": selected_dji_route,
        "retorno_ciclo": build_retorno_ciclo_context(user, os_id),
        **_build_os_media_context(ordem),
    }


def salvar_admin_os_form(user, os_id, form_data, files_data, root_path):
    context = build_admin_os_form_context(user, os_id)

    if context["modo_visualizacao"]:
        raise PilotoOsError(
            "Voce nao tem permissao para editar esta OS.",
            "danger",
            redirect_endpoint="main.admin_os_formulario_view",
        )

    solicitacao = context["solicitacao"]
    ordem = context["ordem"]

    if ordem is None:
        ordem = _get_or_create_ordem_servico_for_solicitacao(solicitacao)

    _aplicar_campos_formulario(
        user=user,
        solicitacao=solicitacao,
        ordem=ordem,
        form_data=form_data,
        files_data=files_data,
        root_path=root_path,
        piloto_padrao=context["piloto_padrao"],
        auxiliar_padrao=context["auxiliar_padrao"],
        respondido_por_padrao=context["respondido_por_padrao"],
    )

    gerar_retorno = ((ordem.retornar_proxima_semana_monitorar_larvas or "").strip().upper() == "SIM")
    if gerar_retorno:
        retorno_existente = Solicitacao.query.filter_by(origem_retorno_id=solicitacao.id).first()
        if not retorno_existente:
            criar_solicitacao_retorno_monitoramento(solicitacao, ordem)

    db.session.commit()

    if gerar_retorno:
        return "Formulario salvo com sucesso! Uma nova OS de retorno foi criada para 7 dias depois."
    return "Formulario salvo com sucesso!"


def get_os_video_path_for_user(user, os_id):
    solicitacao = get_accessible_solicitacao_for_retorno_ciclo(user, os_id)
    if getattr(user, "tipo_usuario", None) in UVIS_MEDIA_VIEW_TYPES:
        context = build_uvis_os_media_context(user, os_id)
    ordem = solicitacao.ordem_servico if solicitacao else None
    video_path = getattr(ordem, "video", None) if ordem else None
    if not video_path:
        raise PilotoOsError(
            "Esta OS nao possui video anexado.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return video_path


def get_os_principal_image_path_for_user(user, os_id):
    solicitacao = get_accessible_solicitacao_for_retorno_ciclo(user, os_id)
    if getattr(user, "tipo_usuario", None) in UVIS_MEDIA_VIEW_TYPES:
        context = build_uvis_os_media_context(user, os_id)
    ordem = solicitacao.ordem_servico if solicitacao else None
    image_path = getattr(ordem, "imagem_principal", None) if ordem else None
    if not image_path:
        raise PilotoOsError(
            "Esta OS nao possui foto principal anexada.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return image_path


def get_os_complementary_image_path_for_user(user, os_id, image_index):
    solicitacao = get_accessible_solicitacao_for_retorno_ciclo(user, os_id)
    if getattr(user, "tipo_usuario", None) in UVIS_MEDIA_VIEW_TYPES:
        context = build_uvis_os_media_context(user, os_id)
    ordem = solicitacao.ordem_servico if solicitacao else None
    imagens = _parse_json_list(getattr(ordem, "outras_imagens", None) if ordem else None)
    try:
        index = int(image_index) - 1
    except (TypeError, ValueError):
        index = -1
    if index < 0 or index >= len(imagens):
        raise PilotoOsError(
            "Imagem complementar nao encontrada.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return imagens[index]


def criar_solicitacao_retorno_monitoramento(solicitacao_original, ordem_atual):
    data_base = (
        solicitacao_original.data_agendamento
        or ordem_atual.data_aplicacao
        or date.today()
    )
    nova_data = data_base + timedelta(days=7)

    nova_observacao = (solicitacao_original.observacao or "").strip() or None

    nova_solicitacao = Solicitacao(
        data_agendamento=nova_data,
        hora_agendamento=solicitacao_original.hora_agendamento,
        foco=solicitacao_original.foco,
        tipo_operacao=solicitacao_original.tipo_operacao,
        tipo_visita=solicitacao_original.tipo_visita,
        altura_voo=solicitacao_original.altura_voo,
        criadouro=solicitacao_original.criadouro,
        apoio_cet=solicitacao_original.apoio_cet,
        observacao=nova_observacao,
        area_restrita=solicitacao_original.area_restrita,
        cep=solicitacao_original.cep,
        logradouro=solicitacao_original.logradouro,
        bairro=solicitacao_original.bairro,
        cidade=solicitacao_original.cidade,
        uf=solicitacao_original.uf,
        numero=solicitacao_original.numero,
        complemento=solicitacao_original.complemento,
        latitude=solicitacao_original.latitude,
        longitude=solicitacao_original.longitude,
        perimetro_planejado=solicitacao_original.perimetro_planejado,
        perimetro_executado=None,
        anexo_path=solicitacao_original.anexo_path,
        anexo_nome=solicitacao_original.anexo_nome,
        protocolo=None,
        justificativa=None,
        equipe_uvis_nome=solicitacao_original.equipe_uvis_nome,
        status="PENDENTE",
        usuario_id=solicitacao_original.usuario_id,
        prefeitura_id=solicitacao_original.prefeitura_id,
        piloto_id=solicitacao_original.piloto_id,
        equipe_id=solicitacao_original.equipe_id,
        origem_retorno_id=solicitacao_original.id,
        gerada_automaticamente=True,
    )

    db.session.add(nova_solicitacao)
    db.session.flush()

    nova_ordem = OrdemServico(
        solicitacao_id=nova_solicitacao.id,
        equipe_id=solicitacao_original.equipe_id,
        identificador_os="",
        respondido_por="",
        respondido_em=None,
        situacao_aplicacao="",
        larva_visualizada="",
        retornar_proxima_semana_monitorar_larvas="NAO",
        distrito_administrativo=ordem_atual.distrito_administrativo,
        nome_rf_ace_responsavel_os=ordem_atual.nome_rf_ace_responsavel_os,
        criadouro_os_tipo_volume=ordem_atual.criadouro_os_tipo_volume,
        data_aplicacao=None,
        hora_inicio_aplicacao=None,
        hora_termino_aplicacao=None,
        tratamento_adicional_realizado="",
        quantos_quais="",
        descricao_produto=ordem_atual.descricao_produto,
        formulacao_produto=ordem_atual.formulacao_produto,
        dosagem_g_10l=ordem_atual.dosagem_g_10l,
        tipo_aplicacao=ordem_atual.tipo_aplicacao,
        quantidade_produto_administrada_ml=None,
        pulverizacao_area_l_ha=ordem_atual.pulverizacao_area_l_ha,
        prefixo_aeronave_pulverizacao=ordem_atual.prefixo_aeronave_pulverizacao,
        prefixo_aeronave_monitoramento=ordem_atual.prefixo_aeronave_monitoramento,
        quantidade_videos_registradas=None,
        quantidade_imagens_registradas=None,
        ponta_pulverizacao=ordem_atual.ponta_pulverizacao,
        temperatura_c=None,
        umidade_relativa_pct=None,
        velocidade_vento_kmh=None,
        motivo_nao_realizacao="",
        observacoes="",
        piloto=ordem_atual.piloto,
        assinatura_piloto="",
        auxiliar=ordem_atual.auxiliar,
        proprietario_ou_preposto="",
        assinatura_proprietario_ou_preposto="",
        drone_id=ordem_atual.drone_id,
        drone_monitoramento_id=ordem_atual.drone_monitoramento_id,
        drone_denominacao=ordem_atual.drone_denominacao,
        drone_modelo=ordem_atual.drone_modelo,
        drone_numero_serie=ordem_atual.drone_numero_serie,
        drone_registro_anatel=ordem_atual.drone_registro_anatel,
        drone_registro_anac=ordem_atual.drone_registro_anac,
        drone_monitoramento_denominacao=ordem_atual.drone_monitoramento_denominacao,
        drone_monitoramento_modelo=ordem_atual.drone_monitoramento_modelo,
        drone_monitoramento_numero_serie=ordem_atual.drone_monitoramento_numero_serie,
        drone_monitoramento_registro_anatel=ordem_atual.drone_monitoramento_registro_anatel,
        drone_monitoramento_registro_anac=ordem_atual.drone_monitoramento_registro_anac,
    )
    db.session.add(nova_ordem)
    return nova_solicitacao


def _admin_can_edit_os_form(user, solicitacao) -> bool:
    if getattr(user, "tipo_usuario", None) not in ADMIN_PANEL_EDIT_TYPES:
        return False

    return (getattr(solicitacao, "status", "") or "").strip().upper() != "CANCELADO"


def _aplicar_campos_formulario(
    *,
    user,
    solicitacao,
    ordem,
    form_data,
    files_data,
    root_path,
    piloto_padrao,
    auxiliar_padrao,
    respondido_por_padrao,
):
    drone_pulv_id = _to_int(form_data.get("drone_id"))
    drone_monit_id = _to_int(form_data.get("drone_monitoramento_id"))

    if drone_pulv_id:
        drone_p = _get_valid_os_drone(
            user,
            solicitacao,
            drone_pulv_id,
            DRONE_CATEGORY_PULVERIZACAO,
            "drone de pulverizacao",
        )
        ordem.drone_id = drone_p.id
        ordem.drone_denominacao = drone_p.renomacao
        ordem.drone_modelo = drone_p.modelo
        ordem.drone_numero_serie = drone_p.numero_serie
        ordem.drone_registro_anatel = drone_p.registro_anatel
        ordem.drone_registro_anac = drone_p.registro_anac
        ordem.prefixo_aeronave_pulverizacao = drone_p.renomacao
    else:
        ordem.drone_id = None
        ordem.drone_denominacao = ""
        ordem.drone_modelo = ""
        ordem.drone_numero_serie = ""
        ordem.drone_registro_anatel = ""
        ordem.drone_registro_anac = ""
        ordem.prefixo_aeronave_pulverizacao = _clean_str(form_data.get("prefixo_aeronave_pulverizacao"))

    if drone_monit_id:
        drone_m = _get_valid_os_drone(
            user,
            solicitacao,
            drone_monit_id,
            DRONE_CATEGORY_MONITORAMENTO,
            "drone de monitoramento",
        )
        ordem.drone_monitoramento_id = drone_m.id
        ordem.drone_monitoramento_denominacao = drone_m.renomacao
        ordem.drone_monitoramento_modelo = drone_m.modelo
        ordem.drone_monitoramento_numero_serie = drone_m.numero_serie
        ordem.drone_monitoramento_registro_anatel = drone_m.registro_anatel
        ordem.drone_monitoramento_registro_anac = drone_m.registro_anac
        ordem.prefixo_aeronave_monitoramento = drone_m.renomacao
    else:
        ordem.drone_monitoramento_id = None
        ordem.drone_monitoramento_denominacao = ""
        ordem.drone_monitoramento_modelo = ""
        ordem.drone_monitoramento_numero_serie = ""
        ordem.drone_monitoramento_registro_anatel = ""
        ordem.drone_monitoramento_registro_anac = ""
        ordem.prefixo_aeronave_monitoramento = _clean_str(form_data.get("prefixo_aeronave_monitoramento"))

    dji_kml_route_id = _to_int(form_data.get("dji_kml_route_id"))
    dji_kml_route = _get_valid_dji_kml_route(user, dji_kml_route_id)
    ordem.dji_kml_route_id = dji_kml_route.id if dji_kml_route else None

    ordem.identificador_os = _clean_str(form_data.get("identificador_os"))
    ordem.respondido_por = _clean_str(form_data.get("respondido_por")) or respondido_por_padrao
    ordem.respondido_em = _to_datetime_local(form_data.get("respondido_em")) or datetime.now()
    ordem.situacao_aplicacao = _clean_str(form_data.get("situacao_aplicacao"))
    ordem.larva_visualizada = _clean_str(form_data.get("larva_visualizada"))
    ordem.retornar_proxima_semana_monitorar_larvas = _clean_str(form_data.get("retornar_proxima_semana_monitorar_larvas"))
    ordem.distrito_administrativo = _clean_str(form_data.get("da")) or _clean_str(form_data.get("distrito_administrativo"))
    ordem.nome_rf_ace_responsavel_os = _clean_str(form_data.get("nome_rf_ace_responsavel_os"))
    ordem.criadouro_os_tipo_volume = _clean_str(form_data.get("criadouro_os_tipo_volume"))
    ordem.data_aplicacao = _to_date(form_data.get("data_aplicacao"))
    ordem.hora_inicio_aplicacao = _to_time(form_data.get("hora_inicio_aplicacao"))
    ordem.hora_termino_aplicacao = _to_time(form_data.get("hora_termino_aplicacao"))
    ordem.tratamento_adicional_realizado = _clean_str(form_data.get("tratamento_adicional_realizado"))
    ordem.quantos_quais = _clean_str(form_data.get("quantos_quais"))
    ordem.descricao_produto = _clean_str(form_data.get("descricao_produto"))
    if ordem.descricao_produto == "BTI":
        ordem.descricao_produto = "Bti"
    ordem.formulacao_produto = _clean_str(form_data.get("formulacao_produto"))
    ordem.dosagem_g_10l = _clean_str(form_data.get("dosagem_g_10l"))
    ordem.tipo_aplicacao = _clean_str(form_data.get("tipo_aplicacao"))
    ordem.quantidade_produto_administrada_ml = _to_float(form_data.get("quantidade_produto_administrada_ml"))
    ordem.pulverizacao_area_l_ha = _to_float(form_data.get("pulverizacao_area_l_ha"))
    ordem.pulverizacao_foco_tempo_estimado_segundos = _to_float(form_data.get("pulverizacao_foco_tempo_estimado_segundos"))
    ordem.pulverizacao_foco_l_min = _to_float(form_data.get("pulverizacao_foco_l_min"))
    ordem.quantidade_imagens_registradas = _to_int(form_data.get("quantidade_imagens_registradas"))
    ordem.quantidade_videos_registradas = _to_int(form_data.get("quantidade_videos_registradas"))
    ordem.ponta_pulverizacao = _clean_str(form_data.get("ponta_pulverizacao"))
    ordem.temperatura_c = _to_float(form_data.get("temperatura_c"))
    ordem.umidade_relativa_pct = _to_float(form_data.get("umidade_relativa_pct"))
    ordem.velocidade_vento_kmh = _to_float(form_data.get("velocidade_vento_kmh"))
    ordem.motivo_nao_realizacao = _clean_str(form_data.get("motivo_nao_realizacao"))
    ordem.observacoes = _clean_str(form_data.get("observacoes"))
    ordem.piloto = _clean_str(form_data.get("piloto")) or piloto_padrao
    ordem.assinatura_piloto = _clean_str(form_data.get("assinatura_piloto"))
    ordem.auxiliar = _clean_str(form_data.get("auxiliar")) or auxiliar_padrao
    ordem.proprietario_ou_preposto = _clean_str(form_data.get("proprietario_ou_preposto"))
    ordem.assinatura_proprietario_ou_preposto = _clean_str(form_data.get("assinatura_proprietario_ou_preposto"))
    _aplicar_midias_os(
        solicitacao=solicitacao,
        ordem=ordem,
        form_data=form_data,
        files_data=files_data,
        root_path=root_path,
    )
    if ordem.quantidade_imagens_registradas is None:
        total_midias_salvas = (1 if ordem.imagem_principal else 0) + len(_parse_json_list(ordem.outras_imagens))
        if total_midias_salvas:
            ordem.quantidade_imagens_registradas = total_midias_salvas
    if ordem.quantidade_videos_registradas is None and ordem.video:
        ordem.quantidade_videos_registradas = 1


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


def _to_float(value):
    value = _clean(value)
    if value is None:
        return None

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")

    try:
        return float(value)
    except Exception:
        return None


def _to_date(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _to_time(value):
    value = _clean(value)
    if value is None:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except Exception:
            pass
    return None


def _to_datetime_local(value):
    value = _clean(value)
    if value is None:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return None


def _build_data_coleta_imagem_label(solicitacao, ordem):
    if ordem and ordem.data_aplicacao:
        return ordem.data_aplicacao.strftime("%d/%m/%Y")
    if ordem and ordem.respondido_em:
        return ordem.respondido_em.strftime("%d/%m/%Y")
    if solicitacao and solicitacao.data_agendamento:
        return solicitacao.data_agendamento.strftime("%d/%m/%Y")
    return ""


def _build_os_media_context(ordem):
    imagem_principal_path = getattr(ordem, "imagem_principal", None) if ordem else None
    outras_imagens_paths = _parse_json_list(getattr(ordem, "outras_imagens", None) if ordem else None)
    video_path = getattr(ordem, "video", None) if ordem else None
    video_filename = os.path.basename(str(video_path or "").replace("\\", "/")) if video_path else ""
    return {
        "imagem_principal_path": imagem_principal_path,
        "outras_imagens_paths": outras_imagens_paths,
        "video_path": video_path,
        "video_filename": video_filename,
        "total_midias_formulario": (
            (1 if imagem_principal_path else 0)
            + len(outras_imagens_paths)
            + (1 if video_path else 0)
        ),
    }


def build_os_media_context(ordem):
    return _build_os_media_context(ordem)


def _uvis_owner_id_for_media(user):
    tipo_usuario = getattr(user, "tipo_usuario", None)
    if tipo_usuario == "uvis":
        return getattr(user, "id", None)
    if tipo_usuario == "equipe_uvis":
        return getattr(user, "equipe_uvis_uvis_usuario_id", None)
    return None


def build_uvis_os_media_context(user, os_id):
    owner_id = _uvis_owner_id_for_media(user)
    if not owner_id:
        raise PilotoOsError("Acesso restrito.", "danger", redirect_endpoint="main.dashboard")

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .get_or_404(os_id)
    )

    if solicitacao.usuario_id != owner_id:
        raise PilotoOsError("Voce nao tem permissao para acessar esta OS.", "danger", redirect_endpoint="main.dashboard")

    if (solicitacao.status or "").strip().upper() not in set(STATUS_OS_CONCLUIDAS):
        raise PilotoOsError(
            "Esta OS ainda nao esta liberada para consulta de midias.",
            "warning",
            redirect_endpoint="main.uvis_historico_os",
        )

    return {
        "solicitacao": solicitacao,
        "equipe": solicitacao.equipe,
        "ordem": solicitacao.ordem_servico,
        **_build_os_media_context(solicitacao.ordem_servico),
    }


def _parse_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).replace("\\", "/") for item in value if item]
    try:
        data = json.loads(value)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).replace("\\", "/") for item in data if item]


def _parse_json_object(value):
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        data = json.loads(value)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _get_or_create_ordem_servico_for_solicitacao(solicitacao):
    solicitacao_id = solicitacao.id
    equipe_id = solicitacao.equipe_id

    with db.session.no_autoflush:
        ordem = (
            OrdemServico.query
            .options(lazyload("*"))
            .filter_by(solicitacao_id=solicitacao_id)
            .with_for_update(of=OrdemServico)
            .first()
        )
    if ordem:
        return ordem

    ordem = OrdemServico(
        solicitacao_id=solicitacao_id,
        equipe_id=equipe_id,
    )
    db.session.add(ordem)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        ordem = (
            OrdemServico.query
            .options(lazyload("*"))
            .filter_by(solicitacao_id=solicitacao_id)
            .with_for_update(of=OrdemServico)
            .first()
        )
        if ordem is None:
            raise
    return ordem


def _truncate_text(value, max_length):
    value = _clean(value)
    if value is None:
        return ""
    return str(value)[:max_length]


def _round_float(value, digits=4):
    parsed = _to_float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _sanitize_calculo_dosagem_planejado(raw_value):
    payload = _parse_json_object(raw_value)
    if not payload:
        return None

    medicao = payload.get("medicao") or {}
    resultado = payload.get("resultado") or {}
    campos = medicao.get("campos") or {}
    contexto = payload.get("contexto") or {}

    cenario = _truncate_text(payload.get("cenario"), 40)
    valor_base = _round_float(medicao.get("valor_base"))
    carga_bti_g = _round_float(resultado.get("carga_bti_g"))
    calda_total_ml = _round_float(resultado.get("calda_total_ml"))

    if not cenario or valor_base is None or carga_bti_g is None or calda_total_ml is None:
        return None

    normalizado = {
        "version": 1,
        "cenario": cenario,
        "cenario_label": _truncate_text(payload.get("cenario_label"), 80),
        "contexto": {
            "tipo_operacao": _truncate_text(contexto.get("tipo_operacao"), 60),
            "tipo_visita": _truncate_text(contexto.get("tipo_visita"), 60),
            "foco": _truncate_text(contexto.get("foco"), 120),
        },
        "medicao": {
            "modo": _truncate_text(medicao.get("modo"), 40),
            "modo_label": _truncate_text(medicao.get("modo_label"), 80),
            "medida_label": _truncate_text(medicao.get("medida_label"), 120),
            "valor_base": valor_base,
            "unidade_base": _truncate_text(medicao.get("unidade_base"), 20),
            "resumo": _truncate_text(medicao.get("resumo"), 220),
            "formula_hint": _truncate_text(medicao.get("formula_hint"), 220),
            "campos": {
                "valor_direto": _round_float(campos.get("valor_direto")),
                "comprimento_m": _round_float(campos.get("comprimento_m")),
                "largura_m": _round_float(campos.get("largura_m")),
                "altura_agua_m": _round_float(campos.get("altura_agua_m")),
                "raio_m": _round_float(campos.get("raio_m")),
                "largura_media_m": _round_float(campos.get("largura_media_m")),
                "margens": _to_int(campos.get("margens")),
            },
        },
        "resultado": {
            "descricao_produto": _truncate_text(resultado.get("descricao_produto"), 120),
            "formulacao_produto": _truncate_text(resultado.get("formulacao_produto"), 120),
            "dosagem_g_10l": _truncate_text(resultado.get("dosagem_g_10l"), 40),
            "tipo_aplicacao": _truncate_text(resultado.get("tipo_aplicacao"), 100),
            "carga_bti_g": carga_bti_g,
            "calda_total_ml": calda_total_ml,
            "calda_total_label": _truncate_text(resultado.get("calda_total_label"), 80),
            "tempo_aplicacao_segundos": _round_float(resultado.get("tempo_aplicacao_segundos")),
            "tempo_aplicacao_label": _truncate_text(resultado.get("tempo_aplicacao_label"), 80),
            "pulverizacao_area_l_ha": _round_float(resultado.get("pulverizacao_area_l_ha")),
            "ponta_pulverizacao": _truncate_text(resultado.get("ponta_pulverizacao"), 80),
            "numero_bicos": _to_int(resultado.get("numero_bicos")),
            "vazao_bicos_ml_min": _round_float(resultado.get("vazao_bicos_ml_min")),
            "dose_bti_g_min": _round_float(resultado.get("dose_bti_g_min")),
            "pressao_bar": _round_float(resultado.get("pressao_bar")),
            "faixa_aplicacao_m": _round_float(resultado.get("faixa_aplicacao_m")),
            "tamanho_gotas_dmv": _truncate_text(resultado.get("tamanho_gotas_dmv"), 40),
        },
    }

    return json.dumps(normalizado, ensure_ascii=False)


def _validar_arquivo_imagem_os(arquivo):
    nome_seguro = secure_filename((arquivo.filename or "").strip())
    ext = os.path.splitext(nome_seguro)[1].lower().lstrip(".")
    if not nome_seguro or ext not in OS_IMAGE_EXTENSIONS:
        raise PilotoOsError(
            "Envie apenas imagens nos formatos JPG, JPEG ou PNG para o levantamento.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return ext


def _validar_arquivo_video_os(arquivo):
    nome_seguro = secure_filename((arquivo.filename or "").strip())
    ext = os.path.splitext(nome_seguro)[1].lower().lstrip(".")
    if not nome_seguro or ext not in OS_VIDEO_EXTENSIONS:
        raise PilotoOsError(
            "Envie apenas videos nos formatos MP4, MOV, WEBM, M4V ou LRF/DJI para o levantamento.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return ext


def _upload_os_media_para_skybox(arquivo, os_id, nome, *, tipo="arquivo"):
    try:
        return upload_file_to_skybox(
            arquivo,
            build_os_media_remote_path(os_id, nome),
        )
    except SkyboxError as exc:
        raise PilotoOsError(
            f"Falha ao enviar {tipo} para o Skybox: {exc}",
            "danger",
            redirect_endpoint="main.piloto_os_formulario_view",
        ) from exc


def _salvar_upload_os_imagem(arquivo, root_path, os_id, prefixo, *, usar_skybox=False, copiar_skybox=False):
    if not arquivo or not arquivo.filename:
        return None

    ext = _validar_arquivo_imagem_os(arquivo)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nome = secure_filename(f"{prefixo}_os_{os_id}_{stamp}.{ext}")

    if usar_skybox and skybox_enabled():
        return _upload_os_media_para_skybox(arquivo, os_id, nome, tipo="imagem")

    pasta_destino = os.path.join(root_path, "static", "uploads", "os", str(os_id))
    os.makedirs(pasta_destino, exist_ok=True)
    arquivo.save(os.path.join(pasta_destino, nome))

    if copiar_skybox and skybox_enabled():
        _upload_os_media_para_skybox(arquivo, os_id, nome, tipo="imagem")

    return f"uploads/os/{os_id}/{nome}"


def _salvar_upload_os_video(arquivo, root_path, os_id, prefixo):
    if not arquivo or not arquivo.filename:
        return None

    ext = _validar_arquivo_video_os(arquivo)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nome = secure_filename(f"{prefixo}_os_{os_id}_{stamp}.{ext}")

    if skybox_enabled():
        try:
            return upload_file_to_skybox(arquivo, build_os_video_remote_path(os_id, nome))
        except SkyboxError as exc:
            raise PilotoOsError(
                f"Falha ao enviar o video para o Skybox: {exc}",
                "danger",
                redirect_endpoint="main.piloto_os_formulario_view",
            ) from exc

    pasta_destino = os.path.join(root_path, "static", "uploads", "os", str(os_id))
    os.makedirs(pasta_destino, exist_ok=True)
    arquivo.save(os.path.join(pasta_destino, nome))
    return f"uploads/os/{os_id}/{nome}"


def _webdav_setting(*names):
    for name in names:
        value = current_app.config.get(name) or os.getenv(name)
        if value:
            return value
    return None


def _is_webdav_path(value):
    return str(value or "").startswith(WEBDAV_MARKER_PREFIX)


def _clean_webdav_remote_path(value):
    parts = [part.strip() for part in str(value or "").replace("\\", "/").split("/") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _webdav_remote_path_from_marker(value):
    remote_path = str(value or "")[len(WEBDAV_MARKER_PREFIX):].replace("\\", "/")
    return _clean_webdav_remote_path(remote_path)


def _delete_webdav_marker(value):
    base_url = (_webdav_setting("WEBDAV_URL", "SKYBOX_WEBDAV_URL") or "").strip().rstrip("/")
    username = (_webdav_setting("WEBDAV_USER", "SKYBOX_USERNAME") or "").strip()
    password = _webdav_setting("WEBDAV_PASS", "SKYBOX_APP_PASSWORD") or ""
    remote_path = _webdav_remote_path_from_marker(value)
    if not base_url or not username or not password or not remote_path:
        return

    encoded_path = "/".join(quote(part, safe="") for part in remote_path.split("/") if part)
    response = requests.delete(
        f"{base_url}/{encoded_path}",
        auth=(username, password),
        timeout=WEBDAV_DELETE_TIMEOUT,
    )
    if response.status_code not in (200, 202, 204, 404):
        raise requests.RequestException(f"Falha ao remover arquivo WebDAV ({response.status_code}).")


def _remover_upload_os_arquivo(root_path, rel_path):
    if not rel_path:
        return

    if _is_webdav_path(rel_path):
        try:
            _delete_webdav_marker(rel_path)
        except requests.RequestException:
            pass
        return

    if is_skybox_path(rel_path):
        try:
            delete_skybox_file(rel_path)
        except SkyboxError:
            pass
        return

    rel_normalizado = str(rel_path or "").replace("\\", "/")
    partes = rel_normalizado.split("/")
    if len(partes) >= 4 and partes[-4] == "uploads" and partes[-3] == "os":
        os_id = partes[-2]
        nome = partes[-1]
        if os_id and nome:
            try:
                delete_skybox_file(build_os_media_remote_path(os_id, nome))
            except SkyboxError:
                pass

    static_root = os.path.abspath(os.path.join(root_path, "static"))
    abs_path = os.path.abspath(os.path.join(static_root, rel_normalizado.replace("/", os.sep)))
    if not abs_path.startswith(static_root):
        return
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass


def _aplicar_midias_os(*, solicitacao, ordem, form_data, files_data, root_path):
    files_data = files_data or {}
    getlist = getattr(files_data, "getlist", None)
    imagem_principal_file = files_data.get("imagem_principal_file") if hasattr(files_data, "get") else None
    outras_imagens_files = [arquivo for arquivo in (getlist("outras_imagens_files") if callable(getlist) else []) if arquivo and arquivo.filename]
    video_file = files_data.get("video_file") if hasattr(files_data, "get") else None

    remover_imagem_principal = form_data.get("remover_imagem_principal") == "1"
    limpar_outras_imagens = form_data.get("limpar_outras_imagens") == "1"
    remover_video = form_data.get("remover_video") == "1"

    imagem_principal_atual = getattr(ordem, "imagem_principal", None)
    outras_imagens_atuais = _parse_json_list(getattr(ordem, "outras_imagens", None))
    video_atual = getattr(ordem, "video", None)

    if remover_imagem_principal and imagem_principal_atual:
        _remover_upload_os_arquivo(root_path, imagem_principal_atual)
        ordem.imagem_principal = None
        imagem_principal_atual = None

    if imagem_principal_file and imagem_principal_file.filename:
        if imagem_principal_atual:
            _remover_upload_os_arquivo(root_path, imagem_principal_atual)
        ordem.imagem_principal = _salvar_upload_os_imagem(
            imagem_principal_file,
            root_path,
            solicitacao.id,
            "principal",
            copiar_skybox=True,
        )

    if limpar_outras_imagens and outras_imagens_atuais:
        for rel_path in outras_imagens_atuais:
            _remover_upload_os_arquivo(root_path, rel_path)
        outras_imagens_atuais = []

    if outras_imagens_files:
        inicio = len(outras_imagens_atuais) + 1
        for indice, arquivo in enumerate(outras_imagens_files, start=inicio):
            outras_imagens_atuais.append(
                _salvar_upload_os_imagem(
                    arquivo,
                    root_path,
                    solicitacao.id,
                    f"complementar_{indice}",
                    usar_skybox=True,
                )
            )

    ordem.outras_imagens = (
        json.dumps(outras_imagens_atuais, ensure_ascii=False)
        if outras_imagens_atuais else None
    )

    if remover_video and video_atual:
        _remover_upload_os_arquivo(root_path, video_atual)
        ordem.video = None
        video_atual = None

    if video_file and video_file.filename:
        if video_atual:
            _remover_upload_os_arquivo(root_path, video_atual)
        ordem.video = _salvar_upload_os_video(
            video_file,
            root_path,
            solicitacao.id,
            "video",
        )


def _buscar_vinculo_ativo_piloto(piloto_id):
    return (
        EquipePiloto.query
        .join(Equipe, Equipe.id == EquipePiloto.equipe_id)
        .options(joinedload(EquipePiloto.equipe))
        .filter(
            EquipePiloto.piloto_id == piloto_id,
            Equipe.ativa.is_(True),
        )
        .order_by(
            db.case((EquipePiloto.papel == "piloto", 0), else_=1),
            EquipePiloto.criado_em.desc(),
        )
        .first()
    )


def _buscar_vinculo_piloto_na_equipe(piloto_id, equipe_id):
    return (
        EquipePiloto.query
        .join(Equipe, Equipe.id == EquipePiloto.equipe_id)
        .options(joinedload(EquipePiloto.equipe))
        .filter(
            EquipePiloto.equipe_id == equipe_id,
            EquipePiloto.piloto_id == piloto_id,
            Equipe.ativa.is_(True),
        )
        .first()
    )
