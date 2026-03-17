from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Baterias, Drones, Equipe, EquipePiloto, Solicitacao, Veiculos
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
    "APROVADO COM RECOMENDAÇÕES",
    "APROVADA COM RECOMENDAÇÕES",
]
STATUS_OS_CONCLUIDAS = ["CONCLUIDO", "CONCLUÍDO"]


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
