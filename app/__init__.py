from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'chave-secreta'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sgsv.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # -----------------------------------
    # TRATAMENTO DE ERROS (1 HTML só)
    # -----------------------------------
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
            mensagem="Ocorreu um erro inesperado. Por favor, tente novamente."
        ), 500

    @app.errorhandler(Exception)
    def erro_generico(e):
        return render_template(
            "erro.html",
            codigo="Erro",
            titulo="Ocorreu um erro",
            mensagem=str(e)
        ), 500

    # Registrar rotas e modelos
    from app.routes import bp
    app.register_blueprint(bp)

    from app import models  

    return app