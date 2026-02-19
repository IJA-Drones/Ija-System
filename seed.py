import os
from app import create_app, db
from app.models import Usuario, EquipeUvis # Importe de acordo com a estrutura das suas pastas
from werkzeug.security import generate_password_hash

app = create_app()

def seed():
    with app.app_context():
        # 1. Garante que as tabelas existam no test.db
        print("🛠️ Criando tabelas no banco de dados...")
        db.create_all()

        # 2. Criar Usuário Admin
        # Nota: Seu modelo usa 'login' e 'senha_hash' em vez de username/password
        admin = Usuario.query.filter_by(login="admin").first()
        if not admin:
            admin = Usuario(
                login="admin",
                nome_uvis="Administrador Central",
                regiao="Sede",
                tipo_usuario="admin"
            )
            admin.set_senha("admin123") # Usa o método do seu model
            db.session.add(admin)
            print("✅ Admin criado: login: admin / senha: admin123")
        else:
            print("ℹ️ Admin já existe.")

        # 3. Criar uma UVIS de teste
        uvis_user = Usuario.query.filter_by(login="uvis_itajuba").first()
        if not uvis_user:
            uvis_user = Usuario(
                login="uvis_itajuba",
                nome_uvis="UVIS Itajubá Sul",
                regiao="Sul",
                codigo_setor="123",
                tipo_usuario="uvis"
            )
            uvis_user.set_senha("uvis123")
            db.session.add(uvis_user)
            db.session.flush() # Para gerar o ID e usar na equipe abaixo

            # 4. Adicionar Membros na Equipe desta UVIS (conforme seu modelo EquipeUvis)
            membro1 = EquipeUvis(
                uvis_usuario=uvis_user,
                nome_equipe="Equipe Alfa",
                ordem=1,
                nome="Pedro Cruz",
                funcao="Coordenador",
                contato="35 9999-9999"
            )
            db.session.add(membro1)
            print("✅ UVIS e Equipe criadas: login: uvis_itajuba / senha: uvis123")
        else:
            print("ℹ️ UVIS Itajubá já existe.")

        db.session.commit()
        print("\n🚀 IJA System: Banco de teste populado com sucesso!")

if __name__ == "__main__":
    seed()