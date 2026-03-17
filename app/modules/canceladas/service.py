from sqlalchemy.orm import joinedload

from app.models import Solicitacao


def build_canceladas_query(user):
    return (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
        )
        .filter(Solicitacao.usuario_id == user.id)
        .filter(Solicitacao.status == "CANCELADO")
        .order_by(Solicitacao.data_criacao.desc())
    )
