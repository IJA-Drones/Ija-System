from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os
from dotenv import load_dotenv
from whitenoise import WhiteNoise
from flask_talisman import Talisman

# Extensões (SEM init_app aqui)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# Carrega variáveis de ambiente
load_dotenv()

def create_app():
    app = Flask(__name__)

    # Static files (produção)
    app.wsgi_app = WhiteNoise(app.wsgi_app, root='app/static/')

    # Secret Key
    app.config['SECRET_KEY'] = os.getenv(
        'SECRET_KEY', 'chave-secreta-padrao-desenvolvimento'
    )

    # Banco de Dados
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql://", 1
            )
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sgsv.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicialização das extensões
    db.init_app(app)
    migrate.init_app(app, db)

    # Segurança HTTPS
    if app.debug:
        Talisman(app, content_security_policy=None, force_https=False)
    else:
        Talisman(app, content_security_policy=None)

    # Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Context Processor (APENAS o tema)
    @app.context_processor
    def inject_global_vars():
        tema = request.cookies.get('theme', 'light')
        return dict(tema_escolhido=tema)

    # Tratamento de erros
    @app.errorhandler(404)
    def erro_404(e):
        return render_template(
            "erro.html",
            codigo=404,
            titulo="Página não encontrada",
            mensagem="A página que você tentou acessar não existe."
        ), 404

    @app.errorhandler(500)
    def erro_500(e):
        return render_template(
            "erro.html",
            codigo=500,
            titulo="Erro interno do servidor",
            mensagem="Ocorreu um erro inesperado."
        ), 500

    # Blueprints
    from app.routes import bp
    app.register_blueprint(bp)

    return app
