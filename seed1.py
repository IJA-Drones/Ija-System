from app import create_app, db
from app.models import Equipe, Drones, Baterias
from datetime import date

app = create_app()

with app.app_context():
    # 1. Criar uma Equipe para teste
    equipe_alfa = Equipe(
        nome_equipe="Equipe Alfa - PMSP",
        regiao="NORTE",
        ativa=True
    )
    db.session.add(equipe_alfa)
    db.session.flush() 

    # 2. Criar um Drone (Removi o 'fabricante')
    drone1 = Drones(
        renomacao="PLOA 19",
        modelo="AGRAS T10",
        categoria="Pulverização dengue PMSP", # Usei categoria no lugar de fabricante
        numero_serie="4VNBL8Q001007K",
        registro_anatel="10889-21-07248",
        registro_anac="PP-085447956",
        pmd_kg=25.0,
        status="Ativo",
        equipe_id=equipe_alfa.id 
    )
    db.session.add(drone1)
    db.session.flush()

    # 3. Criar Baterias
    bat1 = Baterias(
        renomacao="BAT-01",
        modelo="T10 Intelligent Battery",
        numero_serie="3VJPK35CA000EU",
        ciclo=97,
        drone_id=drone1.id, 
        status="Ativo"
    )
    
    bat2 = Baterias(
        renomacao="BAT-02",
        modelo="T10 Intelligent Battery",
        numero_serie="3VJPK35CA000EX",
        ciclo=45,
        drone_id=drone1.id,
        status="Ativo"
    )

    db.session.add_all([bat1, bat2])
    
    try:
        db.session.commit()
        print("✅ Dados de teste inseridos com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao popular: {e}")