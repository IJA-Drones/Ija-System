from sqlalchemy import Integer, cast, extract, false

from app.models import Solicitacao


def _as_raw_values(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def get_multi_values(args, name):
    raw_values = []
    if hasattr(args, "getlist"):
        raw_values = args.getlist(name)
    elif isinstance(args, dict):
        raw_values = _as_raw_values(args.get(name))

    if not raw_values and hasattr(args, "get"):
        raw_values = _as_raw_values(args.get(name))

    values = []
    seen = set()
    for raw_value in raw_values:
        for piece in str(raw_value or "").split(","):
            value = piece.strip()
            if value and value not in seen:
                values.append(value)
                seen.add(value)
    return values


def get_multi_int_values(args, name):
    values = []
    seen = set()
    for value in get_multi_values(args, name):
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            continue
        if int_value not in seen:
            values.append(int_value)
            seen.add(int_value)
    return values


def normalize_multi_values(value):
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = _as_raw_values(value)

    values = []
    seen = set()
    for raw_value in raw_values:
        for piece in str(raw_value or "").split(","):
            item = piece.strip()
            if item and item not in seen:
                values.append(item)
                seen.add(item)
    return values


def normalize_multi_int_values(value):
    values = []
    seen = set()
    for item in normalize_multi_values(value):
        try:
            int_value = int(item)
        except (TypeError, ValueError):
            continue
        if int_value not in seen:
            values.append(int_value)
            seen.add(int_value)
    return values


def first_or_empty(values):
    values = normalize_multi_values(values)
    return values[0] if values else ""


def multi_value_to_query(value):
    values = normalize_multi_values(value)
    return ",".join(values)


MULTI_VALUE_QUERY_KEYS = {"unidade", "foco", "uvis_id"}


def query_args_without_page(args):
    result = {}
    keys = args.keys() if hasattr(args, "keys") else []
    for key in keys:
        if key == "page":
            continue
        if key in MULTI_VALUE_QUERY_KEYS:
            values = get_multi_values(args, key)
            if values:
                result[key] = multi_value_to_query(values)
            continue

        values = args.getlist(key) if hasattr(args, "getlist") else _as_raw_values(args.get(key))
        values = [str(value).strip() for value in values if str(value or "").strip()]
        if values:
            result[key] = values[0] if len(values) == 1 else ",".join(values)
    return result


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

    uvis_ids = normalize_multi_int_values(uvis_id)
    if uvis_ids:
        query = query.filter(Solicitacao.usuario_id.in_(uvis_ids))

    return query
