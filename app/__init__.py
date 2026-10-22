import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from flask_login import current_user
from flask_talisman import Talisman
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from whitenoise import WhiteNoise

from app.extensions import db, login_manager, migrate


UTC_TZ = ZoneInfo("UTC")
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _to_brazil_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)

    return value.astimezone(BRAZIL_TZ)


def create_app():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    dotenv_path = os.path.join(base_dir, ".env")
    load_dotenv(dotenv_path)

    app = Flask(__name__)

    from config import Config

    app.config.from_object(Config)
    from app.modules.ortomosaicos.storage import register_storage
    register_storage(app)
    from app.shared.private_uploads import PrivateUploadsMiddleware
    app.wsgi_app = PrivateUploadsMiddleware(WhiteNoise(app.wsgi_app, root="app/static/"))

    if app.config.get("CSS_BUNDLE_AUTO_BUILD"):
        from scripts.build_css_bundle import build_css_bundle_if_stale

        @app.before_request
        def refresh_css_bundle():
            build_css_bundle_if_stale()

    db.init_app(app)
    migrate.init_app(app, db)

    if app.debug:
        Talisman(app, content_security_policy=None, force_https=False)
    else:
        Talisman(app, content_security_policy=None)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.modules.auditoria.recorder import register_audit

    register_audit(app)

    from app.shared.file_recovery import register_file_recovery
    register_file_recovery(app)

    from app.shared.password_expiration import register_password_expiration

    register_password_expiration(app)

    from app.shared.session_security import register_session_security

    register_session_security(app)

    from app.shared.csrf_security import register_csrf_security

    register_csrf_security(app)

    from app.models import Usuario
    from app.shared.presence import record_user_presence

    @app.get("/healthz")
    def healthz():
        return Response("ok\n", mimetype="text/plain")

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
    def update_user_presence():
        if request.blueprint == "session_security":
            return
        if not getattr(current_user, "is_authenticated", False):
            return

        record_user_presence(current_user)

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
    def inject_style_bundle_version():
        bundle_path = os.path.join(app.static_folder, "css", "style.bundle.css")
        try:
            version = os.stat(bundle_path).st_mtime_ns
        except OSError:
            version = "missing"
        return {"style_bundle_version": version}

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

    from app.shared.edit_control import register_edit_control

    register_edit_control(app)

    return app
