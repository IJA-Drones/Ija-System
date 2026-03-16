import os

from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_talisman import Talisman
from whitenoise import WhiteNoise

from app.extensions import db, login_manager, migrate


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
    login_manager.login_view = "main.login"

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    @app.context_processor
    def inject_google_maps_key():
        return dict(google_maps_key=app.config.get("Maps_KEY_FRONT"))

    @app.context_processor
    def inject_global_vars():
        tema = request.cookies.get("theme", "light")
        return dict(tema_escolhido=tema)

    @app.errorhandler(404)
    def erro_404(e):
        return render_template(
            "erro.html",
            codigo=404,
            titulo="Pagina nao encontrada",
            mensagem="A pagina que voce tentou acessar nao existe.",
        ), 404

    @app.errorhandler(500)
    def erro_500(e):
        return render_template(
            "erro.html",
            codigo=500,
            titulo="Erro interno do servidor",
            mensagem="Ocorreu um erro inesperado.",
        ), 500

    from app.routes import bp

    app.register_blueprint(bp)

    return app
