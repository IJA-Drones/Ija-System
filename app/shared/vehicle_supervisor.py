"""Operational team and equipment access for vehicle supervisors."""

from app.extensions import db
from app.models import Equipe, Veiculos
from app.shared.access import apply_prefeitura_scope, is_veiculos_supervisor


def get_supervisor_equipe(user):
    """O supervisor não pertence a uma equipe como usuário."""
    return None


def get_supervisor_operational_equipe(user):
    """Equipe do veículo atribuído, apenas como contexto para ordens de serviço."""
    if not is_veiculos_supervisor(user):
        return None
    veiculo = (
        supervisor_equipment_query(Veiculos, user)
        .filter(Veiculos.responsavel == f"sup_veiculos:{user.id}")
        .first()
    )
    return veiculo.equipe if veiculo else None


def supervisor_equipment_query(model, user):
    """
    Libera o acesso aos veículos com base estritamente na prefeitura do utilizador,
    permitindo que o supervisor visualize e opere a frota sem travas de equipa.
    """
    query = model.query
    prefeitura_id = getattr(user, "prefeitura_id", None)
    
    if prefeitura_id is not None:
        # Filtra diretamente pelos veículos da prefeitura do supervisor
        query = query.filter(
            db.or_(
                model.prefeitura_id == prefeitura_id,
                db.and_(
                    model.prefeitura_id.is_(None),
                    model.equipe.has(Equipe.prefeitura_id == prefeitura_id),
                ),
            )
        )
    return query
