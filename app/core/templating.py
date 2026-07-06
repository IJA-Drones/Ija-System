from datetime import datetime

from flask import url_for
from flask_login import current_user
from werkzeug.routing import BuildError

from app import db
from app.models import Notificacao
from app.modules.agenda_notificacoes.service import can_view_all_notifications
from app.modules.feedback.service import build_support_notification_snapshot, can_access_feedback
from app.shared.access import is_admin_global_user, is_dev_user
from app.shared.formatters import format_currency_br, format_phone_br
from app.shared.solicitacao_focos import build_focus_catalog


def register_template_helpers(bp):
    @bp.context_processor
    def inject_globals():
        def safe_url_for(endpoint, fallback=None, **values):
            try:
                return url_for(endpoint, **values)
            except BuildError:
                if fallback is not None:
                    return fallback
                raise

        focus_catalog = build_focus_catalog()
        if current_user.is_authenticated:
            try:
                query = db.session.query(db.func.count(Notificacao.id)).filter(
                    Notificacao.lida_em.is_(None),
                    Notificacao.apagada_em.is_(None),
                )

                if not can_view_all_notifications(current_user):
                    query = query.filter(Notificacao.usuario_id == current_user.id)

                support_snapshot = (
                    build_support_notification_snapshot(current_user)
                    if can_access_feedback(current_user)
                    else {"count": 0, "latest_id": 0}
                )

                return {
                    "notif_count": query.scalar() or 0,
                    "support_nav_count": support_snapshot["count"],
                    "support_nav_latest_id": support_snapshot["latest_id"],
                    "safe_url_for": safe_url_for,
                    "is_admin_global_user": is_admin_global_user,
                    "is_dev_user": is_dev_user,
                    "solicitacao_focus_catalog": focus_catalog,
                    "solicitacao_filter_foco_opcoes": focus_catalog["filtro_foco_opcoes"],
                    "solicitacao_tipo_visita_opcoes": focus_catalog["tipo_visita_opcoes"],
                    "solicitacao_tipo_imovel_opcoes": focus_catalog["tipo_imovel_opcoes"],
                }
            except Exception:
                db.session.rollback()
                return {
                    "notif_count": 0,
                    "support_nav_count": 0,
                    "support_nav_latest_id": 0,
                    "safe_url_for": safe_url_for,
                    "is_admin_global_user": is_admin_global_user,
                    "is_dev_user": is_dev_user,
                    "solicitacao_focus_catalog": focus_catalog,
                    "solicitacao_filter_foco_opcoes": focus_catalog["filtro_foco_opcoes"],
                    "solicitacao_tipo_visita_opcoes": focus_catalog["tipo_visita_opcoes"],
                    "solicitacao_tipo_imovel_opcoes": focus_catalog["tipo_imovel_opcoes"],
                }

        return {
            "notif_count": 0,
            "support_nav_count": 0,
            "support_nav_latest_id": 0,
            "safe_url_for": safe_url_for,
            "is_admin_global_user": is_admin_global_user,
            "is_dev_user": is_dev_user,
            "solicitacao_focus_catalog": focus_catalog,
            "solicitacao_filter_foco_opcoes": focus_catalog["filtro_foco_opcoes"],
            "solicitacao_tipo_visita_opcoes": focus_catalog["tipo_visita_opcoes"],
            "solicitacao_tipo_imovel_opcoes": focus_catalog["tipo_imovel_opcoes"],
        }

    @bp.app_template_filter("datetimeformat")
    def datetimeformat(value, format="%d-%m-%y"):
        if value is None:
            return ""

        try:
            if isinstance(value, str):
                return datetime.strptime(value, "%Y-%m-%d").strftime(format)
            return value.strftime(format)
        except Exception:
            return value

    @bp.app_template_filter("currencybr")
    def currencybr(value):
        return format_currency_br(value)

    @bp.app_template_filter("phonebr")
    def phonebr(value):
        return format_phone_br(value)
