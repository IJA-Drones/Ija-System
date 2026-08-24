import re
import unicodedata
from datetime import date, datetime

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Solicitacao, Usuario
from app.shared.access import apply_prefeitura_scope, is_admin_global_user, is_prefeitura_admin_user
from app.shared.geofencing import detectar_area_restrita
from app.shared.place_id import resolve_google_place_id_for_address
from app.shared.solicitacao_focos import (
    FILTER_FOCO_OPCOES,
    TIPO_VISITA_OUTRO_LABEL,
    canonical_tipo_visita,
    get_tipo_visita_opcoes,
    same_normalized,
    validate_foco_selection,
)

STATUS_OPCOES_EDICAO = [
    "PENDENTE",
    "EM ANÁLISE",
    "APROVADO",
    "APROVADO COM RECOMENDAÇÕES",
    "NEGADO",
]
FOCO_OPCOES_EDICAO = FILTER_FOCO_OPCOES
STATUS_CONCLUIDO_BLOQUEIO = ("CONCLUIDO", "CONCLU\u00cdDO")
UF_OPCOES = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]


class NovoCadastroValidationError(Exception):
    def __init__(self, message, *, category="warning"):
        super().__init__(message)
        self.message = message
        self.category = category


class SolicitacaoAccessError(Exception):
    def __init__(self, message, *, category="danger", redirect_endpoint="main.dashboard"):
        super().__init__(message)
        self.message = message
        self.category = category
        self.redirect_endpoint = redirect_endpoint


def can_use_custom_visit_other(user) -> bool:
    tipo_usuario = (getattr(user, "tipo_usuario", None) or "").strip().lower()
    regiao = (getattr(user, "regiao", None) or "").strip().upper()
    return tipo_usuario in {"dev", "diretor", "admin"} or (tipo_usuario != "uvis" and regiao == "COVISA")


def _clean_empty_marker(value):
    value = (value or "").strip()
    return "" if value == "//" else value


def _clean_place_id(value):
    return (value or "").strip() or None


def _clean_address_number(value):
    return re.sub(r"\s+", "", str(value or "")).strip()


def _validate_single_address_number(value):
    numero = _clean_address_number(value)
    if not numero:
        raise NovoCadastroValidationError("Por favor, informe o numero do endereco.")

    if re.fullmatch(r"s/?n", numero, flags=re.IGNORECASE):
        return "S/N"

    if not re.fullmatch(r"\d{1,6}[A-Za-z]?", numero):
        raise NovoCadastroValidationError(
            "Informe apenas um numero predial no campo Numero. Para outro numero, crie uma nova solicitacao separada."
        )

    return numero.upper()


def _clean_street_name(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _validate_street_without_address_number(value):
    logradouro = _clean_street_name(value)
    if not logradouro:
        raise NovoCadastroValidationError("Por favor, informe o logradouro.")

    if re.search(r"(?:,|/|-|\bn[ºo.]?)\s*\d{1,6}[A-Za-z]?\s*$", logradouro, flags=re.IGNORECASE):
        raise NovoCadastroValidationError(
            "Nao coloque numero predial no Logradouro. Informe o numero somente no campo Numero."
        )

    return logradouro


def _normalize_address_part(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().strip()
    normalized = re.sub(r"\b(r|r\.)\b", "rua", normalized)
    normalized = re.sub(r"\b(av|av\.)\b", "avenida", normalized)
    normalized = re.sub(r"\b(al|al\.)\b", "alameda", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_cep(value):
    return re.sub(r"\D", "", str(value or ""))


def _address_key_from_mapping(data):
    data = data or {}
    return {
        "cep": _normalize_cep(data.get("cep")),
        "logradouro": _normalize_address_part(data.get("logradouro")),
        "numero": _normalize_address_part(data.get("numero")),
        "bairro": _normalize_address_part(data.get("bairro")),
        "cidade": _normalize_address_part(data.get("cidade")),
        "uf": _normalize_address_part(data.get("uf")),
    }


def _address_key_from_solicitacao(solicitacao):
    return {
        "cep": _normalize_cep(getattr(solicitacao, "cep", None)),
        "logradouro": _normalize_address_part(getattr(solicitacao, "logradouro", None)),
        "numero": _normalize_address_part(getattr(solicitacao, "numero", None)),
        "bairro": _normalize_address_part(getattr(solicitacao, "bairro", None)),
        "cidade": _normalize_address_part(getattr(solicitacao, "cidade", None)),
        "uf": _normalize_address_part(getattr(solicitacao, "uf", None)),
    }


def _same_address_key(left, right):
    if not left.get("logradouro") or not left.get("numero") or not left.get("cidade") or not left.get("uf"):
        return False
    required_fields = ("logradouro", "numero", "cidade", "uf")
    if any(left.get(field) != right.get(field) for field in required_fields):
        return False
    if left.get("bairro") and right.get("bairro") and left["bairro"] != right["bairro"]:
        return False
    if left.get("cep") and right.get("cep") and left["cep"] != right["cep"]:
        return False
    return True


def _base_bloqueio_query(prefeitura_id=None):
    query = Solicitacao.query.filter(
        Solicitacao.endereco_bloqueado.is_(True),
        Solicitacao.status.in_(STATUS_CONCLUIDO_BLOQUEIO),
    )
    if prefeitura_id is None:
        return query.filter(Solicitacao.prefeitura_id.is_(None))
    return query.filter(Solicitacao.prefeitura_id == prefeitura_id)


def find_solicitacao_bloqueada_por_place_id(place_id, prefeitura_id=None, endereco=None):
    place_id = _clean_place_id(place_id)
    query = _base_bloqueio_query(prefeitura_id)

    if place_id:
        bloqueada = (
            query
            .filter(Solicitacao.place_id == place_id)
            .order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
            .first()
        )
        if bloqueada:
            return bloqueada

    address_key = _address_key_from_mapping(endereco)
    if not address_key.get("logradouro") or not address_key.get("numero"):
        return None

    candidates = (
        query
        .order_by(Solicitacao.data_criacao.desc(), Solicitacao.id.desc())
        .limit(300)
        .all()
    )
    for solicitacao in candidates:
        if _same_address_key(address_key, _address_key_from_solicitacao(solicitacao)):
            return solicitacao

    return None


def resolve_prefeitura_id_para_bloqueio(user, uvis_responsavel_id=None):
    if getattr(user, "tipo_usuario", None) in ["dev", "diretor", "admin", "visualizar", "prefeitura_admin"]:
        if uvis_responsavel_id:
            uvis = Usuario.query.filter_by(id=uvis_responsavel_id, tipo_usuario="uvis").first()
            if not uvis:
                return getattr(user, "prefeitura_id", None)
            if is_prefeitura_admin_user(user) and uvis.prefeitura_id != getattr(user, "prefeitura_id", None):
                return getattr(user, "prefeitura_id", None)
            return uvis.prefeitura_id or getattr(user, "prefeitura_id", None)

    return getattr(user, "prefeitura_id", None)


def build_novo_cadastro_context(user, google_maps_key):
    uvis_lista = []
    if user.tipo_usuario in ["dev", "diretor", "admin", "visualizar", "prefeitura_admin"]:
        query = Usuario.query.filter_by(tipo_usuario="uvis")
        query = apply_prefeitura_scope(query, user, Usuario.prefeitura_id)
        uvis_lista = query.order_by(Usuario.nome_uvis.asc()).all()

    return {
        "hoje": date.today().isoformat(),
        "google_maps_key": google_maps_key,
        "uvis_lista": uvis_lista,
        "allow_custom_visit_other": can_use_custom_visit_other(user),
        "solicitacao_tipo_visita_opcoes": get_tipo_visita_opcoes(can_use_custom_visit_other(user)),
        "form_values": {},
    }


def build_novo_cadastro_context_with_form(user, google_maps_key, form_source):
    context = build_novo_cadastro_context(user, google_maps_key)
    context["form_values"] = {
        "data": (form_source.get("data") or "").strip(),
        "hora": (form_source.get("hora") or "").strip(),
        "uvis_responsavel_id": (form_source.get("uvis_responsavel_id") or "").strip(),
        "cep": (form_source.get("cep") or "").strip(),
        "logradouro": (form_source.get("logradouro") or "").strip(),
        "numero": (form_source.get("numero") or "").strip(),
        "complemento": (form_source.get("complemento") or "").strip(),
        "bairro": (form_source.get("bairro") or "").strip(),
        "cidade": (form_source.get("cidade") or "").strip(),
        "uf": (form_source.get("uf") or "").strip(),
        "latitude": (form_source.get("latitude") or "").strip(),
        "longitude": (form_source.get("longitude") or "").strip(),
        "place_id": (form_source.get("place_id") or "").strip(),
        "tipo_visita": (form_source.get("tipo_visita") or "").strip(),
        "tipo_visita_outros": (form_source.get("tipo_visita_outros") or "").strip(),
        "tipo_imovel": (form_source.get("tipo_imovel") or "").strip(),
        "foco": (form_source.get("foco") or "").strip(),
        "tipo_operacao": (form_source.get("tipo_operacao") or "").strip(),
        "altura_voo": (form_source.get("altura_voo") or "").strip(),
        "distrito_administrativo": _clean_empty_marker(form_source.get("distrito_administrativo")),
        "apoio_cet": (form_source.get("apoio_cet") or "").strip(),
        "observacao": (form_source.get("observacao") or "").strip(),
    }
    return context


def create_nova_solicitacao(user, form_data):
    place_id = _clean_place_id(form_data.get("place_id"))
    logradouro = _validate_street_without_address_number(form_data.get("logradouro"))
    numero = _validate_single_address_number(form_data.get("numero"))
    data_str = form_data.get("data")
    hora_str = form_data.get("hora")
    data_obj = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else None
    hora_obj = datetime.strptime(hora_str, "%H:%M").time() if hora_str else None
    distrito_administrativo = _clean_empty_marker(form_data.get("distrito_administrativo"))

    if not distrito_administrativo:
        raise NovoCadastroValidationError("Por favor, informe o DA (Distrito).")

    if user.tipo_usuario in ["dev", "diretor", "admin", "visualizar", "prefeitura_admin"]:
        uvis_id_final = form_data.get("uvis_responsavel_id")
        if not uvis_id_final:
            raise NovoCadastroValidationError("Por favor, selecione a UVIS responsavel.")
        uvis = Usuario.query.filter_by(id=uvis_id_final, tipo_usuario="uvis").first()
        if not uvis:
            raise NovoCadastroValidationError("UVIS selecionada nao encontrada.")
        if is_prefeitura_admin_user(user) and uvis.prefeitura_id != getattr(user, "prefeitura_id", None):
            raise NovoCadastroValidationError("Essa UVIS nao pertence a sua prefeitura.", category="danger")
        prefeitura_id_final = uvis.prefeitura_id or getattr(user, "prefeitura_id", None)
    else:
        uvis_id_final = user.id
        prefeitura_id_final = getattr(user, "prefeitura_id", None)

    place_id = resolve_google_place_id_for_address(
        place_id=place_id,
        logradouro=form_data.get("logradouro"),
        numero=form_data.get("numero"),
        bairro=form_data.get("bairro"),
        cidade=form_data.get("cidade"),
        uf=form_data.get("uf"),
        cep=form_data.get("cep"),
    )

    solicitacao_bloqueada = find_solicitacao_bloqueada_por_place_id(
        place_id,
        prefeitura_id=prefeitura_id_final,
        endereco=form_data,
    )
    if solicitacao_bloqueada:
        raise NovoCadastroValidationError(
            f"O endereco selecionado ja foi concluido na OS #{solicitacao_bloqueada.id} e nao aceita novas solicitacoes.",
            category="danger",
        )

    lat_raw = (form_data.get("latitude") or "").strip()
    lng_raw = (form_data.get("longitude") or "").strip()
    latitude = float(lat_raw.replace(",", ".")) if lat_raw else None
    longitude = float(lng_raw.replace(",", ".")) if lng_raw else None
    area_restrita = detectar_area_restrita(latitude, longitude) or form_data.get("risco_aereo") == "1"
    
    try:
        tipo_visita, tipo_imovel, foco = validate_foco_selection(
            form_data.get("tipo_visita"),
            form_data.get("tipo_imovel"),
            form_data.get("foco"),
            allow_custom_tipo_visita=can_use_custom_visit_other(user),
            tipo_visita_outro=form_data.get("tipo_visita_outros"),
        )
    except ValueError as exc:
        raise NovoCadastroValidationError(str(exc))

    nova_solicitacao = Solicitacao(
        data_agendamento=data_obj,
        hora_agendamento=hora_obj,
        place_id=place_id,
        cep=form_data.get("cep"),
        logradouro=logradouro,
        bairro=form_data.get("bairro"),
        cidade=form_data.get("cidade"),
        numero=numero,
        uf=form_data.get("uf"),
        complemento=form_data.get("complemento"),
        foco=foco,
        tipo_visita=tipo_visita,
        tipo_imovel=tipo_imovel,
        tipo_operacao=form_data.get("tipo_operacao"),
        altura_voo=form_data.get("altura_voo"),
        distrito_administrativo=distrito_administrativo,
        apoio_cet=form_data.get("apoio_cet") == "sim",
        observacao=form_data.get("observacao"),
        latitude=latitude,
        longitude=longitude,
        area_restrita=area_restrita,
        perimetro_planejado=form_data.get("perimetro_planejado"),
        usuario_id=uvis_id_final,
        prefeitura_id=prefeitura_id_final,
        status="PENDENTE",
    )

    try:
        db.session.add(nova_solicitacao)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return nova_solicitacao


def build_editar_solicitacao_context(user, solicitacao_id):
    pedido = (
        Solicitacao.query.options(joinedload(Solicitacao.usuario))
        .get_or_404(solicitacao_id)
    )
    is_admin = is_admin_global_user(user)
    allow_custom_visit_other = can_use_custom_visit_other(user)
    pedido_tipo_visita_padrao = canonical_tipo_visita(pedido.tipo_visita)
    pedido_tipo_visita_outros = ""
    pedido_tipo_visita_select = pedido.tipo_visita or ""

    if allow_custom_visit_other and pedido.tipo_visita and not pedido_tipo_visita_padrao:
        pedido_tipo_visita_select = TIPO_VISITA_OUTRO_LABEL
        pedido_tipo_visita_outros = pedido.tipo_visita

    if not is_admin:
        if pedido.usuario_id != user.id:
            raise SolicitacaoAccessError(
                "Permiss\u00e3o negada. Voc\u00ea s\u00f3 pode editar suas pr\u00f3prias solicita\u00e7\u00f5es."
            )

        if pedido.status not in ["PENDENTE", "NEGADO"]:
            raise SolicitacaoAccessError(
                "Esta solicita\u00e7\u00e3o j\u00e1 est\u00e1 em processo de aprova\u00e7\u00e3o e n\u00e3o pode ser editada.",
                category="warning",
            )

    return {
        "pedido": pedido,
        "is_admin": is_admin,
        "status_opcoes": STATUS_OPCOES_EDICAO,
        "foco_opcoes": FOCO_OPCOES_EDICAO,
        "tipo_visita_opcoes": get_tipo_visita_opcoes(allow_custom_visit_other),
        "solicitacao_tipo_visita_opcoes": get_tipo_visita_opcoes(allow_custom_visit_other),
        "uf_opcoes": UF_OPCOES,
        "allow_custom_visit_other": allow_custom_visit_other,
        "pedido_tipo_visita_select": pedido_tipo_visita_select,
        "pedido_tipo_visita_outros": pedido_tipo_visita_outros,
    }


def atualizar_solicitacao(user, solicitacao_id, form_data):
    context = build_editar_solicitacao_context(user, solicitacao_id)
    pedido = context["pedido"]
    is_admin = context["is_admin"]
    endereco_original = (
        pedido.cep,
        pedido.logradouro,
        pedido.numero,
        pedido.bairro,
        pedido.cidade,
        pedido.uf,
    )

    pedido.data_agendamento = (
        datetime.strptime(form_data.get("data_agendamento"), "%Y-%m-%d").date()
        if form_data.get("data_agendamento")
        else None
    )
    pedido.hora_agendamento = (
        datetime.strptime(form_data.get("hora_agendamento"), "%H:%M").time()
        if form_data.get("hora_agendamento")
        else None
    )

    try:
        tipo_visita, tipo_imovel, foco = validate_foco_selection(
            form_data.get("tipo_visita"),
            form_data.get("tipo_imovel"),
            form_data.get("foco"),
            allow_custom_tipo_visita=can_use_custom_visit_other(user),
            tipo_visita_outro=form_data.get("tipo_visita_outros"),
        )
    except ValueError as exc:
        if (
            same_normalized(form_data.get("foco"), pedido.foco)
            and (
                same_normalized(form_data.get("tipo_visita"), pedido.tipo_visita)
                or (
                    same_normalized(form_data.get("tipo_visita"), TIPO_VISITA_OUTRO_LABEL)
                    and same_normalized(form_data.get("tipo_visita_outros"), pedido.tipo_visita)
                )
            )
            and same_normalized(form_data.get("tipo_imovel"), pedido.tipo_imovel)
        ):
            tipo_visita = pedido.tipo_visita
            tipo_imovel = pedido.tipo_imovel
            foco = pedido.foco
        else:
            raise NovoCadastroValidationError(str(exc))

    pedido.foco = foco
    pedido.tipo_visita = tipo_visita
    pedido.tipo_imovel = tipo_imovel
    pedido.tipo_operacao = form_data.get("tipo_operacao") or pedido.tipo_operacao
    pedido.altura_voo = form_data.get("altura_voo") or pedido.altura_voo
    pedido.distrito_administrativo = (
        _clean_empty_marker(form_data.get("distrito_administrativo"))
        or pedido.distrito_administrativo
    )
    if pedido.ordem_servico and pedido.distrito_administrativo:
        pedido.ordem_servico.distrito_administrativo = pedido.distrito_administrativo
    pedido.apoio_cet = (form_data.get("apoio_cet", "n\u00e3o") or "").lower() == "sim"
    pedido.observacao = form_data.get("observacao") or pedido.observacao

    pedido.cep = form_data.get("cep") or pedido.cep
    pedido.logradouro = form_data.get("logradouro") or pedido.logradouro
    pedido.numero = form_data.get("numero") or pedido.numero
    pedido.bairro = form_data.get("bairro") or pedido.bairro
    pedido.cidade = form_data.get("cidade") or pedido.cidade
    pedido.uf = form_data.get("uf") or pedido.uf

    endereco_atual = (
        pedido.cep,
        pedido.logradouro,
        pedido.numero,
        pedido.bairro,
        pedido.cidade,
        pedido.uf,
    )
    endereco_foi_alterado = endereco_atual != endereco_original
    if endereco_foi_alterado or not _clean_place_id(pedido.place_id):
        pedido.place_id = resolve_google_place_id_for_address(
            place_id=None if endereco_foi_alterado else pedido.place_id,
            cep=pedido.cep,
            logradouro=pedido.logradouro,
            numero=pedido.numero,
            bairro=pedido.bairro,
            cidade=pedido.cidade,
            uf=pedido.uf,
        )

    lat_raw = (form_data.get("latitude") or "").strip()
    lng_raw = (form_data.get("longitude") or "").strip()
    pedido.latitude = float(lat_raw.replace(",", ".")) if lat_raw else pedido.latitude
    pedido.longitude = float(lng_raw.replace(",", ".")) if lng_raw else pedido.longitude
    pedido.area_restrita = detectar_area_restrita(pedido.latitude, pedido.longitude) or form_data.get("risco_aereo") == "1"

    if is_admin:
        pedido.status = form_data.get("status") or pedido.status
        pedido.protocolo = form_data.get("protocolo") or pedido.protocolo
        justificativa = (form_data.get("justificativa") or "").strip()
        pedido.justificativa = justificativa or None
    else:
        if pedido.status == "NEGADO":
            motivo_original = (pedido.justificativa or "").strip()
            limpo = re.sub(r"^\s*CORRE\u00c7\u00c3O:\s*", "", motivo_original, flags=re.IGNORECASE)
            pedido.justificativa = "CORRE\u00c7\u00c3O: corrigido pela UVIS" if not limpo else f"CORRE\u00c7\u00c3O: {limpo}"
        else:
            pedido.justificativa = None

        pedido.status = "PENDENTE"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "main.admin_dashboard" if is_admin else "main.dashboard"


def deletar_solicitacao_admin(user, solicitacao_id):
    if not is_admin_global_user(user):
        raise SolicitacaoAccessError(
            "Permiss\u00e3o negada. Apenas administradores podem deletar registros.",
            redirect_endpoint="main.admin_dashboard",
        )

    pedido = Solicitacao.query.get_or_404(solicitacao_id)
    pedido_id = pedido.id
    autor_nome = pedido.usuario.nome_uvis if pedido.usuario else "UVIS"

    try:
        db.session.delete(pedido)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return f"Pedido #{pedido_id} da {autor_nome} deletado permanentemente."
