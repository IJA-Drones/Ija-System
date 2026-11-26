"""Maintenance timestamps are stored in UTC and displayed in São Paulo."""
from datetime import timezone
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo('America/Sao_Paulo')


def to_sao_paulo(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SAO_PAULO)


def maintenance_datetime(value):
    return to_sao_paulo(value).strftime('%d/%m/%Y %H:%M') if value else '—'
