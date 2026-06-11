from sqlalchemy import Integer, cast, extract, false

from app.models import Solicitacao


def parse_search_id(value, prefixes=("id",)):
    text = (value or "").strip().lower()
    if not text:
        return None

    for prefix in prefixes or ():
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip(" #:-")
            break

    text = text.lstrip(" #:-")
    if text.isdigit():
        return int(text)
    return None


def id_search_clause(column, value, prefixes=("id",)):
    search_id = parse_search_id(value, prefixes=prefixes)
    return column == search_id if search_id is not None else false()


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
