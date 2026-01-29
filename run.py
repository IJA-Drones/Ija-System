from app import create_app, db
from app.models import Usuario, Solicitacao, Pilotos, PilotoUvis

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


            # --- 1.6. GARANTE USUÁRIOS DE AUDITORIA (Visualizar e Covisa) ---
            # Criamos uma lista para facilitar a manutenção
            perfis_auditoria = [
                {"login": "visualizar", "nome": "AUDITORIA", "senha": "123", "regiao": "AUDITORIA"},
                {"login": "covisa", "nome": "COVISA", "senha": "123456", "regiao": "COVISA"}
            ]

            for p_auditoria in perfis_auditoria:
                user_aud = Usuario.query.filter_by(login=p_auditoria["login"]).first()
                if not user_aud:
                    print(f"--- Criando usuário {p_auditoria['login']}... ---")
                    user_aud = Usuario(
                        nome_uvis=p_auditoria["nome"], 
                        regiao=p_auditoria["regiao"], 
                        codigo_setor="99",
                        login=p_auditoria["login"],
                        tipo_usuario="visualizar" # Ambos herdam o mesmo perfil
                    )
                    user_aud.set_senha(p_auditoria["senha"])
                    db.session.add(user_aud)
                else:
                    user_aud.tipo_usuario = "visualizar"


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

            # --- 4. GARANTE PILOTO (NOVO) ---
            # 4.1) Garante cadastro do piloto na tabela Pilotos
            piloto = Pilotos.query.filter_by(nome_piloto="Piloto 01").first()
            if not piloto:
                print("--- Criando cadastro Piloto (Pilotos)... ---")
                piloto = Pilotos(
                    nome_piloto="Piloto 01",
                    regiao="OESTE",
                    telefone="11999999999"
                )
                db.session.add(piloto)
                db.session.flush()  # garante piloto.id sem precisar commit
            else:
                print(f"--- Piloto encontrado (ID: {piloto.id}) ---")

            # 4.2) Garante usuário de login do piloto (tabela usuarios)
            usuario_piloto = Usuario.query.filter_by(login='piloto').first()
            if not usuario_piloto:
                print("--- Criando usuário Piloto (login piloto)... ---")
                usuario_piloto = Usuario(
                    nome_uvis="Piloto 01",     # você usa nome_uvis como nome exibido
                    regiao="OESTE",
                    codigo_setor="P1",
                    login="piloto",
                    tipo_usuario="piloto",
                    piloto_id=piloto.id
                )
                usuario_piloto.set_senha("1234")
                db.session.add(usuario_piloto)
            else:
                # garante que está correto
                if usuario_piloto.tipo_usuario != 'piloto':
                    usuario_piloto.tipo_usuario = 'piloto'
                usuario_piloto.piloto_id = piloto.id
                print(f"--- Usuário Piloto encontrado (ID: {usuario_piloto.id}) ---")

            # 4.3) (Opcional, recomendado) vincula UVIS que esse piloto atende
            # aqui eu vou vincular as UVIS já criadas: lapa e teste
            # se você quiser, pode remover ou trocar
            def vincular_uvis(piloto_id, uvis_usuario_id):
                existe = PilotoUvis.query.filter_by(
                    piloto_id=piloto_id,
                    uvis_usuario_id=uvis_usuario_id
                ).first()
                if not existe:
                    db.session.add(PilotoUvis(
                        piloto_id=piloto_id,
                        uvis_usuario_id=uvis_usuario_id
                    ))

            # garante que lapa/teste existem no escopo (você cria acima)
            if lapa and lapa.id:
                vincular_uvis(piloto.id, lapa.id)

            print("--- Vínculos Piloto ↔ UVIS garantidos ---")



            db.session.commit()
            print(">>> Banco de dados verificado com sucesso!")


    except Exception as e:
        print(f"!!! ERRO FATAL NA VERIFICAÇÃO DO BANCO: {e}")
 
if __name__ == "__main__":

    verificar_banco()
    # Comente ou remova as linhas abaixo para o Render:
    app.run(debug=True, host='127.0.0.1', port=5000)

    app.run(host='0.0.0.0', port=5000, debug=True)
    
    # Adicione este print para você saber que ele terminou:
    print(">>> Banco de dados pronto! Passando o controle para o Gunicorn...")

    # Para Render, o Gunicorn iniciará o app automaticamente.