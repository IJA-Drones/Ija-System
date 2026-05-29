from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_

from app.models import AuditoriaUsuario


UTC_TZ = ZoneInfo("UTC")
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def parse_date_filter(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_auditoria_filters(q, metodo, tipo_evento, status, data_inicio, data_fim):
    return {
        "q": (q or "").strip(),
        "metodo": (metodo or "").strip().upper(),
        "tipo_evento": (tipo_evento or "").strip().upper(),
        "status": (status or "").strip(),
        "data_inicio": (data_inicio or "").strip(),
        "data_fim": (data_fim or "").strip(),
    }


def build_auditoria_query(q="", metodo="", tipo_evento="", status="", data_inicio="", data_fim=""):
    query = AuditoriaUsuario.query

    if q:
        term = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(func.coalesce(AuditoriaUsuario.usuario_nome, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.usuario_login, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.tipo_usuario, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.tipo_evento, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.endpoint, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.path, "")).like(term),
                func.lower(func.coalesce(AuditoriaUsuario.ip, "")).like(term),
            )
        )

    if metodo:
        query = query.filter(AuditoriaUsuario.metodo == metodo)

    if tipo_evento:
        query = query.filter(AuditoriaUsuario.tipo_evento == tipo_evento)

    if status:
        try:
            query = query.filter(AuditoriaUsuario.status_code == int(status))
        except ValueError:
            pass

    inicio = parse_date_filter(data_inicio)
    if inicio:
        inicio_utc = (
            datetime.combine(inicio, time.min, tzinfo=BRAZIL_TZ)
            .astimezone(UTC_TZ)
            .replace(tzinfo=None)
        )
        query = query.filter(AuditoriaUsuario.criado_em >= inicio_utc)

    fim = parse_date_filter(data_fim)
    if fim:
        fim_utc = (
            datetime.combine(fim + timedelta(days=1), time.min, tzinfo=BRAZIL_TZ)
            .astimezone(UTC_TZ)
            .replace(tzinfo=None)
        )
        query = query.filter(
            AuditoriaUsuario.criado_em < fim_utc
        )

    return query.order_by(AuditoriaUsuario.criado_em.desc(), AuditoriaUsuario.id.desc())
