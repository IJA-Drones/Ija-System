from datetime import datetime
from zoneinfo import ZoneInfo


BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def now_brazil_naive():
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)


def current_brazil_date():
    return now_brazil_naive().date()


def datetime_local_input_value(value):
    if not value:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(BRAZIL_TZ).replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M")
