import os
import platform
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from flask_login import current_user
from sqlalchemy import func, text

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario, UsuarioPresenca, WatchdogDeployEvent


PRESENCE_ONLINE_WINDOW = timedelta(minutes=5)
PRESENCE_AWAY_WINDOW = timedelta(minutes=30)
UTC_TZ = ZoneInfo("UTC")
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _check_item(name, status, detail, severity="success"):
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "severity": severity,
    }


def _database_check():
    try:
        db.session.execute(text("SELECT 1"))
        return _check_item("Banco de dados", "Operacional", "Conexão respondendo normalmente.")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Falha no diagnóstico do banco de dados.")
        return _check_item("Banco de dados", "Falha", str(exc)[:180], "danger")


def _writable_directory_check(name, path):
    exists = os.path.isdir(path)
    writable = exists and os.access(path, os.W_OK)
    if writable:
        return _check_item(name, "Gravável", path)
    detail = f"{path} não existe." if not exists else f"{path} sem permissão de escrita."
    return _check_item(name, "Atenção", detail, "warning")


def _display_name(user):
    return (
        getattr(user, "nome_uvis", None)
        or getattr(user, "login", None)
        or "dev"
    )


def _greeting_for(hour):
    if 5 <= hour < 12:
        return "Bom dia"
    if 12 <= hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _current_user_activity(since_24h, since_7d):
    user_id = getattr(current_user, "id", None)
    if not user_id:
        return {
            "actions_24h": 0,
            "actions_7d": 0,
            "last_event": None,
        }

    base_query = AuditoriaUsuario.query.filter(AuditoriaUsuario.usuario_id == user_id)
    return {
        "actions_24h": base_query.filter(AuditoriaUsuario.criado_em >= since_24h).count(),
        "actions_7d": base_query.filter(AuditoriaUsuario.criado_em >= since_7d).count(),
        "last_event": base_query.order_by(AuditoriaUsuario.criado_em.desc()).first(),
    }


def _serialize_datetime(value):
    if not value:
        return None
    return value.isoformat()


def _format_brazil_datetime(value):
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)
    return value.astimezone(BRAZIL_TZ).strftime("%d/%m/%Y %H:%M")


def _serialize_error_log(log):
    return {
        "id": log.id,
        "created_at": _serialize_datetime(log.criado_em),
        "status_code": log.status_code,
        "user_name": log.usuario_nome,
        "user_login": log.usuario_login,
        "user_type": log.tipo_usuario,
        "method": log.metodo,
        "event_type": log.tipo_evento,
        "endpoint": log.endpoint,
        "path": log.path,
        "query_string": log.query_string,
        "ip": log.ip,
        "user_agent": log.user_agent,
        "referrer": log.referrer,
    }


def _serialize_top_error(item):
    return {
        "endpoint": item.endpoint,
        "path": item.path,
        "total": item.total,
        "max_status": item.max_status,
    }


def _parse_iso_datetime(value):
    if not value:
        return None
    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _serialize_watchdog_event(event):
    if not event:
        return None
    return {
        "id": event.id,
        "event_id": event.event_id,
        "status": event.status,
        "source": event.source,
        "health_url": event.health_url,
        "failures": event.failures,
        "attempts": event.attempts,
        "started_at": _serialize_datetime(event.started_at),
        "recovered_at": _serialize_datetime(event.recovered_at),
        "created_at": _serialize_datetime(event.criado_em),
    }


def _presence_status(presence, now):
    logged_out = (
        presence.logout_em
        and (not presence.login_em or presence.logout_em >= presence.login_em)
        and presence.logout_em >= (presence.ultimo_acesso_em - timedelta(seconds=1))
    )
    if logged_out:
        return {
            "key": "offline",
            "label": "Offline",
            "severity": "secondary",
        }

    if presence.ultimo_acesso_em >= now - PRESENCE_ONLINE_WINDOW:
        return {
            "key": "online",
            "label": "Online",
            "severity": "success",
        }
    if presence.ultimo_acesso_em >= now - PRESENCE_AWAY_WINDOW:
        return {
            "key": "away",
            "label": "Ausente",
            "severity": "warning",
        }
    return {
        "key": "offline",
        "label": "Offline",
        "severity": "secondary",
    }


def _serialize_presence(presence, now):
    user = presence.usuario
    status = _presence_status(presence, now)
    return {
        "user_id": presence.usuario_id,
        "name": _display_name(user),
        "login": getattr(user, "login", None),
        "type": getattr(user, "tipo_usuario", None),
        "region": getattr(user, "regiao", None),
        "prefeitura": getattr(getattr(user, "prefeitura", None), "nome", None),
        "status": status["key"],
        "status_label": status["label"],
        "status_severity": status["severity"],
        "first_seen_at": _serialize_datetime(presence.primeiro_acesso_em),
        "last_seen_at": _serialize_datetime(presence.ultimo_acesso_em),
        "last_seen_label": _format_brazil_datetime(presence.ultimo_acesso_em),
        "login_at": _serialize_datetime(presence.login_em),
        "login_label": _format_brazil_datetime(presence.login_em),
        "logout_at": _serialize_datetime(presence.logout_em),
        "logout_label": _format_brazil_datetime(presence.logout_em),
        "method": presence.ultimo_metodo,
        "endpoint": presence.ultimo_endpoint,
        "path": presence.ultimo_path,
        "query_string": presence.ultimo_query_string,
        "ip": presence.ip,
        "user_agent": presence.user_agent,
        "referrer": presence.referrer,
    }


def _user_presence_summary(now):
    presences = (
        UsuarioPresenca.query
        .order_by(UsuarioPresenca.ultimo_acesso_em.desc(), UsuarioPresenca.id.desc())
        .limit(40)
        .all()
    )
    users = [_serialize_presence(presence, now) for presence in presences]
    online_count = sum(1 for item in users if item["status"] == "online")
    away_count = sum(1 for item in users if item["status"] == "away")
    offline_count = sum(1 for item in users if item["status"] == "offline")
    return {
        "users": users,
        "online_count": online_count,
        "away_count": away_count,
        "offline_count": offline_count,
        "tracked_count": len(users),
    }


def _watchdog_deploy_metrics(since_24h, since_7d):
    base_query = WatchdogDeployEvent.query
    last_event = base_query.order_by(WatchdogDeployEvent.criado_em.desc()).first()
    return {
        "total": base_query.count(),
        "last_24h": base_query.filter(WatchdogDeployEvent.criado_em >= since_24h).count(),
        "last_7d": base_query.filter(WatchdogDeployEvent.criado_em >= since_7d).count(),
        "last_event": last_event,
    }


def record_watchdog_deploy_event(payload):
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        return None, "event_id ausente."

    existing = WatchdogDeployEvent.query.filter_by(event_id=event_id).first()
    if existing:
        return existing, None

    event = WatchdogDeployEvent(
        event_id=event_id[:64],
        status=(str(payload.get("status") or "redeploy_triggered").strip() or "redeploy_triggered")[:30],
        source=(str(payload.get("source") or "github-actions").strip() or None),
        health_url=(str(payload.get("health_url") or "").strip() or None),
        failures=max(0, int(payload.get("failures") or 0)),
        attempts=max(0, int(payload.get("attempts") or 0)),
        started_at=_parse_iso_datetime(payload.get("started_at")),
        recovered_at=_parse_iso_datetime(payload.get("recovered_at")),
    )
    db.session.add(event)
    db.session.commit()
    return event, None


def _failure_timeline(since_24h):
    logs = (
        AuditoriaUsuario.query.with_entities(AuditoriaUsuario.criado_em)
        .filter(
            AuditoriaUsuario.criado_em >= since_24h,
            AuditoriaUsuario.status_code >= 400,
        )
        .all()
    )
    totals_by_hour = {}
    for log in logs:
        created_at = log.criado_em
        if not created_at:
            continue
        totals_by_hour[created_at.hour] = totals_by_hour.get(created_at.hour, 0) + 1

    current_hour = datetime.utcnow().hour

    timeline = []
    for offset in range(23, -1, -1):
        hour = (current_hour - offset) % 24
        timeline.append({
            "hour": f"{hour:02d}:00",
            "total": totals_by_hour.get(hour, 0),
        })
    return timeline


def _diagnostic_snapshot(context):
    metrics = context["metrics"]
    runtime = context["runtime"]
    maps_status = "configurado" if context["maps_enabled"] else "ausente"
    return "\n".join([
        f"Snapshot dev - {context['generated_at'].strftime('%d/%m/%Y %H:%M:%S')}",
        f"Dev: {context['dev_profile']['name']} ({context['dev_profile']['type'] or '-'})",
        f"Ações 24h: {metrics['audited_24h']} | Erros 24h: {metrics['errors_24h']} ({metrics['error_rate']}%)",
        f"Erros 5xx/7d: {metrics['server_errors_7d']} | Usuários ativos/24h: {metrics['active_users_24h']}",
        f"Redeploys watchdog: {metrics['watchdog_deploys_7d']}/7d | {metrics['watchdog_deploys_24h']}/24h | {metrics['watchdog_deploys_total']} total",
        f"Checks OK: {metrics['healthy_checks']}/{metrics['total_checks']} | Google Maps: {maps_status}",
        f"Runtime: Python {runtime['python']} | Banco {runtime['database']} | Debug {'ativo' if runtime['debug'] else 'off'}",
        f"Plataforma: {runtime['platform']}",
    ])


def _base_dev_dashboard_context():
    now = datetime.utcnow()
    generated_at = datetime.now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    total_24h = AuditoriaUsuario.query.filter(AuditoriaUsuario.criado_em >= since_24h).count()
    errors_24h = AuditoriaUsuario.query.filter(
        AuditoriaUsuario.criado_em >= since_24h,
        AuditoriaUsuario.status_code >= 400,
    ).count()
    server_errors_7d = AuditoriaUsuario.query.filter(
        AuditoriaUsuario.criado_em >= since_7d,
        AuditoriaUsuario.status_code >= 500,
    ).count()

    top_error_routes = (
        db.session.query(
            AuditoriaUsuario.endpoint,
            AuditoriaUsuario.path,
            func.count(AuditoriaUsuario.id).label("total"),
            func.max(AuditoriaUsuario.status_code).label("max_status"),
        )
        .filter(
            AuditoriaUsuario.criado_em >= since_7d,
            AuditoriaUsuario.status_code >= 400,
        )
        .group_by(AuditoriaUsuario.endpoint, AuditoriaUsuario.path)
        .order_by(func.count(AuditoriaUsuario.id).desc())
        .limit(8)
        .all()
    )

    recent_errors = (
        AuditoriaUsuario.query
        .filter(AuditoriaUsuario.status_code >= 400)
        .order_by(AuditoriaUsuario.criado_em.desc())
        .limit(10)
        .all()
    )

    secret_key = current_app.config.get("SECRET_KEY") or ""
    maps_key = (
        current_app.config.get("Maps_KEY_FRONT")
        or current_app.config.get("KEY_API_GOOGLE_MAPS")
    )
    dropbox_ready = all(
        current_app.config.get(key)
        for key in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
    )

    checks = [
        _database_check(),
        _check_item(
            "Chave da sessão",
            "Configurada" if secret_key and not secret_key.startswith("dev-") else "Insegura",
            "SECRET_KEY persistente configurada."
            if secret_key and not secret_key.startswith("dev-")
            else "A aplicação está usando uma chave temporária ou de desenvolvimento.",
            "success" if secret_key and not secret_key.startswith("dev-") else "danger",
        ),
        _check_item(
            "Google Maps",
            "Configurado" if maps_key else "Ausente",
            "Chave disponível para mapas e geocodificação."
            if maps_key
            else "Recursos de mapa podem falhar sem KEY_API_GOOGLE_MAPS.",
            "success" if maps_key else "warning",
        ),
        _check_item(
            "Dropbox / backup",
            "Configurado" if dropbox_ready else "Incompleto",
            "Credenciais de backup presentes."
            if dropbox_ready
            else "Uma ou mais credenciais do Dropbox não estão configuradas.",
            "success" if dropbox_ready else "warning",
        ),
        _check_item(
            "Modo debug",
            "Ativo" if current_app.debug else "Desativado",
            "Não use o modo debug em produção." if current_app.debug else "Configuração adequada para produção.",
            "warning" if current_app.debug else "success",
        ),
        _writable_directory_check("Diretório de uploads", os.path.join(current_app.root_path, "static", "uploads")),
        _writable_directory_check("Diretório da instância", current_app.instance_path),
    ]

    error_rate = round((errors_24h / total_24h) * 100, 1) if total_24h else 0
    dev_count = Usuario.query.filter_by(tipo_usuario="dev").count()
    route_count = len(list(current_app.url_map.iter_rules()))
    active_users_24h = (
        db.session.query(func.count(func.distinct(AuditoriaUsuario.usuario_id)))
        .filter(
            AuditoriaUsuario.criado_em >= since_24h,
            AuditoriaUsuario.usuario_id.isnot(None),
        )
        .scalar()
        or 0
    )
    healthy_checks = sum(1 for item in checks if item["severity"] == "success")
    current_user_activity = _current_user_activity(since_24h, since_7d)
    watchdog_metrics = _watchdog_deploy_metrics(since_24h, since_7d)
    presence_summary = _user_presence_summary(now)

    alerts = []
    if server_errors_7d:
        alerts.append({
            "severity": "danger",
            "title": "Erros 5xx detectados",
            "detail": f"{server_errors_7d} resposta(s) 5xx registrada(s) nos últimos 7 dias.",
        })
    if error_rate >= 10:
        alerts.append({
            "severity": "warning",
            "title": "Taxa de falha elevada",
            "detail": f"{error_rate}% das ações auditadas nas últimas 24 horas retornaram erro.",
        })
    alerts.extend(
        {
            "severity": item["severity"],
            "title": item["name"],
            "detail": item["detail"],
        }
        for item in checks
        if item["severity"] in {"warning", "danger"}
    )

    return {
        "generated_at": generated_at,
        "checks": checks,
        "alerts": alerts,
        "recent_errors": recent_errors,
        "top_error_routes": top_error_routes,
        "maps_key": maps_key or "",
        "maps_enabled": bool(maps_key),
        "dev_profile": {
            "name": _display_name(current_user),
            "login": getattr(current_user, "login", None),
            "type": getattr(current_user, "tipo_usuario", None),
            "region": getattr(current_user, "regiao", None),
            "city_hint": "São Paulo, SP",
            "greeting": _greeting_for(generated_at.hour),
            "actions_24h": current_user_activity["actions_24h"],
            "actions_7d": current_user_activity["actions_7d"],
            "last_event": current_user_activity["last_event"],
        },
        "local_context": {
            "default_location": {
                "lat": -23.55052,
                "lng": -46.63331,
                "label": "São Paulo, SP",
            },
            "weather_provider": "Open-Meteo",
        },
        "metrics": {
            "audited_24h": total_24h,
            "errors_24h": errors_24h,
            "error_rate": error_rate,
            "server_errors_7d": server_errors_7d,
            "route_count": route_count,
            "dev_count": dev_count,
            "active_users_24h": active_users_24h,
            "online_users": presence_summary["online_count"],
            "healthy_checks": healthy_checks,
            "total_checks": len(checks),
            "watchdog_deploys_total": watchdog_metrics["total"],
            "watchdog_deploys_24h": watchdog_metrics["last_24h"],
            "watchdog_deploys_7d": watchdog_metrics["last_7d"],
        },
        "watchdog": {
            "deploys_total": watchdog_metrics["total"],
            "deploys_24h": watchdog_metrics["last_24h"],
            "deploys_7d": watchdog_metrics["last_7d"],
            "last_event": watchdog_metrics["last_event"],
        },
        "presence": presence_summary,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": db.engine.dialect.name,
            "debug": current_app.debug,
        },
        "failure_timeline": _failure_timeline(since_24h),
    }


def build_dev_dashboard_context():
    context = _base_dev_dashboard_context()
    context["diagnostic_snapshot"] = _diagnostic_snapshot(context)
    return context


def build_dev_dashboard_payload():
    context = build_dev_dashboard_context()
    return {
        "generated_at": _serialize_datetime(context["generated_at"]),
        "checks": context["checks"],
        "alerts": context["alerts"],
        "metrics": context["metrics"],
        "watchdog": {
            **context["watchdog"],
            "last_event": _serialize_watchdog_event(context["watchdog"]["last_event"]),
        },
        "presence": context["presence"],
        "runtime": context["runtime"],
        "dev_profile": {
            **context["dev_profile"],
            "last_event": _serialize_error_log(context["dev_profile"]["last_event"])
            if context["dev_profile"]["last_event"]
            else None,
        },
        "recent_errors": [_serialize_error_log(log) for log in context["recent_errors"]],
        "top_error_routes": [_serialize_top_error(item) for item in context["top_error_routes"]],
        "failure_timeline": context["failure_timeline"],
        "diagnostic_snapshot": context["diagnostic_snapshot"],
    }


def get_dev_error_detail(log_id):
    log = AuditoriaUsuario.query.get(log_id)
    if not log or log.status_code < 400:
        return None
    return _serialize_error_log(log)


def run_manual_check(slug):
    checks_by_slug = {
        "database": _database_check,
        "uploads": lambda: _writable_directory_check(
            "Diretório de uploads",
            os.path.join(current_app.root_path, "static", "uploads"),
        ),
        "instance": lambda: _writable_directory_check("Diretório da instância", current_app.instance_path),
        "maps": lambda: _check_item(
            "Google Maps",
            "Configurado"
            if (current_app.config.get("Maps_KEY_FRONT") or current_app.config.get("KEY_API_GOOGLE_MAPS"))
            else "Ausente",
            "Chave disponível para mapas e geocodificação."
            if (current_app.config.get("Maps_KEY_FRONT") or current_app.config.get("KEY_API_GOOGLE_MAPS"))
            else "Recursos de mapa podem falhar sem KEY_API_GOOGLE_MAPS.",
            "success"
            if (current_app.config.get("Maps_KEY_FRONT") or current_app.config.get("KEY_API_GOOGLE_MAPS"))
            else "warning",
        ),
        "backup": lambda: _check_item(
            "Dropbox / backup",
            "Configurado"
            if all(
                current_app.config.get(key)
                for key in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
            )
            else "Incompleto",
            "Credenciais de backup presentes."
            if all(
                current_app.config.get(key)
                for key in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
            )
            else "Uma ou mais credenciais do Dropbox não estão configuradas.",
            "success"
            if all(
                current_app.config.get(key)
                for key in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
            )
            else "warning",
        ),
    }
    check = checks_by_slug.get(slug)
    if not check:
        return None
    return check()
