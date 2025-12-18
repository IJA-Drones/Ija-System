from flask import Flask, render_template, request # Adicione request aqui
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager # Certifique-se de importar o LoginManager

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'chave-secreta'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sgsv.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # Inicialize o LoginManager se ainda não estiver (Essencial para o current_user)
    # ... dentro da função create_app()

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'bp.login' # Nome da sua rota de login

    @login_manager.user_loader
    def load_user(user_id):

        from app.models import Usuario # Verifique se o nome do seu modelo é Usuario ou User
        return Usuario.query.get(int(user_id))

    # ... depois vem o seu context_processor e errorhandlers
    # --------------------------------------------------------------------
    # CONTEXT PROCESSOR: Resolve o Dark Mode (Cookie) e o current_user
    # --------------------------------------------------------------------
    @app.context_processor
    def inject_global_vars():
        # 1. Pega o tema do cookie (Resolve o Flash Branco)
        tema = request.cookies.get('theme', 'light')
        
        # 2. Proteção para o current_user nos templates de erro
        # Importamos aqui dentro para evitar importação cíclica
        from flask_login import current_user
        
        return dict(
            tema_escolhido=tema,
            current_user=current_user
        )

    # -----------------------------------
    # TRATAMENTO DE ERROS
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