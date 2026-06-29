import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from flask_login import current_user
from flask_talisman import Talisman
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from whitenoise import WhiteNoise

from app.extensions import db, login_manager, migrate


UTC_TZ = ZoneInfo("UTC")
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


AUDIT_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

AUDIT_IGNORED_KEYWORDS = (
    "login",
    "logout",
    "chatbot",
    "api_cep",
    "api_geocode",
    "heatmap",
    "backup_status",
)

AUDIT_ACTION_KEYWORDS = (
    "acesso-operacional",
    "acesso_operacional",
    "abrir",
    "adicionar",
    "alternar",
    "atribuir",
    "atualizar",
    "cadastro",
    "cadastrar",
    "cancelamento",
    "cancelar",
    "checklist",
    "concluir",
    "configuracoes",
    "credenciais",
    "criar",
    "deletar",
    "delete",
    "dosagem",
    "editar",
    "encerrar",
    "excluir",
    "fechar",
    "formulario",
    "importar",
    "limpar",
    "manutencao",
    "mapeamento",
    "nova",
    "novo",
    "receber",
    "registrar",
    "remover",
    "reset_senha",
    "salvar",
    "template",
    "update",
)


def _resolve_request_ip():
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip

    return request.remote_addr or None


def _utcnow_naive():
    return datetime.now(UTC_TZ).replace(tzinfo=None)


def _to_brazil_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)

    return value.astimezone(BRAZIL_TZ)


def _should_audit_request():
    endpoint = (request.endpoint or "").strip().lower()
    path = (request.path or "").strip().lower()
    haystack = f"{endpoint} {path}"

    if path.startswith("/static/") or endpoint.startswith("static"):
        return False

    if any(keyword in haystack for keyword in AUDIT_IGNORED_KEYWORDS):
        return False

    if request.method not in AUDIT_MUTATION_METHODS:
        return False

    return any(keyword in haystack for keyword in AUDIT_ACTION_KEYWORDS)


def _resolve_audit_event_type(endpoint, path):
    haystack = f"{(endpoint or '').lower()} {(path or '').lower()}"

    if "cancelar" in haystack or "cancelamento" in haystack:
        return "CANCELAMENTO"
    if any(keyword in haystack for keyword in ("excluir", "delete", "deletar", "remover")):
        return "EXCLUSAO"
    if any(keyword in haystack for keyword in ("concluir", "encerrar", "fechar")):
        return "CONCLUSAO"
    if "dosagem" in haystack:
        return "DOSAGEM"
    if "formulario" in haystack or "checklist" in haystack:
        return "FORMULARIO"
    if any(keyword in haystack for keyword in ("credenciais", "reset_senha", "acesso-operacional", "acesso_operacional")):
        return "CREDENCIAIS"
    if any(keyword in haystack for keyword in ("cadastrar", "cadastro", "novo", "nova", "criar", "importar", "registrar", "abrir")):
        return "CRIACAO"
    if any(keyword in haystack for keyword in ("editar", "update", "atualizar", "salvar", "atribuir", "alternar", "receber", "limpar", "manutencao", "mapeamento", "configuracoes", "template")):
        return "EDICAO"

    return "ACAO"


def create_app():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    dotenv_path = os.path.join(base_dir, ".env")
    load_dotenv(dotenv_path)

    app = Flask(__name__)

    from config import Config

    app.config.from_object(Config)
    app.wsgi_app = WhiteNoise(app.wsgi_app, root="app/static/")

    db.init_app(app)
    migrate.init_app(app, db)

    if app.debug:
        Talisman(app, content_security_policy=None, force_https=False)
    else:
        Talisman(app, content_security_policy=None)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import AuditoriaUsuario, Usuario
    from app.shared.presence import record_user_presence

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "status": "ok",
            "service": "ija-system",
        })

    @app.get("/healthz/full")
    def healthz_full():
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            app.logger.exception("Health check completo falhou no banco de dados.")
            return jsonify({
                "status": "error",
                "service": "ija-system",
                "checks": {
                    "database": "error",
                },
            }), 503

        return jsonify({
            "status": "ok",
            "service": "ija-system",
            "checks": {
                "database": "ok",
            },
        })

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return Usuario.query.get(int(user_id))
        except SQLAlchemyError:
            app.logger.exception("Falha ao carregar usuario autenticado (banco indisponivel).")
            return None

    @app.before_request
    def capture_audit_user():
        if not getattr(current_user, "is_authenticated", False):
            return

        record_user_presence(current_user)

        g.audit_user_id = getattr(current_user, "id", None)
        g.audit_user_nome = (
            getattr(current_user, "nome_uvis", None)
            or getattr(current_user, "login", None)
            or "Usuario sem nome"
        )
        g.audit_user_login = getattr(current_user, "login", None)
        g.audit_tipo_usuario = getattr(current_user, "tipo_usuario", None)

    @app.after_request
    def register_user_audit(response):
        endpoint = (request.endpoint or "").strip()

        if not _should_audit_request():
            return response

        user_id = getattr(g, "audit_user_id", None)
        user_name = getattr(g, "audit_user_nome", None)
        user_login = getattr(g, "audit_user_login", None)
        user_type = getattr(g, "audit_tipo_usuario", None)

        if not user_name and getattr(current_user, "is_authenticated", False):
            user_id = getattr(current_user, "id", None)
            user_name = (
                getattr(current_user, "nome_uvis", None)
                or getattr(current_user, "login", None)
                or "Usuario sem nome"
            )
            user_login = getattr(current_user, "login", None)
            user_type = getattr(current_user, "tipo_usuario", None)

        if not user_name:
            return response

        query_string = request.query_string.decode("utf-8", errors="ignore").strip() or None
        user_agent = (request.headers.get("User-Agent") or "").strip() or None
        referrer = (request.referrer or "").strip() or None
        tipo_evento = _resolve_audit_event_type(endpoint, request.path)

        try:
            with db.engine.begin() as conn:
                conn.execute(
                    AuditoriaUsuario.__table__.insert().values(
                        usuario_id=user_id,
                        usuario_nome=(user_name or "Usuario sem nome")[:100],
                        usuario_login=user_login or None,
                        tipo_usuario=user_type or None,
                        metodo=request.method,
                        tipo_evento=tipo_evento,
                        endpoint=endpoint or None,
                        path=(request.path or "/")[:255],
                        query_string=query_string,
                        status_code=int(response.status_code or 0),
                        ip=_resolve_request_ip(),
                        user_agent=user_agent,
                        referrer=referrer[:255] if referrer else None,
                        criado_em=_utcnow_naive(),
                    )
                )
        except Exception:
            app.logger.exception("Erro ao registrar auditoria de usuario.")

        return response

    @app.context_processor
    def inject_google_maps_key():
        return dict(
            google_maps_key=(
                app.config.get("Maps_KEY_FRONT")
                or app.config.get("KEY_API_GOOGLE_MAPS")
                or os.getenv("KEY_API_GOOGLE_MAPS")
                or ""
            )
        )

    @app.context_processor
    def inject_global_vars():
        tema = request.cookies.get("theme", "light")
        return dict(
            tema_escolhido=tema,
            brazil_datetime=_to_brazil_datetime,
        )

    @app.errorhandler(404)
    def erro_404(e):
        if request.path.startswith("/api/") or "/api/" in request.path or request.is_json:
            return jsonify({
                "success": False,
                "error": "O recurso solicitado nao foi encontrado.",
                "code": 404,
            }), 404

        return render_template(
            "erro.html",
            codigo=404,
            titulo="Pagina nao encontrada",
            mensagem="A pagina que voce tentou acessar nao existe.",
        ), 404

    @app.errorhandler(500)
    def erro_500(e):
        app.logger.exception("Erro interno nao tratado.")
        if request.path.startswith("/api/") or "/api/" in request.path or request.is_json:
            return jsonify({
                "success": False,
                "error": "Ocorreu um erro no servidor. Tente novamente em instantes.",
                "code": 500,
            }), 500

        return render_template(
            "erro.html",
            codigo=500,
            titulo="Erro interno do servidor",
            mensagem="Ocorreu um erro inesperado.",
        ), 500

    from app.modules.auth import bp as auth_bp
    from app.routes import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
