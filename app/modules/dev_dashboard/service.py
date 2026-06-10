import os
import platform
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func, text

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario


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


def build_dev_dashboard_context():
    now = datetime.utcnow()
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
        "generated_at": datetime.now(),
        "checks": checks,
        "alerts": alerts,
        "recent_errors": recent_errors,
        "top_error_routes": top_error_routes,
        "metrics": {
            "audited_24h": total_24h,
            "errors_24h": errors_24h,
            "error_rate": error_rate,
            "server_errors_7d": server_errors_7d,
            "route_count": route_count,
            "dev_count": dev_count,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": db.engine.dialect.name,
            "debug": current_app.debug,
        },
    }
