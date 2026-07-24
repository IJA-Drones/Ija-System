import os
import re
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from flask import current_app, make_response, send_file
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Abastecimento, Equipe, EquipePiloto, LogVeiculo, Pilotos, Veiculos
from app.shared.access import apply_prefeitura_scope, normalize_role
from app.shared.query_filters import id_search_clause
from app.shared.skybox import (
    SkyboxError,
    build_veiculo_media_remote_path,
    is_skybox_path,
    skybox_enabled,
    upload_file_to_skybox,
)


EQUIPE_OCEANO_USER_TYPE = "equipe_oceano"
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
MAX_KM_POR_TURNO = 500
VEICULOS_ALLOWED_TYPES = (
    "dev",
    "admin",
    "visualizar",
    "operario",
    "operador",
    "uvis",
    "piloto",
    EQUIPE_OCEANO_USER_TYPE,
    "prefeitura_admin",
)


def _now_brazil():
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)
VEICULOS_LOGS_ALLOWED_TYPES = (
    "dev",
    "admin",
    "visualizar",
    "operario",
    "operador",
    "prefeitura_admin",
    EQUIPE_OCEANO_USER_TYPE,
)


class VeiculoTurnoError(Exception):
    def __init__(self, message, category="warning"):
        super().__init__(message)
        self.category = category


def list_veiculos(tipo_usuario, args, user=None):
    tipo_usuario = normalize_role(tipo_usuario)
    if tipo_usuario not in VEICULOS_ALLOWED_TYPES:
        raise PermissionError

    q = (args.get("q") or "").strip()
    operacao = (args.get("operacao") or "").strip().upper()
    frota = (args.get("frota") or "").strip().upper()
    status = (args.get("status") or "").strip()

    query = Veiculos.query
    if user is not None and tipo_usuario != EQUIPE_OCEANO_USER_TYPE:
        query = apply_prefeitura_scope(query, user, Veiculos.prefeitura_id)

    if tipo_usuario == EQUIPE_OCEANO_USER_TYPE:
        equipe = _equipe_oceano_logada(user)
        if not equipe:
            raise PermissionError
        query = query.filter(_veiculo_equipe_operacional_filter(equipe, user))

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                id_search_clause(Veiculos.id, q),
                Veiculos.modelo.ilike(like),
                Veiculos.placa.ilike(like),
                Veiculos.responsavel.ilike(like),
            )
        )

    if operacao:
        query = query.filter(Veiculos.operacao == operacao)

    if frota:
        query = query.filter(Veiculos.frota == frota)

    if status:
        query = query.filter(Veiculos.status == status)

    veiculos = query.order_by(Veiculos.criado_em.desc()).all()

    return {
        "veiculos": veiculos,
        "is_admin": tipo_usuario in {"dev", "admin"},
        "can_manage": tipo_usuario in {"dev", "admin", "operario", "operador"},
        "filters": {
            "q": q,
            "operacao": operacao,
            "frota": frota,
            "status": status,
            "total": len(veiculos),
        },
        "ultimos_logs": _build_ultimos_logs(veiculos),
    }


def list_responsaveis_choices(user=None):
    papeis_por_piloto = {}
    for row in db.session.query(EquipePiloto.piloto_id, EquipePiloto.papel).all():
        papeis_por_piloto.setdefault(row.piloto_id, set()).add((row.papel or "").lower())

    pilotos_query = Pilotos.query
    if user is not None:
        pilotos_query = apply_prefeitura_scope(pilotos_query, user, Pilotos.prefeitura_id)
    pilotos = pilotos_query.order_by(Pilotos.nome_piloto.asc()).all()

    options = []
    for piloto in pilotos:
        papeis = papeis_por_piloto.get(piloto.id, set())

        if "piloto" in papeis and "auxiliar" in papeis:
            label = f"{piloto.nome_piloto} (Piloto/Aux)"
        elif "auxiliar" in papeis:
            label = f"{piloto.nome_piloto} (Auxiliar)"
        else:
            label = f"{piloto.nome_piloto} (Piloto)"

        options.append({"value": piloto.nome_piloto, "label": label})

    return options


def list_equipes_choices(user=None):
    query = Equipe.query.filter(Equipe.ativa.is_(True))
    if user is not None:
        query = apply_prefeitura_scope(query, user, Equipe.prefeitura_id)

    equipes = query.order_by(Equipe.nome_equipe.asc()).all()
    return [{"value": str(equipe.id), "label": equipe.nome_equipe} for equipe in equipes]


def validate_veiculo_form(form_data, *, responsaveis, equipes=None, existing_veiculo=None):
    errors = {}
    equipes = equipes or []

    modelo = (form_data.get("modelo") or "").strip()
    ano_raw = (form_data.get("ano_fabricacao") or "").strip()
    frota = (form_data.get("frota") or "").strip().upper()
    operacao = (form_data.get("operacao") or "").strip().upper()
    placa = (form_data.get("placa") or "").strip().upper()
    responsavel = (form_data.get("responsavel") or "").strip()
    equipe_id_raw = (form_data.get("equipe_id") or "").strip()
    km_atual_raw = (form_data.get("km_atual") or "").strip()
    km_prox_raw = (form_data.get("km_prox_revisao") or "").strip()
    status = (form_data.get("status") or "Ativo").strip()
    revisao_marcada_raw = (form_data.get("revisao_marcada_em") or "").strip()
    revisao_obs = (form_data.get("revisao_obs") or "").strip()

    form = {
        "modelo": modelo,
        "ano_fabricacao": ano_raw,
        "frota": frota,
        "operacao": operacao,
        "placa": placa,
        "responsavel": responsavel,
        "equipe_id": equipe_id_raw,
        "km_atual": km_atual_raw,
        "km_prox_revisao": km_prox_raw,
        "status": status,
        "revisao_marcada_em": revisao_marcada_raw,
        "revisao_obs": revisao_obs,
    }

    if not modelo:
        errors["modelo"] = "Informe o modelo."
    if not ano_raw:
        errors["ano_fabricacao"] = "Informe o ano."
    if frota not in ("PROPRIA", "ALUGADA"):
        errors["frota"] = "Selecione PROPRIA ou ALUGADA."
    if not operacao:
        errors["operacao"] = (
            "Informe a operação (ex: PMSP / AGRO)."
            if existing_veiculo is None
            else "Informe a operação."
        )
    if not placa:
        errors["placa"] = "Informe a placa."

    valid_values = {responsavel_item["value"] for responsavel_item in responsaveis}
    if responsavel and responsavel not in valid_values:
        errors["responsavel"] = "Selecione um responsável válido."

    valid_equipe_ids = {item["value"] for item in equipes}
    equipe_id = None
    if equipe_id_raw:
        if equipe_id_raw not in valid_equipe_ids:
            errors["equipe_id"] = "Selecione uma equipe válida."
        else:
            equipe_id = int(equipe_id_raw)

    ano_fabricacao = None
    if ano_raw:
        try:
            ano_fabricacao = int(ano_raw)
            if ano_fabricacao < 1900 or ano_fabricacao > 2100:
                errors["ano_fabricacao"] = "Ano inválido."
        except ValueError:
            errors["ano_fabricacao"] = "Ano inválido."

    km_atual = (existing_veiculo.km_atual if existing_veiculo is not None else 0) or 0
    if km_atual_raw:
        try:
            km_atual = _parse_km_form(km_atual_raw, "KM atual")
            if km_atual < 0:
                errors["km_atual"] = (
                    "KM atual não pode ser negativo."
                    if existing_veiculo is None
                    else "KM atual inválido."
                )
        except ValueError:
            errors["km_atual"] = (
                "KM atual inválido."
                if existing_veiculo is not None
                else "KM atual inválido."
            )

    km_prox_revisao = None
    if km_prox_raw:
        try:
            km_prox_revisao = float(km_prox_raw.replace(",", "."))
            if existing_veiculo is None and km_prox_revisao < 0:
                errors["km_prox_revisao"] = "Próx revisão inválida."
        except ValueError:
            errors["km_prox_revisao"] = "Próx revisão inválida."

    revisao_marcada_em = None
    if revisao_marcada_raw:
        try:
            revisao_marcada_em = datetime.strptime(revisao_marcada_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors["revisao_marcada_em"] = "Data/hora inválida."

    if placa and not errors.get("placa"):
        query = Veiculos.query.filter_by(placa=placa)
        if existing_veiculo is not None:
            query = query.filter(Veiculos.id != existing_veiculo.id)
        if query.first():
            errors["placa"] = "Já existe um veículo com essa placa."

    cleaned = {
        "modelo": modelo,
        "ano_fabricacao": ano_fabricacao,
        "frota": frota,
        "operacao": operacao,
        "placa": placa,
        "responsavel": responsavel or None,
        "equipe_id": equipe_id,
        "km_atual": km_atual,
        "km_prox_revisao": km_prox_revisao,
        "status": status,
        "revisao_marcada_em": revisao_marcada_em,
        "revisao_obs": revisao_obs or None,
    }

    return form, cleaned, errors


def create_veiculo(cleaned, *, prefeitura_id=None):
    prefeitura_id = _resolve_prefeitura_id_veiculo(cleaned["equipe_id"], prefeitura_id)
    novo = Veiculos(
        tipo_equipamento="veiculos",
        status=cleaned["status"],
        modelo=cleaned["modelo"],
        ano_fabricacao=cleaned["ano_fabricacao"],
        renomacao=cleaned["placa"],
        categoria=None,
        numero_serie=None,
        ultima_manutencao=None,
        frota=cleaned["frota"],
        operacao=cleaned["operacao"],
        placa=cleaned["placa"],
        responsavel=cleaned["responsavel"],
        km_atual=cleaned["km_atual"],
        km_prox_revisao=cleaned["km_prox_revisao"],
        revisao_marcada_em=cleaned["revisao_marcada_em"],
        revisao_obs=cleaned["revisao_obs"],
        equipe_id=cleaned["equipe_id"],
        prefeitura_id=prefeitura_id,
    )
    db.session.add(novo)
    db.session.commit()
    return novo


def update_veiculo(veiculo, cleaned):
    veiculo.modelo = cleaned["modelo"]
    veiculo.ano_fabricacao = cleaned["ano_fabricacao"]
    veiculo.frota = cleaned["frota"]
    veiculo.operacao = cleaned["operacao"]
    veiculo.placa = cleaned["placa"]
    veiculo.responsavel = cleaned["responsavel"]
    veiculo.equipe_id = cleaned["equipe_id"]
    veiculo.prefeitura_id = _resolve_prefeitura_id_veiculo(cleaned["equipe_id"], veiculo.prefeitura_id)
    veiculo.km_atual = cleaned["km_atual"]
    veiculo.km_prox_revisao = cleaned["km_prox_revisao"]
    veiculo.status = cleaned["status"]
    veiculo.revisao_marcada_em = cleaned["revisao_marcada_em"]
    veiculo.revisao_obs = cleaned["revisao_obs"]
    veiculo.renomacao = cleaned["placa"]
    db.session.commit()
    return veiculo


def delete_veiculo(veiculo):
    db.session.delete(veiculo)
    db.session.commit()


def build_veiculo_form(veiculo):
    return {
        "modelo": veiculo.modelo or "",
        "ano_fabricacao": str(veiculo.ano_fabricacao or ""),
        "frota": veiculo.frota or "",
        "operacao": veiculo.operacao or "",
        "placa": veiculo.placa or "",
        "responsavel": veiculo.responsavel or "",
        "equipe_id": str(veiculo.equipe_id or ""),
        "km_atual": str(veiculo.km_atual or ""),
        "km_prox_revisao": str(veiculo.km_prox_revisao or "") if veiculo.km_prox_revisao is not None else "",
        "status": veiculo.status or "Ativo",
        "revisao_marcada_em": (
            veiculo.revisao_marcada_em.strftime("%Y-%m-%dT%H:%M")
            if veiculo.revisao_marcada_em else ""
        ),
        "revisao_obs": veiculo.revisao_obs or "",
    }


def build_piloto_veiculos_context(user):
    if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe = _equipe_oceano_logada(user)
        if not equipe:
            return {
                "piloto_vinculado": False,
                "veiculos": [],
                "turnos_abertos": {},
                "km_inicial_referencias": {},
            }

        veiculos = (
            Veiculos.query
            .filter(_veiculo_equipe_operacional_filter(equipe, user))
            .order_by(Veiculos.operacao.asc(), Veiculos.modelo.asc())
            .all()
        )
        return {
            "piloto_vinculado": True,
            "veiculos": veiculos,
            "turnos_abertos": _build_turnos_abertos_veiculos(veiculos, user),
            "km_inicial_referencias": _build_km_inicial_referencias(veiculos),
        }

    nome_piloto = _piloto_nome_logado(user)

    if not nome_piloto or not getattr(user, "piloto_id", None):
        return {
            "piloto_vinculado": False,
            "veiculos": [],
            "turnos_abertos": {},
            "km_inicial_referencias": {},
        }

    equipe_ids = _equipe_ids_do_piloto(user)
    filtros_responsabilidade = [_veiculo_responsavel_filter(nome_piloto, user)]
    if equipe_ids:
        filtros_responsabilidade.append(Veiculos.equipe_id.in_(equipe_ids))

    veiculos = (
        Veiculos.query
        .filter(db.or_(*filtros_responsabilidade))
        .order_by(Veiculos.operacao.asc(), Veiculos.modelo.asc())
        .all()
    )

    return {
        "piloto_vinculado": True,
        "veiculos": veiculos,
        "turnos_abertos": _build_turnos_abertos_veiculos(veiculos, user),
        "km_inicial_referencias": _build_km_inicial_referencias(veiculos),
    }


def _build_turnos_abertos_veiculos(veiculos, user):
    turnos_abertos = {}
    veiculo_ids = [veiculo.id for veiculo in veiculos]

    if veiculo_ids:
        query = (
            LogVeiculo.query
            .options(selectinload(LogVeiculo.abastecimentos_detalhados))
            .filter(LogVeiculo.veiculo_id.in_(veiculo_ids), LogVeiculo.km_final.is_(None))
        )
        query = _apply_log_actor_scope(query, user)
        logs_abertos = query.order_by(LogVeiculo.veiculo_id.asc(), LogVeiculo.data_registro.desc()).all()
        for log in logs_abertos:
            if log.veiculo_id not in turnos_abertos:
                turnos_abertos[log.veiculo_id] = log

    return turnos_abertos


def _build_km_inicial_referencias(veiculos):
    referencias = {}
    if not veiculos:
        return referencias

    veiculo_ids = [veiculo.id for veiculo in veiculos]
    logs_fechados = (
        LogVeiculo.query
        .filter(LogVeiculo.veiculo_id.in_(veiculo_ids), LogVeiculo.km_final.isnot(None))
        .order_by(LogVeiculo.veiculo_id.asc(), LogVeiculo.data_registro.desc(), LogVeiculo.id.desc())
        .all()
    )
    for log in logs_fechados:
        if log.veiculo_id not in referencias:
            referencias[log.veiculo_id] = {
                "km": log.km_final,
                "origem": "ultimo_fechamento",
                "data": log.data_registro,
                "log_id": log.id,
            }

    for veiculo in veiculos:
        referencias.setdefault(
            veiculo.id,
            {
                "km": veiculo.km_atual or 0,
                "origem": "km_atual",
                "data": None,
                "log_id": None,
            },
        )

    return referencias


def _buscar_ultimo_fechamento_veiculo(veiculo_id):
    return (
        LogVeiculo.query
        .filter(LogVeiculo.veiculo_id == veiculo_id, LogVeiculo.km_final.isnot(None))
        .order_by(LogVeiculo.data_registro.desc(), LogVeiculo.id.desc())
        .first()
    )


def iniciar_turno_piloto(user, veiculo_id, form_data, files_data, root_path):
    veiculo = _veiculo_do_operacional_logado(veiculo_id, user=user)
    piloto_id = getattr(user, "piloto_id", None) if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE else None
    equipe_id = veiculo.equipe_id if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE else _parse_equipe_oceano_id(user)
    ultimo_fechamento = _buscar_ultimo_fechamento_veiculo(veiculo.id)

    try:
        km_inicial_enviado = _parse_km_form(form_data.get("km_inicial"), "Kilometragem inicial")
    except ValueError as exc:
        raise VeiculoTurnoError("Kilometragem inicial invalida.", "warning") from exc

    assinatura_b64 = form_data.get("assinatura_b64")
    foto_painel = files_data.get("foto_painel")
    km_inicial = ultimo_fechamento.km_final if ultimo_fechamento is not None else (veiculo.km_atual or 0)

    if km_inicial_enviado is not None and abs(km_inicial_enviado - km_inicial) > 0.0001:
        origem_km_inicial = (
            "o ultimo KM final registrado para este veiculo"
            if ultimo_fechamento is not None
            else "o KM atual cadastrado para este veiculo"
        )
        raise VeiculoTurnoError(
            f"KM inicial travado em {km_inicial:.0f} km, conforme {origem_km_inicial}.",
            "danger",
        )

    if km_inicial is None or not assinatura_b64 or not foto_painel or not foto_painel.filename:
        raise VeiculoTurnoError(
            "Foto do painel e assinatura sao obrigatorias.",
            "warning",
        )

    km_atual_veiculo = veiculo.km_atual or 0
    if ultimo_fechamento is None and km_atual_veiculo > 0 and abs(km_inicial - km_atual_veiculo) > 0.0001:
        raise VeiculoTurnoError("KM inicial deve ser igual ao KM atual do veiculo.", "danger")

    turno_aberto = _buscar_turno_aberto_usuario(veiculo.id, user)
    if turno_aberto:
        raise VeiculoTurnoError(
            "Ja existe um turno aberto para este veiculo. Finalize-o antes de iniciar outro.",
            "warning",
        )

    novo_log = LogVeiculo(
        veiculo_id=veiculo.id,
        piloto_id=piloto_id,
        equipe_id=equipe_id,
        km_inicial=km_inicial,
        km_final=None,
        check_diario=True,
        assinatura_piloto=assinatura_b64,
        data_registro=_now_brazil(),
    )
    novo_log.foto_painel_path = _salvar_upload_veiculo(
        foto_painel,
        root_path,
        "paineis",
        "painel_inicial",
        veiculo.placa,
        copiar_skybox=True,
    )

    db.session.add(novo_log)
    veiculo.km_atual = km_inicial

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        error_text = str(getattr(exc, "orig", exc)).lower()
        if "km_final" in error_text:
            raise VeiculoTurnoError(
                "Erro de banco: o campo km_final ainda nao aceita vazio. Rode a migracao para permitir NULL.",
                "danger",
            ) from exc
        raise

    return f"Turno de {veiculo.modelo} iniciado com sucesso!"


def registrar_abastecimento_turno_piloto(user, veiculo_id, form_data, files_data, root_path):
    veiculo = _veiculo_do_operacional_logado(veiculo_id, user=user)
    log = _buscar_turno_aberto_usuario(veiculo.id, user, incluir_abastecimentos=True)

    if not log:
        raise VeiculoTurnoError(
            "Nenhum turno aberto encontrado para registrar abastecimento.",
            "warning",
        )

    try:
        km_registro = _parse_km_form(form_data.get("km_abastecimento"), "KM do abastecimento")
        litros = _parse_decimal_form(form_data.get("litros"))
        valor_total = _parse_decimal_form(form_data.get("valor_abastecimento"))
    except ValueError as exc:
        raise VeiculoTurnoError("Os dados do abastecimento estao invalidos.", "warning") from exc

    tipo_abastecimento = (form_data.get("tipo_abastecimento") or "").strip()
    foto_nf = files_data.get("foto_nf")
    foto_painel = files_data.get("foto_painel_abastecimento")

    if (
        km_registro is None
        or litros is None
        or valor_total is None
        or not tipo_abastecimento
        or not foto_nf
        or not foto_nf.filename
        or not foto_painel
        or not foto_painel.filename
    ):
        raise VeiculoTurnoError(
            "KM, tipo, litros, valor total, foto do painel e foto da nota sao obrigatorios no abastecimento.",
            "warning",
        )

    if len(tipo_abastecimento) > 100:
        raise VeiculoTurnoError(
            "O tipo de abastecimento deve ter no maximo 100 caracteres.",
            "warning",
        )

    _validar_limite_km_turno(log.km_inicial or 0, km_registro, "KM do abastecimento")

    novo_abastecimento = Abastecimento(
        log_veiculo_id=log.id,
        data_hora=_now_brazil(),
        km_registro=km_registro,
        tipo_abastecimento=tipo_abastecimento,
        litros=litros,
        valor_total=valor_total,
        foto_nf_path=_salvar_upload_veiculo(
            foto_nf,
            root_path,
            "notas",
            "nf",
            veiculo.placa,
            copiar_skybox=True,
        ),
        foto_painel_path=_salvar_upload_veiculo(
            foto_painel,
            root_path,
            "paineis",
            "painel_abastecimento",
            veiculo.placa,
            copiar_skybox=True,
        ),
    )

    db.session.add(novo_abastecimento)
    db.session.commit()
    return "Abastecimento registrado com sucesso!"


def encerrar_turno_piloto(user, veiculo_id, form_data, files_data=None, root_path=None):
    veiculo = _veiculo_do_operacional_logado(veiculo_id, user=user)

    try:
        km_final = _parse_km_form(form_data.get("km_final"), "Kilometragem final")
    except ValueError as exc:
        raise VeiculoTurnoError("Kilometragem final invalida.", "warning") from exc

    qtd_fazendas_enderecos = _parse_optional_int(form_data.get("qtd_fazendas_enderecos"))
    observacao = (form_data.get("observacao") or "").strip() or None
    files_data = files_data or {}
    foto_painel_final = files_data.get("foto_painel_final") if hasattr(files_data, "get") else None

    if km_final is None:
        raise VeiculoTurnoError(
            "Informe a kilometragem final para encerrar o turno.",
            "warning",
        )

    if not foto_painel_final or not foto_painel_final.filename:
        raise VeiculoTurnoError(
            "A foto do painel no fechamento do turno e obrigatoria.",
            "warning",
        )

    log = _buscar_turno_aberto_usuario(veiculo_id, user, incluir_abastecimentos=True)
    if not log:
        raise VeiculoTurnoError("Nenhum turno aberto encontrado.", "warning")

    km_inicial_turno = log.km_inicial or 0
    if km_final < km_inicial_turno:
        raise VeiculoTurnoError(
            f"KM final nao pode ser menor que o KM inicial do turno ({km_inicial_turno:.0f}).",
            "danger",
        )
    maior_km_abastecimento = max(
        [
            abastecimento.km_registro
            for abastecimento in (log.abastecimentos_detalhados or [])
            if abastecimento.km_registro is not None
        ],
        default=None,
    )
    if maior_km_abastecimento is not None and km_final < maior_km_abastecimento:
        raise VeiculoTurnoError(
            f"KM final nao pode ser menor que o KM do abastecimento ({maior_km_abastecimento:.0f}).",
            "danger",
        )
    _validar_limite_km_turno(km_inicial_turno, km_final, "KM final")

    log.qtd_fazendas_enderecos = qtd_fazendas_enderecos
    log.km_final = km_final
    log.observacao = observacao
    log.foto_painel_final_path = _salvar_upload_veiculo(
        foto_painel_final,
        root_path,
        "paineis",
        "painel_fechamento",
        veiculo.placa,
        copiar_skybox=True,
    )
    if log.veiculo:
        log.veiculo.km_atual = km_final

    db.session.commit()
    return "Turno encerrado com sucesso!"


def _piloto_nome_logado(user, *, strict=False):
    nome_piloto = (getattr(user, "nome_uvis", None) or "").strip()
    if strict and (not nome_piloto or not getattr(user, "piloto_id", None)):
        raise PermissionError
    return nome_piloto


def _parse_equipe_oceano_id(user):
    raw = (getattr(user, "codigo_setor", None) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _equipe_oceano_logada(user):
    if getattr(user, "tipo_usuario", None) != EQUIPE_OCEANO_USER_TYPE:
        return None

    equipe_id = _parse_equipe_oceano_id(user)
    if not equipe_id:
        return None

    query = Equipe.query.filter(Equipe.id == equipe_id, Equipe.ativa.is_(True))
    query = apply_prefeitura_scope(query, user, Equipe.prefeitura_id)
    return query.first()


def _resolve_prefeitura_id_veiculo(equipe_id, fallback_prefeitura_id=None):
    if not equipe_id:
        return fallback_prefeitura_id

    equipe = Equipe.query.filter(Equipe.id == equipe_id).first()
    if equipe and equipe.prefeitura_id is not None:
        return equipe.prefeitura_id
    return fallback_prefeitura_id


def _veiculo_prefeitura_legacy_filter(user):
    prefeitura_id = getattr(user, "prefeitura_id", None)
    if prefeitura_id is None:
        return db.true()
    return db.or_(Veiculos.prefeitura_id == prefeitura_id, Veiculos.prefeitura_id.is_(None))


def _veiculo_responsavel_filter(nome, user):
    return db.and_(
        db.func.lower(Veiculos.responsavel) == (nome or "").strip().lower(),
        _veiculo_prefeitura_legacy_filter(user),
    )


def _veiculo_equipe_operacional_filter(equipe, user):
    return db.or_(
        Veiculos.equipe_id == equipe.id,
        _veiculo_responsavel_filter(equipe.nome_equipe, user),
    )


def _veiculo_responsavel_ok(veiculo, nome, user):
    responsavel = (getattr(veiculo, "responsavel", None) or "").strip().lower()
    if responsavel != (nome or "").strip().lower():
        return False

    prefeitura_id = getattr(user, "prefeitura_id", None)
    return prefeitura_id is None or getattr(veiculo, "prefeitura_id", None) in (None, prefeitura_id)


def _equipe_ids_do_piloto(user):
    piloto_id = getattr(user, "piloto_id", None)
    if not piloto_id:
        return []

    query = (
        db.session.query(EquipePiloto.equipe_id)
        .join(Equipe, Equipe.id == EquipePiloto.equipe_id)
        .filter(
            EquipePiloto.piloto_id == piloto_id,
            Equipe.ativa.is_(True),
        )
    )
    prefeitura_id = getattr(user, "prefeitura_id", None)
    if prefeitura_id is not None:
        query = query.filter(Equipe.prefeitura_id == prefeitura_id)

    rows = query.all()
    return [row.equipe_id for row in rows if row.equipe_id]


def _parse_decimal_form(raw_value):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None

    if "," in raw_value and "." in raw_value:
        raw_value = raw_value.replace(".", "").replace(",", ".")
    else:
        raw_value = raw_value.replace(",", ".")

    return float(raw_value)


def _parse_km_form(raw_value, label="KM"):
    raw_value = (raw_value or "").strip().replace(" ", "")
    if not raw_value:
        return None

    if re.fullmatch(r"\d+", raw_value):
        return float(raw_value)

    br_milhares = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?", raw_value)
    if br_milhares:
        decimal = br_milhares.group(2)
        if decimal and decimal.strip("0"):
            raise ValueError(f"{label} deve ser informado sem casas decimais.")
        return float(br_milhares.group(1).replace(".", ""))

    us_milhares = re.fullmatch(r"(\d{1,3}(?:,\d{3})+)(?:\.(\d+))?", raw_value)
    if us_milhares:
        decimal = us_milhares.group(2)
        if decimal and decimal.strip("0"):
            raise ValueError(f"{label} deve ser informado sem casas decimais.")
        return float(us_milhares.group(1).replace(",", ""))

    decimal_simples = re.fullmatch(r"(\d+)[,.](\d+)", raw_value)
    if decimal_simples and not decimal_simples.group(2).strip("0"):
        return float(decimal_simples.group(1))

    raise ValueError(f"{label} deve ser informado em KM inteiro, sem virgula decimal.")


def _validar_limite_km_turno(km_referencia, km_informado, label):
    km_referencia = km_referencia or 0
    if km_informado is None:
        return

    km_rodado = km_informado - km_referencia
    if km_rodado > MAX_KM_POR_TURNO:
        raise VeiculoTurnoError(
            (
                f"{label} ultrapassa o limite de {MAX_KM_POR_TURNO} km por turno. "
                f"Conferir o painel: referencia {km_referencia:.0f} km, informado {km_informado:.0f} km."
            ),
            "danger",
        )


def _parse_optional_int(raw_value):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _veiculo_do_operacional_logado(veiculo_id, *, user=None):
    query = Veiculos.query.filter(Veiculos.id == veiculo_id)
    veiculo = query.first_or_404()

    if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe = _equipe_oceano_logada(user)
        responsavel_ok = bool(equipe and _veiculo_responsavel_ok(veiculo, equipe.nome_equipe, user))
        if not equipe or (veiculo.equipe_id != equipe.id and not responsavel_ok):
            raise PermissionError
        return veiculo

    nome_piloto = _piloto_nome_logado(user, strict=True)
    equipe_ids = _equipe_ids_do_piloto(user)
    responsavel_ok = _veiculo_responsavel_ok(veiculo, nome_piloto, user)
    equipe_ok = bool(veiculo.equipe_id and veiculo.equipe_id in equipe_ids)
    if not responsavel_ok and not equipe_ok:
        raise PermissionError
    return veiculo


def _apply_log_actor_scope(query, user):
    if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe_id = _parse_equipe_oceano_id(user)
        if not equipe_id:
            return query.filter(db.false())
        return query.filter(LogVeiculo.equipe_id == equipe_id)
    return query.filter(LogVeiculo.piloto_id == getattr(user, "piloto_id", None))


def _buscar_turno_aberto_usuario(veiculo_id, user, incluir_abastecimentos=False):
    query = LogVeiculo.query.filter(LogVeiculo.veiculo_id == veiculo_id, LogVeiculo.km_final.is_(None))
    query = _apply_log_actor_scope(query, user)
    if incluir_abastecimentos:
        query = query.options(selectinload(LogVeiculo.abastecimentos_detalhados))
    return query.order_by(LogVeiculo.data_registro.desc()).first()


def _upload_veiculo_media_para_skybox(arquivo, placa, subpasta, nome, *, tipo="arquivo", dia=None):
    remote_path = build_veiculo_media_remote_path(placa, subpasta, nome, day=dia)
    try:
        marker = upload_file_to_skybox(arquivo, remote_path)
        current_app.logger.info(
            "Foto de veiculo enviada ao Skybox: placa=%s tipo=%s caminho=%s",
            placa,
            tipo,
            remote_path,
        )
        return marker
    except SkyboxError as exc:
        raise VeiculoTurnoError(
            f"Falha ao enviar {tipo} para o Skybox: {exc}",
            "danger",
        ) from exc


def build_veiculo_media_skybox_path(media_path, placa):
    if not media_path:
        return None
    if is_skybox_path(media_path):
        return media_path

    placa = (placa or "").strip()
    if not placa:
        return None

    parts = [part for part in str(media_path or "").replace("\\", "/").split("/") if part]
    if len(parts) < 4 or parts[-4] != "uploads" or parts[-3] != "veiculos":
        return None

    return build_veiculo_media_remote_path(placa, parts[-2], parts[-1], day=_dia_media_veiculo(parts[-1]))


def _dia_media_veiculo(filename):
    match = re.search(r"_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}-\d{3}\.", str(filename or ""))
    if match:
        return match.group(1)
    return None


def get_veiculo_log_for_media(user, log_id):
    tipo_usuario = normalize_role(getattr(user, "tipo_usuario", None))
    if tipo_usuario not in VEICULOS_LOGS_ALLOWED_TYPES:
        raise PermissionError

    return _build_veiculos_logs_query(user=user).filter(LogVeiculo.id == log_id).first()


def get_abastecimento_for_media(user, abastecimento_id):
    abastecimento = (
        Abastecimento.query
        .options(joinedload(Abastecimento.log_pai).joinedload(LogVeiculo.veiculo))
        .filter(Abastecimento.id == abastecimento_id)
        .first()
    )
    if not abastecimento:
        return None

    if not get_veiculo_log_for_media(user, abastecimento.log_veiculo_id):
        return None

    return abastecimento


def _salvar_upload_veiculo(arquivo, root_path, subpasta, prefixo, placa, *, copiar_skybox=False):
    if not arquivo or not arquivo.filename:
        return None

    pasta_base = os.path.join(root_path, "static", "uploads", "veiculos")
    pasta_destino = os.path.join(pasta_base, subpasta)
    os.makedirs(pasta_destino, exist_ok=True)

    ext = os.path.splitext(secure_filename(arquivo.filename))[1] or ".jpg"
    agora = _now_brazil()
    stamp = f"{agora:%Y-%m-%d_%H-%M-%S}-{agora.microsecond // 1000:03d}"
    nome = secure_filename(f"{prefixo}_{placa}_{stamp}{ext}")
    arquivo.save(os.path.join(pasta_destino, nome))

    if copiar_skybox and skybox_enabled():
        _upload_veiculo_media_para_skybox(arquivo, placa, subpasta, nome, tipo="imagem", dia=f"{agora:%Y-%m-%d}")

    return f"uploads/veiculos/{subpasta}/{nome}"


def build_veiculos_export_response(tipo_usuario, args, user=None):
    tipo_usuario = normalize_role(tipo_usuario)
    if tipo_usuario not in VEICULOS_ALLOWED_TYPES:
        raise PermissionError

    veiculos = list_veiculos(tipo_usuario, args, user=user)["veiculos"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Ve\u00edculos"

    fill_title = PatternFill("solid", fgColor="FFD966")
    fill_header = PatternFill("solid", fgColor="FFF2CC")
    fill_green = PatternFill("solid", fgColor="C6EFCE")
    fill_yellow = PatternFill("solid", fgColor="FFEB9C")
    fill_red = PatternFill("solid", fgColor="FFC7CE")
    fill_none = PatternFill()

    font_bold = Font(bold=True)
    font_title = Font(bold=True, size=12)

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    thin = Side(style="thin", color="000000")
    border_thin = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        "MODELO",
        "ANO",
        "FROTA",
        "OPERA\u00c7\u00c3O",
        "PLACA",
        "RESPONSAVEL",
        "KM ATUAL",
        "PROX REVISAO",
        "OBS",
    ]

    def write_section(title, rows, start_row):
        ws.merge_cells(start_row=start_row, start_column=2, end_row=start_row, end_column=8)
        cell = ws.cell(row=start_row, column=2, value=title)
        cell.font = font_title
        cell.alignment = align_center
        cell.fill = fill_title

        for c in range(2, 9):
            ws.cell(row=start_row, column=c).fill = fill_title
            ws.cell(row=start_row, column=c).border = border_thin

        header_row = start_row + 1
        for col_idx, header in enumerate(headers, start=1):
            current = ws.cell(row=header_row, column=col_idx, value=header)
            current.font = font_bold
            current.alignment = align_center
            current.fill = fill_header
            current.border = border_thin

        row = header_row + 1
        for veiculo in rows:
            falt = veiculo.km_restante_revisao

            obs = ""
            if veiculo.revisao_marcada_em:
                obs = "MARCADO " + veiculo.revisao_marcada_em.strftime("%d/%m %H:%M")
            elif veiculo.revisao_obs:
                obs = veiculo.revisao_obs

            data = [
                veiculo.modelo or "",
                veiculo.ano_fabricacao or "",
                veiculo.frota or "",
                veiculo.operacao or "",
                veiculo.placa or "",
                veiculo.responsavel or "",
                float(veiculo.km_atual or 0),
                float(veiculo.km_prox_revisao) if veiculo.km_prox_revisao is not None else "",
                obs,
            ]

            for col_idx, value in enumerate(data, start=1):
                current = ws.cell(row=row, column=col_idx, value=value)
                current.border = border_thin
                current.alignment = align_left if col_idx in (1, 5, 6, 9) else align_center

                if col_idx in (7, 8) and isinstance(value, (int, float)):
                    current.number_format = "#,##0.00"

                if col_idx == 7 and isinstance(value, (int, float)):
                    current.fill = fill_green

                if col_idx == 8:
                    if value == "" or falt is None:
                        current.fill = fill_none
                    elif falt < 0:
                        current.fill = fill_red
                    elif falt <= 2000:
                        current.fill = fill_yellow
                    else:
                        current.fill = fill_green

            row += 1

        return row + 2

    by_op = {}
    for veiculo in veiculos:
        operacao = (veiculo.operacao or "OUTROS").upper()
        by_op.setdefault(operacao, []).append(veiculo)

    ops_order = []
    for current in ("PMSP", "AGRO"):
        if current in by_op:
            ops_order.append(current)
    for current in sorted(by_op.keys()):
        if current not in ops_order:
            ops_order.append(current)

    current_row = 2
    for operacao in ops_order:
        current_row = write_section(f"VEICULOS {operacao}", by_op[operacao], current_row)

    col_widths = {
        1: 16,
        2: 8,
        3: 12,
        4: 12,
        5: 14,
        6: 18,
        7: 14,
        8: 14,
        9: 26,
    }
    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    response = make_response(file_stream.getvalue())
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="veiculos_{_now_brazil().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )
    return response


def _build_ultimos_logs(veiculos):
    ultimos_logs = {}
    if not veiculos:
        return ultimos_logs

    veiculo_ids = [veiculo.id for veiculo in veiculos]
    logs = (
        LogVeiculo.query
        .options(selectinload(LogVeiculo.abastecimentos_detalhados))
        .filter(LogVeiculo.veiculo_id.in_(veiculo_ids))
        .order_by(LogVeiculo.veiculo_id.asc(), LogVeiculo.data_registro.desc())
        .all()
    )
    for log in logs:
        if log.veiculo_id not in ultimos_logs:
            ultimos_logs[log.veiculo_id] = log
    return ultimos_logs


def _build_veiculos_timeline_from_logs(logs):
    historico = {}
    dias_por_veiculo = defaultdict(dict)

    for log in logs:
        veiculo = log.veiculo
        item = historico.setdefault(
            log.veiculo_id,
            {
                "veiculo": veiculo,
                "logs": [],
                "dias": [],
                "total_logs": 0,
                "total_km": 0,
                "total_gasto": 0,
                "total_abastecimentos": 0,
            },
        )
        if item["veiculo"] is None and veiculo is not None:
            item["veiculo"] = veiculo

        km_rodado = _km_rodado_log_veiculo(log)
        gasto = log.total_valor_abastecido or 0
        data_inicio = log.data_registro
        movimentacao = log.ultima_movimentacao_em or data_inicio
        dia = data_inicio.date() if data_inicio else (movimentacao.date() if movimentacao else None)
        log_info = {
            "id": log.id,
            "data": movimentacao,
            "data_inicio": data_inicio,
            "operador": _operador_log_veiculo(log),
            "km_inicial": log.km_inicial or 0,
            "km_final": log.km_final if log.km_final is not None else log.ultimo_km_registrado,
            "km_rodado": km_rodado,
            "gasto": gasto,
            "status": "Aberto" if log.km_final is None else "Encerrado",
            "abastecimentos": log.qtd_abastecimentos,
            "qtd_fazendas_enderecos": log.qtd_fazendas_enderecos,
            "observacao": log.observacao,
            "foto_painel_path": log.foto_painel_path,
            "foto_painel_final_path": log.foto_painel_final_path,
            "assinatura_piloto": log.assinatura_piloto,
            "eventos_abastecimento": _eventos_abastecimento_log_veiculo(log),
        }

        item["logs"].append(log_info)
        item["total_logs"] += 1
        item["total_km"] += km_rodado
        item["total_gasto"] += gasto
        item["total_abastecimentos"] += log.qtd_abastecimentos

        if dia is not None:
            dia_item = dias_por_veiculo[log.veiculo_id].setdefault(
                dia,
                {"dia": dia, "km_rodado": 0, "gasto": 0, "logs": 0, "abastecimentos": 0, "turnos": []},
            )
            dia_item["km_rodado"] += km_rodado
            dia_item["gasto"] += gasto
            dia_item["logs"] += 1
            dia_item["abastecimentos"] += log.qtd_abastecimentos
            dia_item["turnos"].append(log_info)

    for veiculo_id, dias in dias_por_veiculo.items():
        historico[veiculo_id]["dias"] = [
            dias[dia]
            for dia in sorted(dias.keys(), reverse=True)
        ]

    return sorted(
        historico.values(),
        key=lambda item: (
            (getattr(item["veiculo"], "modelo", "") or "").upper(),
            (getattr(item["veiculo"], "placa", "") or "").upper(),
        ),
    )


def _build_veiculo_km_conferencia(logs):
    logs_ordenados = sorted(
        logs,
        key=lambda log: (
            log.data_registro or datetime.min,
            log.id or 0,
        ),
    )
    linhas = []
    anterior = None

    for log in logs_ordenados:
        diferenca_anterior = None
        status = "primeiro"
        status_label = "Primeiro turno"

        if anterior is not None:
            if anterior.km_final is None:
                status = "anterior_aberto"
                status_label = "Anterior aberto"
            else:
                diferenca_anterior = (log.km_inicial or 0) - (anterior.km_final or 0)
                if abs(diferenca_anterior) < 0.0001:
                    status = "ok"
                    status_label = "OK"
                elif diferenca_anterior > 0:
                    status = "perdido"
                    status_label = "KM perdido"
                else:
                    status = "sobreposto"
                    status_label = "KM sobreposto"

        linhas.append(
            {
                "id": log.id,
                "data_inicio": log.data_registro,
                "operador": _operador_log_veiculo(log),
                "km_inicial": log.km_inicial or 0,
                "km_final": log.km_final,
                "ultimo_km_registrado": log.ultimo_km_registrado,
                "diferenca_anterior": diferenca_anterior,
                "status": status,
                "status_label": status_label,
                "log_anterior_id": anterior.id if anterior is not None else None,
            }
        )
        anterior = log

    return linhas


def _km_rodado_log_veiculo(log):
    km_inicial = log.km_inicial or 0
    km_final = log.km_final if log.km_final is not None else log.ultimo_km_registrado
    return max((km_final or 0) - km_inicial, 0)


def _operador_log_veiculo(log):
    if log.piloto:
        return log.piloto.nome_piloto
    if log.equipe:
        return log.equipe.nome_equipe
    return "-"


def _eventos_abastecimento_log_veiculo(log):
    eventos = []
    for abastecimento in log.abastecimentos_ordenados:
        eventos.append(
            {
                "id": abastecimento.id,
                "data": abastecimento.data_hora,
                "km": abastecimento.km_registro or 0,
                "tipo": abastecimento.tipo_abastecimento or "Abastecimento",
                "litros": abastecimento.litros or 0,
                "valor": abastecimento.valor_total or 0,
                "foto_painel_path": abastecimento.foto_painel_path,
                "foto_nf_path": abastecimento.foto_nf_path,
            }
        )
    return eventos


def _ultima_movimentacao_log_subquery():
    return (
        db.session.query(
            Abastecimento.log_veiculo_id.label("log_id"),
            db.func.max(Abastecimento.data_hora).label("ultima_movimentacao_em"),
        )
        .group_by(Abastecimento.log_veiculo_id)
        .subquery()
    )


def list_veiculos_logs(tipo_usuario, args, user=None):
    tipo_usuario = normalize_role(tipo_usuario)
    if tipo_usuario not in VEICULOS_LOGS_ALLOWED_TYPES:
        raise PermissionError

    q = (args.get("q") or "").strip()
    data_inicio = (args.get("data_inicio") or "").strip()
    data_fim = (args.get("data_fim") or "").strip()
    page = args.get("page", 1, type=int)

    query = _build_veiculos_logs_query(user=user, q=q, data_inicio=data_inicio, data_fim=data_fim)
    logs_timeline = query.all()
    paginacao = query.paginate(page=page, per_page=20, error_out=False)
    logs = paginacao.items

    return {
        "logs": logs,
        "paginacao": paginacao,
        "total_logs": query.count(),
        "total_abastecido": sum((log.total_valor_abastecido or 0) for log in logs_timeline),
        "filters": {"q": q, "data_inicio": data_inicio, "data_fim": data_fim},
        "can_edit_logs": tipo_usuario in {"dev", "admin", "operario", "operador", "prefeitura_admin"},
        "veiculos_timeline": _build_veiculos_timeline_from_logs(logs_timeline),
    }


def build_veiculo_logs_detalhe_context(tipo_usuario, veiculo_id, args, user=None):
    tipo_usuario = normalize_role(tipo_usuario)
    if tipo_usuario not in VEICULOS_LOGS_ALLOWED_TYPES:
        raise PermissionError

    data_inicio = (args.get("data_inicio") or "").strip()
    data_fim = (args.get("data_fim") or "").strip()

    veiculo = _get_veiculo_logs_scoped(veiculo_id, user)
    logs = (
        _build_veiculos_logs_query(user=user, data_inicio=data_inicio, data_fim=data_fim)
        .filter(LogVeiculo.veiculo_id == veiculo_id)
        .all()
    )
    timeline_items = _build_veiculos_timeline_from_logs(logs)
    timeline = timeline_items[0] if timeline_items else {
        "veiculo": veiculo,
        "logs": [],
        "dias": [],
        "total_logs": 0,
        "total_km": 0,
        "total_gasto": 0,
        "total_abastecimentos": 0,
    }

    return {
        "veiculo": veiculo,
        "timeline": timeline,
        "km_conferencia": _build_veiculo_km_conferencia(logs),
        "filters": {"data_inicio": data_inicio, "data_fim": data_fim},
        "can_edit_logs": tipo_usuario in {"dev", "admin", "operario", "operador", "prefeitura_admin"},
    }


def _get_veiculo_logs_scoped(veiculo_id, user):
    query = Veiculos.query.filter(Veiculos.id == veiculo_id)
    if user is not None and getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
        equipe = _equipe_oceano_logada(user)
        if not equipe:
            raise PermissionError
        query = query.filter(_veiculo_equipe_operacional_filter(equipe, user))
    elif user is not None:
        query = apply_prefeitura_scope(query, user, Veiculos.prefeitura_id)

    veiculo = query.first()
    if veiculo is None:
        raise PermissionError
    return veiculo


def update_veiculo_log_km(user, log_id, form_data):
    tipo_usuario = normalize_role(getattr(user, "tipo_usuario", None))
    if tipo_usuario not in {"dev", "admin", "operario", "operador", "prefeitura_admin"}:
        raise PermissionError

    log = (
        _build_veiculos_logs_query(user=user)
        .filter(LogVeiculo.id == log_id)
        .first()
    )
    if log is None:
        raise PermissionError

    km_inicial = _parse_log_km_field(form_data, "km_inicial", "KM inicial", required=True)
    km_final = _parse_log_km_field(form_data, "km_final", "KM final")
    if km_final is not None and km_final < km_inicial:
        raise VeiculoTurnoError("KM final nao pode ser menor que o KM inicial.")

    abastecimentos = list(log.abastecimentos_detalhados or [])
    abastecimento_kms = []
    for abastecimento in abastecimentos:
        field_name = f"abastecimento_{abastecimento.id}_km"
        km_registro = _parse_log_km_field(
            form_data,
            field_name,
            f"KM do abastecimento #{abastecimento.id}",
            required=True,
        )
        abastecimento_kms.append((abastecimento, km_registro))

    maior_km_abastecimento = max([km for _item, km in abastecimento_kms], default=None)
    if km_final is not None and maior_km_abastecimento is not None and km_final < maior_km_abastecimento:
        raise VeiculoTurnoError("KM final nao pode ser menor que o maior KM de abastecimento.")

    log.km_inicial = km_inicial
    log.km_final = km_final
    for abastecimento, km_registro in abastecimento_kms:
        abastecimento.km_registro = km_registro

    _recalcular_km_atual_veiculo(log.veiculo_id)
    db.session.commit()
    return f"Log #{log.id} corrigido com sucesso."


def delete_veiculo_log(user, log_id):
    tipo_usuario = normalize_role(getattr(user, "tipo_usuario", None))
    if tipo_usuario not in {"dev", "admin", "operario", "operador", "prefeitura_admin"}:
        raise PermissionError

    log = (
        _build_veiculos_logs_query(user=user)
        .filter(LogVeiculo.id == log_id)
        .first()
    )
    if log is None:
        raise PermissionError

    veiculo_id = log.veiculo_id
    db.session.delete(log)
    db.session.flush()
    _recalcular_km_atual_veiculo(veiculo_id)
    db.session.commit()
    return f"Log #{log_id} excluido com sucesso."


def _parse_log_km_field(form_data, field_name, label, *, required=False):
    raw_value = (form_data.get(field_name) or "").strip()
    if not raw_value:
        if required:
            raise VeiculoTurnoError(f"Informe {label}.")
        return None

    try:
        value = _parse_km_form(raw_value, label)
    except (TypeError, ValueError):
        raise VeiculoTurnoError(f"{label} deve ser informado em KM inteiro, sem virgula decimal.")

    if value is None:
        if required:
            raise VeiculoTurnoError(f"Informe {label}.")
        return None
    if value < 0:
        raise VeiculoTurnoError(f"{label} nao pode ser negativo.")
    return value


def _recalcular_km_atual_veiculo(veiculo_id):
    veiculo = db.session.get(Veiculos, veiculo_id)
    if veiculo is None:
        return None

    ultimo_log_fechado = (
        LogVeiculo.query
        .filter(LogVeiculo.veiculo_id == veiculo_id, LogVeiculo.km_final.isnot(None))
        .order_by(LogVeiculo.data_registro.desc(), LogVeiculo.id.desc())
        .first()
    )
    if ultimo_log_fechado is not None:
        veiculo.km_atual = ultimo_log_fechado.km_final or 0
        return veiculo.km_atual

    ultimo_log = (
        LogVeiculo.query
        .filter(LogVeiculo.veiculo_id == veiculo_id)
        .order_by(LogVeiculo.data_registro.desc(), LogVeiculo.id.desc())
        .first()
    )
    veiculo.km_atual = (ultimo_log.km_inicial if ultimo_log is not None else 0) or 0
    return veiculo.km_atual


def build_veiculos_logs_export(tipo_usuario, args, user=None):
    tipo_usuario = normalize_role(tipo_usuario)
    if tipo_usuario not in VEICULOS_LOGS_ALLOWED_TYPES:
        raise PermissionError

    q = (args.get("q") or "").strip()
    data_inicio = (args.get("data_inicio") or "").strip()
    data_fim = (args.get("data_fim") or "").strip()

    logs = _build_veiculos_logs_query(user=user, q=q, data_inicio=data_inicio, data_fim=data_fim).all()

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_header(ws, row=1, height=28):
        ws.row_dimensions[row].height = height
        for cell in ws[row]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = border

    def auto_width(ws, max_col, min_w=10, max_w=48):
        for col in range(1, max_col + 1):
            letter = get_column_letter(col)
            max_len = 0
            for cell in ws[letter]:
                if cell.value is None:
                    continue
                max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[letter].width = max(min_w, min(max_w, max_len + 2))

    def center_cols(ws, cols, start_row, end_row):
        for col in cols:
            for row in range(start_row, end_row + 1):
                ws.cell(row=row, column=col).alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )

    wb = Workbook()
    ws = wb.active
    ws.title = "Detalhamento"

    headers = [
        "Ultima Movimentacao",
        "Veiculo",
        "Placa",
        "Responsavel",
        "Operador / Equipe",
        "Check Diario",
        "KM Inicial",
        "KM Final",
        "KM Rodado",
        "Abasteceu",
        "Qtd. Abastecimentos",
        "Tipos de Abastecimento",
        "Litros",
        "Valor Abastecimento (R$)",
        "Valor por Litro (R$)",
        "Custo por KM (R$)",
        "Assinatura",
        "Observacao",
    ]
    ws.append(headers)
    style_header(ws, row=1)
    ws.freeze_panes = "A2"

    for log in logs:
        ws.append([
            log.ultima_movimentacao_em.strftime("%d/%m/%Y %H:%M") if log.ultima_movimentacao_em else "",
            (log.veiculo.modelo if log.veiculo else "") or "",
            (log.veiculo.placa if log.veiculo else "") or "",
            (log.veiculo.responsavel if log.veiculo else "") or "",
            (log.piloto.nome_piloto if log.piloto else None)
            or (log.equipe.nome_equipe if log.equipe else "")
            or "",
            "SIM" if log.check_diario else "N\u00c3O",
            float(log.km_inicial or 0),
            "" if log.km_final is None else float(log.km_final),
            None,
            "SIM" if log.teve_abastecimento else "N\u00c3O",
            int(log.qtd_abastecimentos or 0),
            log.tipos_abastecimento_resumo or "",
            float(log.total_litros_abastecidos or 0),
            float(log.total_valor_abastecido or 0),
            None,
            None,
            "SIM" if log.assinatura_piloto else "N\u00c3O",
            log.observacao or "",
        ])

    last_row = ws.max_row
    last_col = ws.max_column
    ws.auto_filter.ref = f"A1:{get_column_letter(last_col)}{last_row}"

    col_data = 1
    col_check = 6
    col_km_ini = 7
    col_km_fim = 8
    col_km_rod = 9
    col_abast = 10
    col_qtd_ab = 11
    col_litros = 13
    col_valor = 14
    col_val_litro = 15
    col_custo_km = 16
    col_ass = 17

    for row in range(2, last_row + 1):
        ws.cell(row, col_km_rod).value = (
            f'=IF({get_column_letter(col_km_fim)}{row}="","",'
            f'{get_column_letter(col_km_fim)}{row}-{get_column_letter(col_km_ini)}{row})'
        )
        ws.cell(row, col_val_litro).value = (
            f'=IF(OR({get_column_letter(col_litros)}{row}="",{get_column_letter(col_litros)}{row}=0),"",'
            f'{get_column_letter(col_valor)}{row}/{get_column_letter(col_litros)}{row})'
        )
        ws.cell(row, col_custo_km).value = (
            f'=IF(OR({get_column_letter(col_km_rod)}{row}="",{get_column_letter(col_km_rod)}{row}=0),"",'
            f'{get_column_letter(col_valor)}{row}/{get_column_letter(col_km_rod)}{row})'
        )

        ws.cell(row, col_km_ini).number_format = "#,##0.00"
        ws.cell(row, col_km_fim).number_format = "#,##0.00"
        ws.cell(row, col_km_rod).number_format = "#,##0.00"
        ws.cell(row, col_qtd_ab).number_format = "0"
        ws.cell(row, col_litros).number_format = "#,##0.00"
        ws.cell(row, col_valor).number_format = '"R$" #,##0.00'
        ws.cell(row, col_val_litro).number_format = '"R$" #,##0.00'
        ws.cell(row, col_custo_km).number_format = '"R$" #,##0.00'

        for col in range(1, last_col + 1):
            current = ws.cell(row, col)
            current.border = border
            current.alignment = Alignment(vertical="center", wrap_text=True)

    center_cols(ws, cols=[col_data, col_check, col_abast, col_ass], start_row=2, end_row=last_row)

    stripe_fill = PatternFill("solid", fgColor="F2F2F2")
    white_fill = PatternFill("solid", fgColor="FFFFFF")
    highlight_fill = PatternFill("solid", fgColor="FFF2CC")
    highlight_cols = {col_litros, col_valor, col_val_litro, col_custo_km}

    for row in range(2, last_row + 1):
        row_fill = stripe_fill if (row % 2 == 0) else white_fill
        for col in range(1, last_col + 1):
            current = ws.cell(row, col)
            current.fill = row_fill
            if col in highlight_cols and current.value not in (None, ""):
                current.fill = highlight_fill

    green_fill = PatternFill("solid", fgColor="C6EFCE")
    green_font = Font(color="006100", bold=True)
    red_fill = PatternFill("solid", fgColor="FFC7CE")
    red_font = Font(color="9C0006", bold=True)

    for col in (col_check, col_abast, col_ass):
        col_letter = get_column_letter(col)
        cell_range = f"{col_letter}2:{col_letter}{last_row}"
        ws.conditional_formatting.add(
            cell_range,
            FormulaRule(formula=[f'{col_letter}2="SIM"'], fill=green_fill, font=green_font),
        )
        ws.conditional_formatting.add(
            cell_range,
            FormulaRule(formula=[f'{col_letter}2="N\u00c3O"'], fill=red_fill, font=red_font),
        )

    auto_width(ws, last_col, min_w=10, max_w=48)

    ws2 = wb.create_sheet("Resumo (M\u00e9dias)")

    title_fill = PatternFill("solid", fgColor="0B2F4F")
    card_fill = PatternFill("solid", fgColor="E7EFF8")
    info_fill = PatternFill("solid", fgColor="F8F8F8")
    kpi_fill = PatternFill("solid", fgColor="D9E1F2")

    title_font = Font(color="FFFFFF", bold=True, size=14)
    section_font = Font(color="1F4E79", bold=True, size=12)
    label_font = Font(color="1F4E79", bold=True)
    small_font = Font(color="404040", size=10)
    big_font = Font(color="1F4E79", bold=True, size=16)

    has_data = last_row >= 2
    rng_km_rod = f"Detalhamento!{get_column_letter(col_km_rod)}2:{get_column_letter(col_km_rod)}{last_row}"
    rng_valor = f"Detalhamento!{get_column_letter(col_valor)}2:{get_column_letter(col_valor)}{last_row}"
    rng_litros = f"Detalhamento!{get_column_letter(col_litros)}2:{get_column_letter(col_litros)}{last_row}"
    rng_vl = f"Detalhamento!{get_column_letter(col_val_litro)}2:{get_column_letter(col_val_litro)}{last_row}"
    rng_ckm = f"Detalhamento!{get_column_letter(col_custo_km)}2:{get_column_letter(col_custo_km)}{last_row}"
    rng_qtd_ab = f"Detalhamento!{get_column_letter(col_qtd_ab)}2:{get_column_letter(col_qtd_ab)}{last_row}"

    ws2.merge_cells("A1:H1")
    ws2["A1"] = "RESUMO - M\u00c9DIAS E INDICADORES (FROTA)"
    ws2["A1"].fill = title_fill
    ws2["A1"].font = title_font
    ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 30

    ws2.merge_cells("A2:H2")
    ws2["A2"] = "Painel de custos, consumo e produtividade com base nos registros da aba Detalhamento."
    ws2["A2"].font = small_font
    ws2["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[2].height = 18

    ws2.merge_cells("A4:C4")
    ws2.merge_cells("A5:C6")
    ws2["A4"] = "Total de Registros"
    ws2["A5"] = (f"={max(0, last_row - 1)}" if has_data else "")
    ws2["A4"].font = label_font
    ws2["A5"].font = big_font
    ws2["A4"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["A5"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["A4"].fill = kpi_fill
    ws2["A5"].fill = card_fill

    ws2.merge_cells("D4:F4")
    ws2.merge_cells("D5:F6")
    ws2["D4"] = "Total Abastecido (R$)"
    ws2["D5"] = (f"=SUM({rng_valor})" if has_data else "")
    ws2["D4"].font = label_font
    ws2["D5"].font = big_font
    ws2["D4"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["D5"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["D4"].fill = kpi_fill
    ws2["D5"].fill = card_fill
    ws2["D5"].number_format = '"R$" #,##0.00'

    ws2.merge_cells("G4:H4")
    ws2.merge_cells("G5:H6")
    ws2["G4"] = "Total de Litros"
    ws2["G5"] = (f"=SUM({rng_litros})" if has_data else "")
    ws2["G4"].font = label_font
    ws2["G5"].font = big_font
    ws2["G4"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["G5"].alignment = Alignment(horizontal="center", vertical="center")
    ws2["G4"].fill = kpi_fill
    ws2["G5"].fill = card_fill
    ws2["G5"].number_format = "#,##0.00"

    for row in range(4, 7):
        for col in range(1, 9):
            ws2.cell(row, col).border = border
            ws2.cell(row, col).alignment = Alignment(wrap_text=True, vertical="center")

    ws2["A8"] = "M\u00c9DIAS PRINCIPAIS"
    ws2["A8"].font = section_font
    ws2.merge_cells("A8:H8")

    ws2["A9"] = "M\u00e9trica"
    ws2["D9"] = "Resultado"
    ws2["F9"] = "Como interpretar"
    ws2.merge_cells("A9:C9")
    ws2.merge_cells("D9:E9")
    ws2.merge_cells("F9:H9")

    for cell in ws2["A9:H9"][0]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws2.row_dimensions[9].height = 22

    metrics = [
        ("M\u00e9dia de KM Rodado", f'=AVERAGEIF({rng_km_rod},">0")', "M\u00e9dia de km por registro."),
        ("M\u00e9dia Valor Abastecimento (R$)", f'=AVERAGEIF({rng_valor},">0")', "Valor m\u00e9dio por abastecimento."),
        ("M\u00e9dia Valor por Litro (R$)", f'=AVERAGEIF({rng_vl},">0")', "Pre\u00e7o m\u00e9dio pago por litro."),
        ("M\u00e9dia Custo por KM (R$)", f'=AVERAGEIF({rng_ckm},">0")', "Custo m\u00e9dio por km."),
        ("Qtd. de Abastecimentos", f"=SUM({rng_qtd_ab})", "Quantidade total registrada."),
    ]

    base_row = 10
    for offset, (name, formula, tip) in enumerate(metrics):
        row = base_row + offset
        ws2.merge_cells(f"A{row}:C{row}")
        ws2.merge_cells(f"D{row}:E{row}")
        ws2.merge_cells(f"F{row}:H{row}")

        ws2[f"A{row}"] = name
        ws2[f"D{row}"] = (formula if has_data else "")
        ws2[f"F{row}"] = tip
        ws2[f"A{row}"].font = Font(bold=True, color="1F4E79")
        ws2[f"F{row}"].font = small_font

        for col in range(1, 9):
            current = ws2.cell(row, col)
            current.border = border
            current.alignment = Alignment(vertical="center", wrap_text=True)
            current.fill = info_fill if (offset % 2 == 0) else PatternFill("solid", fgColor="FFFFFF")

    if has_data:
        ws2[f"D{base_row}"].number_format = "#,##0.00"
        ws2[f"D{base_row + 1}"].number_format = '"R$" #,##0.00'
        ws2[f"D{base_row + 2}"].number_format = '"R$" #,##0.00'
        ws2[f"D{base_row + 3}"].number_format = '"R$" #,##0.00'
        ws2[f"D{base_row + 4}"].number_format = "0"

    warn_fill = PatternFill("solid", fgColor="FFF2CC")
    ok_fill = PatternFill("solid", fgColor="C6EFCE")
    bad_fill = PatternFill("solid", fgColor="FFC7CE")

    alert_row = base_row + len(metrics) + 2
    ws2[f"A{alert_row}"] = "ALERTAS (LEITURA R\u00c1PIDA)"
    ws2[f"A{alert_row}"].font = section_font
    ws2.merge_cells(f"A{alert_row}:H{alert_row}")

    limiar_ckm = 1.50
    ws2.merge_cells(f"A{alert_row + 1}:E{alert_row + 1}")
    ws2.merge_cells(f"F{alert_row + 1}:H{alert_row + 1}")
    ws2[f"A{alert_row + 1}"] = f"Custo por KM acima de R$ {limiar_ckm:.2f}"
    ws2[f"F{alert_row + 1}"] = (
        f'=IF(AVERAGEIF({rng_ckm},">0")>{limiar_ckm},"ATEN\u00c7\u00c3O: ALTO","OK")'
        if has_data else ""
    )
    ws2[f"A{alert_row + 1}"].font = Font(bold=True, color="1F4E79")
    ws2[f"F{alert_row + 1}"].font = Font(bold=True)

    for col in range(1, 9):
        current = ws2.cell(alert_row + 1, col)
        current.border = border
        current.alignment = Alignment(vertical="center", wrap_text=True)
        current.fill = warn_fill

    alert_range = f"F{alert_row + 1}:H{alert_row + 1}"
    ws2.conditional_formatting.add(
        alert_range,
        FormulaRule(
            formula=[f'F{alert_row + 1}="OK"'],
            fill=ok_fill,
            font=Font(color="006100", bold=True),
        ),
    )
    ws2.conditional_formatting.add(
        alert_range,
        FormulaRule(
            formula=[f'F{alert_row + 1}<>"OK"'],
            fill=bad_fill,
            font=Font(color="9C0006", bold=True),
        ),
    )

    ws2.freeze_panes = "A10"
    ws2.column_dimensions["A"].width = 24
    ws2.column_dimensions["B"].width = 10
    ws2.column_dimensions["C"].width = 10
    ws2.column_dimensions["D"].width = 16
    ws2.column_dimensions["E"].width = 10
    ws2.column_dimensions["F"].width = 22
    ws2.column_dimensions["G"].width = 14
    ws2.column_dimensions["H"].width = 14

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"logs_veiculos_{_now_brazil().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _build_veiculos_logs_query(*, user=None, q="", data_inicio="", data_fim=""):
    ultima_movimentacao_subq = _ultima_movimentacao_log_subquery()
    ultima_movimentacao_expr = db.func.coalesce(
        ultima_movimentacao_subq.c.ultima_movimentacao_em,
        LogVeiculo.data_registro,
    )

    query = (
        LogVeiculo.query
        .options(
            joinedload(LogVeiculo.veiculo),
            joinedload(LogVeiculo.piloto),
            joinedload(LogVeiculo.equipe),
            selectinload(LogVeiculo.abastecimentos_detalhados),
        )
        .outerjoin(ultima_movimentacao_subq, ultima_movimentacao_subq.c.log_id == LogVeiculo.id)
        .join(Veiculos, LogVeiculo.veiculo_id == Veiculos.id)
        .outerjoin(Pilotos, LogVeiculo.piloto_id == Pilotos.id)
        .outerjoin(Equipe, LogVeiculo.equipe_id == Equipe.id)
    )
    if user is not None:
        if getattr(user, "tipo_usuario", None) == EQUIPE_OCEANO_USER_TYPE:
            equipe = _equipe_oceano_logada(user)
            if not equipe:
                query = query.filter(db.false())
            else:
                query = query.filter(
                    db.or_(
                        LogVeiculo.equipe_id == equipe.id,
                        _veiculo_equipe_operacional_filter(equipe, user),
                    )
                )
        else:
            query = apply_prefeitura_scope(query, user, Veiculos.prefeitura_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                id_search_clause(LogVeiculo.id, q),
                id_search_clause(Veiculos.id, q),
                id_search_clause(Pilotos.id, q),
                id_search_clause(Equipe.id, q),
                Veiculos.modelo.ilike(like),
                Veiculos.placa.ilike(like),
                Veiculos.responsavel.ilike(like),
                Pilotos.nome_piloto.ilike(like),
                Equipe.nome_equipe.ilike(like),
            )
        )

    if data_inicio:
        try:
            dt_ini = datetime.strptime(data_inicio, "%Y-%m-%d")
            query = query.filter(ultima_movimentacao_expr >= dt_ini)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(ultima_movimentacao_expr <= dt_fim)
        except ValueError:
            pass

    return query.order_by(ultima_movimentacao_expr.desc(), LogVeiculo.id.desc())
