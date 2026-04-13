from datetime import datetime

from flask_login import current_user

from app import db
from app.models import Notificacao
from app.shared.formatters import format_currency_br, format_phone_br
from app.shared.solicitacao_focos import build_focus_catalog


def register_template_helpers(bp):
    @bp.context_processor
    def inject_globals():
        focus_catalog = build_focus_catalog()
        if current_user.is_authenticated:
            try:
                query = db.session.query(db.func.count(Notificacao.id)).filter(
                    Notificacao.lida_em.is_(None),
                    Notificacao.apagada_em.is_(None),
                )

                if current_user.tipo_usuario not in ["admin", "operario", "visualizar"]:
                    query = query.filter(Notificacao.usuario_id == current_user.id)

                return {
                    "notif_count": query.scalar() or 0,
                    "solicitacao_focus_catalog": focus_catalog,
                    "solicitacao_filter_foco_opcoes": focus_catalog["filtro_foco_opcoes"],
                    "solicitacao_tipo_visita_opcoes": focus_catalog["tipo_visita_opcoes"],
                    "solicitacao_tipo_imovel_opcoes": focus_catalog["tipo_imovel_opcoes"],
                }
            except Exception:
                db.session.rollback()
                return {
                    "notif_count": 0,
                    "solicitacao_focus_catalog": focus_catalog,
                    "solicitacao_filter_foco_opcoes": focus_catalog["filtro_foco_opcoes"],
                    "solicitacao_tipo_visita_opcoes": focus_catalog["tipo_visita_opcoes"],
                    "solicitacao_tipo_imovel_opcoes": focus_catalog["tipo_imovel_opcoes"],
                }

        return {
            "notif_count": 0,
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
