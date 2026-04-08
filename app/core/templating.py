from datetime import datetime

from flask_login import current_user

from app import db
from app.models import Notificacao
from app.shared.formatters import format_currency_br, format_phone_br


def register_template_helpers(bp):
    @bp.context_processor
    def inject_globals():
        if current_user.is_authenticated:
            try:
                query = db.session.query(db.func.count(Notificacao.id)).filter(
                    Notificacao.lida_em.is_(None),
                    Notificacao.apagada_em.is_(None),
                )

                if current_user.tipo_usuario not in ["admin", "operario", "visualizar"]:
                    query = query.filter(Notificacao.usuario_id == current_user.id)

                return {"notif_count": query.scalar() or 0}
            except Exception:
                db.session.rollback()
                return {"notif_count": 0}

        return {"notif_count": 0}

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
