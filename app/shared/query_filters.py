from sqlalchemy import Integer, cast, extract

from app.models import Solicitacao


def aplicar_filtros_base(query, filtro_data, uvis_id):
    if filtro_data:
        try:
            ano, mes = map(int, filtro_data.split("-"))
            query = query.filter(
                cast(extract("year", Solicitacao.data_agendamento), Integer) == ano,
                cast(extract("month", Solicitacao.data_agendamento), Integer) == mes,
            )
            print(f"DEBUG SQL: Filtrando por Ano={ano} e Mes={mes}")
        except Exception as exc:
            print(f"Erro no filtro de data: {exc}")

    if uvis_id:
        query = query.filter(Solicitacao.usuario_id == int(uvis_id))

    return query
