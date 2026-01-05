from app import create_app, db
from app.models import Usuario, Solicitacao
from datetime import datetime # Importação adicionada para usar em Solicitacao (se necessário)

app = create_app()

def verificar_banco():
    """
    Roda ao iniciar. 
    Cria e garante que todos os usuários de teste estão no banco.
    """
    print(">>> Iniciando verificação do banco de dados...")
    try:
        with app.app_context():
            db.create_all()
            
            # --- 1. GARANTE ADMIN ORIGINAL ---
            admin = Usuario.query.filter_by(login='admin').first()
            if not admin:
                print("--- Criando usuário Admin (original)... ---")
                admin = Usuario(
                    nome_uvis="Administrador Original", 
                    regiao="CENTRAL", 
                    codigo_setor="00",
                    login="admin",
                    tipo_usuario="admin"
                )
                admin.set_senha("admin123")
                db.session.add(admin)
            else:
                if admin.tipo_usuario != 'admin':
                    admin.tipo_usuario = 'admin'
                print(f"--- Usuário Admin (original) encontrado (ID: {admin.id}) ---")


            # --- 1.5. GARANTE OPERARIO ---
            # Este usuário tem permissão total de alteração, mas não de relatório.
            operario = Usuario.query.filter_by(login='operario').first()
            if not operario:
                print("--- Criando novo usuário Operario... ---")
                operario = Usuario(
                    nome_uvis="Usuário Operário", 
                    regiao="OPERACIONAL", 
                    codigo_setor="98",
                    login="operario",
                    tipo_usuario="operario"
                )
                operario.set_senha("operario123")
                db.session.add(operario)
            else:
                if operario.tipo_usuario != 'operario':
                    operario.tipo_usuario = 'operario' 
                print(f"--- Usuário Operario encontrado (ID: {operario.id}) ---")


            # --- 1.7. GARANTE VISUALIZAR (NOVO) ---
            visualizar = Usuario.query.filter_by(login='visualizar').first()
            if not visualizar:
                print("--- Criando novo usuário Visualizar (somente leitura)... ---")
                visualizar = Usuario(
                    nome_uvis="Usuário Somente Leitura", 
                    regiao="AUDITORIA", 
                    codigo_setor="99",
                    login="visualizar",
                    tipo_usuario="visualizar" # NOVO TIPO DE USUÁRIO
                )
                visualizar.set_senha("1234") # Senha solicitada
                db.session.add(visualizar)
            else:
                if visualizar.tipo_usuario != 'visualizar':
                    visualizar.tipo_usuario = 'visualizar' 
                print(f"--- Usuário Visualizar encontrado (ID: {visualizar.id}) ---")


            # --- 2. GARANTE LAPA ---
            lapa = Usuario.query.filter_by(login='lapa').first()
            if not lapa:
                print("--- Criando usuário UVIS Lapa... ---")
                lapa = Usuario(
                    nome_uvis="UVIS Lapa/Pinheiros", 
                    regiao="OESTE", 
                    codigo_setor="90",
                    login="lapa",
                    tipo_usuario="uvis"
                )
                lapa.set_senha("1234")
                db.session.add(lapa)
            else:
                print(f"--- Usuário Lapa encontrado (ID: {lapa.id}) ---")
            
            
            # --- 3. GARANTE NOVO USUÁRIO DE TESTE (teste) ---
            teste = Usuario.query.filter_by(login='teste').first()
            if not teste:
                print("--- Criando novo usuário de TESTE (teste)... ---")
                teste = Usuario(
                    nome_uvis="UVIS Teste QA", 
                    regiao="SUL", 
                    codigo_setor="10",
                    login="teste",
                    tipo_usuario="uvis"
                )
                teste.set_senha("1234")
                db.session.add(teste)
            else:
                print(f"--- Usuário Teste encontrado (ID: {teste.id}) ---")


            db.session.commit()
            print(">>> Banco de dados verificado com sucesso!")


    except Exception as e:
        print(f"!!! ERRO FATAL NA VERIFICAÇÃO DO BANCO: {e}")

#if __name__ == "__main__":
    #verificar_banco()
    # Comente ou remova as linhas abaixo para o Render:
    # print(">>> INICIANDO SERVIDOR FLASK...")
    #app.run(debug=True, port=5000) 

if __name__ == "__main__":

    verificar_banco()
    # Comente ou remova as linhas abaixo para o Render:
    app.run(debug=True, host='127.0.0.1', port=5000)
    
    # Adicione este print para você saber que ele terminou:
    print(">>> Banco de dados pronto! Passando o controle para o Gunicorn...")

    # Para Render, o Gunicorn iniciará o app automaticamente.