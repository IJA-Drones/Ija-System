import json
import os
from datetime import date, datetime, timedelta

from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Baterias, Drones, Equipe, EquipePiloto, OrdemServico, Solicitacao, Veiculos
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, can_access_regiao
from app.shared.query_filters import aplicar_filtros_base


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
OS_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "m4v"}


class PilotoOsError(Exception):
    def __init__(self, message, category="warning", *, redirect_endpoint="main.piloto_os"):
        super().__init__(message)
        self.category = category
        self.redirect_endpoint = redirect_endpoint


def build_piloto_os_context(user, args, google_maps_key):
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.dashboard")

    vinculo = _buscar_vinculo_ativo_piloto(user.piloto_id)
    if not vinculo or not vinculo.equipe_id:
        return {
            "sem_equipe_ativa": True,
            "pedidos": [],
            "paginacao": None,
            "status_ok": STATUS_OS_APROVADAS_COM_ACENTO,
            "pilot_team_nome": None,
            "pilot_team_regiao": None,
            "pilot_team_papel": None,
            "google_maps_key": google_maps_key,
            "drones_equipe": [],
            "baterias_equipe": [],
            "veiculos_equipe": [],
        }

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(
            Solicitacao.equipe_id == vinculo.equipe_id,
            Solicitacao.status.in_(STATUS_OS_APROVADAS_COM_ACENTO),
        )
    )

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
        "pilot_team_nome": vinculo.equipe.nome_equipe if vinculo.equipe else None,
        "pilot_team_regiao": vinculo.equipe.regiao if vinculo.equipe else None,
        "pilot_team_papel": (vinculo.papel or "").lower(),
        "google_maps_key": google_maps_key,
        "drones_equipe": (
            Drones.query
            .options(joinedload(Drones.equipe))
            .filter(Drones.equipe_id == vinculo.equipe_id)
            .order_by(Drones.renomacao.asc())
            .all()
        ),
        "baterias_equipe": (
            Baterias.query
            .join(Drones, Baterias.drone_id == Drones.id)
            .filter(Drones.equipe_id == vinculo.equipe_id)
            .order_by(Baterias.renomacao.asc())
            .all()
        ),
        "veiculos_equipe": (
            Veiculos.query
            .filter(Veiculos.equipe_id == vinculo.equipe_id)
            .order_by(Veiculos.operacao.asc(), Veiculos.modelo.asc())
            .all()
        ),
    }


def build_piloto_os_historico_context(user, args):
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.dashboard")

    equipes_vinculadas = (
        db.session.query(EquipePiloto.equipe_id)
        .filter(
            EquipePiloto.piloto_id == user.piloto_id,
            EquipePiloto.equipe_id.isnot(None),
        )
        .distinct()
    )

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(
            Solicitacao.equipe_id.in_(equipes_vinculadas),
            Solicitacao.status.in_(STATUS_OS_CONCLUIDAS),
        )
    )

    page = args.get("page", 1, type=int)
    paginacao = (
        query
        .order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .paginate(page=page, per_page=6, error_out=False)
    )

    return {"pedidos": paginacao.items, "paginacao": paginacao}


def concluir_os_piloto(user, os_id):
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.dashboard")

    solicitacao = Solicitacao.query.get_or_404(os_id)

    if solicitacao.status not in STATUS_OS_APROVADAS_COM_ACENTO:
        raise PilotoOsError("A OS nao esta aprovada.", "warning")

    if not solicitacao.equipe_id:
        raise PilotoOsError("Esta OS nao possui equipe atribuida.", "danger")

    vinculo = _buscar_vinculo_piloto_na_equipe(user.piloto_id, solicitacao.equipe_id)
    if not vinculo:
        raise PilotoOsError("Voce nao faz parte da equipe atribuida a esta OS.", "danger")

    solicitacao.status = "CONCLU\u00cdDO"
    db.session.commit()

    equipe_nome = vinculo.equipe.nome_equipe if vinculo.equipe else None
    papel = (vinculo.papel or "").lower() if vinculo.papel else None

    if equipe_nome and papel:
        return f"OS #{solicitacao.id} concluida! Equipe: {equipe_nome} | Papel: {papel}."
    if equipe_nome:
        return f"OS #{solicitacao.id} concluida! Equipe: {equipe_nome}."
    return f"OS #{solicitacao.id} concluida com sucesso!"


def build_piloto_os_form_context(user, os_id):
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.dashboard")

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .get_or_404(os_id)
    )

    status_permitidos = set(STATUS_OS_APROVADAS_COM_ACENTO + STATUS_OS_CONCLUIDAS)
    if solicitacao.status not in status_permitidos:
        raise PilotoOsError("Esta OS nao esta liberada para preenchimento do formulario.", "warning")

    if not solicitacao.equipe_id:
        raise PilotoOsError("Esta OS nao possui equipe atribuida.", "danger")

    vinculo = _buscar_vinculo_piloto_na_equipe(user.piloto_id, solicitacao.equipe_id)
    if not vinculo:
        raise PilotoOsError("Voce nao tem permissao para acessar esta OS.", "danger")

    equipe = vinculo.equipe
    ordem = solicitacao.ordem_servico
    drones_equipe = (
        Drones.query
        .filter(
            Drones.equipe_id == solicitacao.equipe_id,
            Drones.status == "Ativo",
        )
        .order_by(Drones.renomacao.asc())
        .all()
    )

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
        "drones_equipe": drones_equipe,
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
        ordem = OrdemServico(
            solicitacao_id=solicitacao.id,
            equipe_id=solicitacao.equipe_id,
        )
        db.session.add(ordem)

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
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo.", "danger")

    drone = Drones.query.get_or_404(drone_id)
    if not drone.equipe_id:
        raise PilotoOsError("Drone sem equipe.", "danger")

    vinculo = _buscar_vinculo_piloto_na_equipe(user.piloto_id, drone.equipe_id)
    if not vinculo:
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

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .get_or_404(os_id)
    )
    pedido_regiao = getattr(getattr(solicitacao, "usuario", None), "regiao", None)
    if not can_access_regiao(user, pedido_regiao):
        raise PilotoOsError("Voce nao tem permissao para acessar esta OS.", "danger", redirect_endpoint="main.dashboard")

    equipe = solicitacao.equipe
    ordem = solicitacao.ordem_servico
    drones_equipe = []
    if solicitacao.equipe_id:
        drones_equipe = (
            Drones.query
            .filter(Drones.equipe_id == solicitacao.equipe_id)
            .order_by(Drones.renomacao.asc())
            .all()
        )

    return {
        "solicitacao": solicitacao,
        "equipe": equipe,
        "ordem": ordem,
        "modo_visualizacao": True,
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
        "respondido_por_padrao": "",
        "respondido_em_value": (
            ordem.respondido_em.strftime("%Y-%m-%dT%H:%M")
            if ordem and ordem.respondido_em else ""
        ),
        "drones_equipe": drones_equipe,
        **_build_os_media_context(ordem),
    }


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
        drone_p = Drones.query.get(drone_pulv_id)
        if drone_p and drone_p.equipe_id == solicitacao.equipe_id:
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
        drone_m = Drones.query.get(drone_monit_id)
        if drone_m and drone_m.equipe_id == solicitacao.equipe_id:
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
    return {
        "imagem_principal_path": imagem_principal_path,
        "outras_imagens_paths": outras_imagens_paths,
        "video_path": video_path,
        "total_midias_formulario": (
            (1 if imagem_principal_path else 0)
            + len(outras_imagens_paths)
            + (1 if video_path else 0)
        ),
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
            "Envie apenas videos nos formatos MP4, MOV, WEBM ou M4V para o levantamento.",
            "warning",
            redirect_endpoint="main.piloto_os_formulario_view",
        )
    return ext


def _salvar_upload_os_imagem(arquivo, root_path, os_id, prefixo):
    if not arquivo or not arquivo.filename:
        return None

    ext = _validar_arquivo_imagem_os(arquivo)
    pasta_destino = os.path.join(root_path, "static", "uploads", "os", str(os_id))
    os.makedirs(pasta_destino, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nome = secure_filename(f"{prefixo}_os_{os_id}_{stamp}.{ext}")
    arquivo.save(os.path.join(pasta_destino, nome))
    return f"uploads/os/{os_id}/{nome}"


def _salvar_upload_os_video(arquivo, root_path, os_id, prefixo):
    if not arquivo or not arquivo.filename:
        return None

    ext = _validar_arquivo_video_os(arquivo)
    pasta_destino = os.path.join(root_path, "static", "uploads", "os", str(os_id))
    os.makedirs(pasta_destino, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    nome = secure_filename(f"{prefixo}_os_{os_id}_{stamp}.{ext}")
    arquivo.save(os.path.join(pasta_destino, nome))
    return f"uploads/os/{os_id}/{nome}"


def _remover_upload_os_arquivo(root_path, rel_path):
    if not rel_path:
        return

    static_root = os.path.abspath(os.path.join(root_path, "static"))
    abs_path = os.path.abspath(os.path.join(static_root, rel_path.replace("/", os.sep)))
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
