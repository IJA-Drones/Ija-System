import os
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.models import Denuncia, DenunciaAnexo, Usuario
from app.extensions import db
from app.shared.access import get_user_regiao, is_admin_global_user, is_covisa_user, is_regional_user
from app.shared.uploads import get_upload_folder


DENUNCIA_TRIAGEM_STATUSES = {
    Denuncia.STATUS_RECEBIDA,
    Denuncia.STATUS_EM_TRIAGEM_COVISA,
}

COORDENADORIAS_DENUNCIA = (
    "CENTRO",
    "NORTE",
    "SUL",
    "LESTE",
    "OESTE",
    "SUDESTE",
    "CENTRO-OESTE",
)


def can_access_denuncias(user):
    return bool(
        is_covisa_user(user)
        or is_admin_global_user(user)
        or is_regional_user(user)
        or getattr(user, "tipo_usuario", None) == "uvis"
    )


def can_access_denuncia(user, denuncia):
    if is_covisa_user(user) or is_admin_global_user(user):
        return True
    if is_regional_user(user):
        return get_user_regiao(user) == (denuncia.coordenadoria or "").strip().upper()
    if getattr(user, "tipo_usuario", None) == "uvis":
        return denuncia.uvis_usuario_id == getattr(user, "id", None)
    return False


def count_denuncias_alerta(user):
    if not can_access_denuncias(user):
        return 0
    query = Denuncia.query
    if is_regional_user(user):
        regiao = get_user_regiao(user)
        if not regiao:
            return 0
        query = query.filter(
            func.upper(func.coalesce(Denuncia.coordenadoria, "")) == regiao,
            Denuncia.status == Denuncia.STATUS_ENCAMINHADA_COORDENADORIA,
        )
        return query.count()
    if getattr(user, "tipo_usuario", None) == "uvis":
        return query.filter(
            Denuncia.uvis_usuario_id == getattr(user, "id", None),
            Denuncia.status == Denuncia.STATUS_ENCAMINHADA_UVIS,
            Denuncia.solicitacao_id.is_(None),
        ).count()
    return query.filter(Denuncia.status.in_(DENUNCIA_TRIAGEM_STATUSES)).count()


def build_denuncias_query(args):
    status = (args.get("status") or "").strip()
    q = (args.get("q") or "").strip()
    tipo_visita = (args.get("tipo_visita") or "").strip()

    query = Denuncia.query.options(joinedload(Denuncia.anexos))

    if status:
        query = query.filter(Denuncia.status == status)
    if tipo_visita:
        query = query.filter(Denuncia.tipo_visita == tipo_visita)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Denuncia.protocolo.ilike(like),
                Denuncia.foco.ilike(like),
                Denuncia.logradouro.ilike(like),
                Denuncia.numero.ilike(like),
                Denuncia.bairro.ilike(like),
                Denuncia.cidade.ilike(like),
                Denuncia.cep.ilike(like),
                Denuncia.cidadao_nome.ilike(like),
            )
        )

    return query.order_by(Denuncia.criado_em.desc(), Denuncia.id.desc())


def build_denuncias_coordenadoria_query(user, args):
    regiao = get_user_regiao(user)
    query = build_denuncias_query(args)
    if not regiao:
        return query.filter(db.false())
    return query.filter(func.upper(func.coalesce(Denuncia.coordenadoria, "")) == regiao)


def build_denuncias_uvis_query(user, args):
    return (
        build_denuncias_query(args)
        .filter(Denuncia.uvis_usuario_id == getattr(user, "id", None))
        .filter(Denuncia.status.in_((Denuncia.STATUS_ENCAMINHADA_UVIS, Denuncia.STATUS_CONVERTIDA_SOLICITACAO)))
    )


def get_denuncia_or_404(denuncia_id):
    return Denuncia.query.options(joinedload(Denuncia.anexos)).filter(Denuncia.id == denuncia_id).first_or_404()


def get_denuncia_scoped_or_404(denuncia_id, user):
    denuncia = get_denuncia_or_404(denuncia_id)
    if not can_access_denuncia(user, denuncia):
        from flask import abort

        abort(403)
    return denuncia


def get_anexo_or_404(anexo_id):
    return DenunciaAnexo.query.join(Denuncia).filter(DenunciaAnexo.id == anexo_id).first_or_404()


def resolve_denuncia_local_media(anexo):
    rel = (anexo.arquivo_path or "").replace("\\", "/")
    if rel.startswith("upload-files/"):
        rel = rel.split("upload-files/", 1)[1]
    if rel.startswith("/") or any(part in {".", ".."} for part in rel.split("/")):
        raise FileNotFoundError("Caminho de anexo invalido.")

    upload_folder = get_upload_folder()
    absolute_path = os.path.join(upload_folder, rel.replace("/", os.sep))
    if not os.path.isfile(absolute_path):
        raise FileNotFoundError("Anexo nao encontrado.")

    return upload_folder, rel, anexo.arquivo_nome or os.path.basename(rel)


def encaminhar_denuncia_para_coordenadoria(denuncia, coordenadoria, user):
    coordenadoria = (coordenadoria or "").strip().upper()
    if coordenadoria not in COORDENADORIAS_DENUNCIA:
        raise ValueError("Selecione uma coordenadoria valida.")

    denuncia.coordenadoria = coordenadoria
    denuncia.status = Denuncia.STATUS_ENCAMINHADA_COORDENADORIA
    denuncia.triado_por_id = getattr(user, "id", None)
    denuncia.encaminhado_em = datetime.now()
    denuncia.arquivado_em = None
    denuncia.arquivado_motivo = None
    db.session.commit()
    return denuncia


def arquivar_denuncia(denuncia, motivo, user):
    motivo = " ".join((motivo or "").strip().split())
    if len(motivo) < 10:
        raise ValueError("Informe um motivo com pelo menos 10 caracteres.")

    denuncia.status = Denuncia.STATUS_ARQUIVADA
    denuncia.triado_por_id = getattr(user, "id", None)
    denuncia.arquivado_em = datetime.now()
    denuncia.arquivado_motivo = motivo
    db.session.commit()
    return denuncia


def build_uvis_options_for_denuncia(denuncia):
    coordenadoria = (denuncia.coordenadoria or "").strip().upper()
    if not coordenadoria:
        return []
    return (
        Usuario.query
        .filter(Usuario.tipo_usuario == "uvis")
        .filter(func.upper(func.coalesce(Usuario.regiao, "")) == coordenadoria)
        .order_by(Usuario.nome_uvis.asc())
        .all()
    )


def designar_denuncia_para_uvis(denuncia, uvis_id, user):
    if not is_regional_user(user) and not is_admin_global_user(user):
        raise ValueError("Usuario sem permissao para designar UVIS.")

    user_regiao = get_user_regiao(user)
    coordenadoria = (denuncia.coordenadoria or "").strip().upper()
    if is_regional_user(user) and user_regiao != coordenadoria:
        raise ValueError("Esta denuncia nao pertence a sua coordenadoria.")

    try:
        uvis_id = int(uvis_id)
    except (TypeError, ValueError):
        raise ValueError("Selecione uma UVIS valida.")

    uvis = Usuario.query.filter(Usuario.id == uvis_id, Usuario.tipo_usuario == "uvis").first()
    if not uvis:
        raise ValueError("Selecione uma UVIS valida.")
    if (uvis.regiao or "").strip().upper() != coordenadoria:
        raise ValueError("A UVIS selecionada nao pertence a coordenadoria da denuncia.")

    denuncia.uvis_usuario_id = uvis.id
    denuncia.status = Denuncia.STATUS_ENCAMINHADA_UVIS
    denuncia.triado_por_id = getattr(user, "id", None)
    db.session.commit()
    return denuncia


def build_solicitacao_form_from_denuncia(denuncia, form_source=None):
    form_source = form_source or {}
    return {
        "data": (form_source.get("data") or "").strip(),
        "hora": (form_source.get("hora") or "").strip(),
        "cep": (form_source.get("cep") or denuncia.cep or "").strip(),
        "logradouro": (form_source.get("logradouro") or denuncia.logradouro or "").strip(),
        "numero": (form_source.get("numero") or denuncia.numero or "").strip(),
        "complemento": (form_source.get("complemento") or denuncia.complemento or "").strip(),
        "bairro": (form_source.get("bairro") or denuncia.bairro or "").strip(),
        "cidade": (form_source.get("cidade") or denuncia.cidade or "").strip(),
        "uf": (form_source.get("uf") or denuncia.uf or "").strip(),
        "latitude": (form_source.get("latitude") or denuncia.latitude or "").strip(),
        "longitude": (form_source.get("longitude") or denuncia.longitude or "").strip(),
        "place_id": (form_source.get("place_id") or denuncia.place_id or "").strip(),
        "tipo_visita": (form_source.get("tipo_visita") or denuncia.tipo_visita or "").strip(),
        "tipo_visita_outros": (form_source.get("tipo_visita_outros") or "").strip(),
        "tipo_imovel": (form_source.get("tipo_imovel") or denuncia.tipo_imovel or "").strip(),
        "foco": (form_source.get("foco") or denuncia.foco or "").strip(),
        "tipo_operacao": (form_source.get("tipo_operacao") or "").strip(),
        "altura_voo": (form_source.get("altura_voo") or "").strip(),
        "distrito_administrativo": (form_source.get("distrito_administrativo") or "").strip(),
        "apoio_cet": (form_source.get("apoio_cet") or "").strip(),
        "observacao": (
            form_source.get("observacao")
            or f"Solicitação originada da denúncia {denuncia.protocolo}. {denuncia.descricao or ''}".strip()
        ),
    }
