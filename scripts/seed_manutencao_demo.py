"""Create a small, repeatable maintenance and inventory demo in a test tenant.

Run with IJA_ALLOW_TEST_SEED=1. Only the clearly marked demo records and the
dedicated demo.manutencao account are replaced on subsequent runs.
"""
from __future__ import annotations

import os
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.getenv("IJA_ALLOW_TEST_SEED") != "1":
    raise SystemExit("Seed bloqueado: defina IJA_ALLOW_TEST_SEED=1 para confirmar o banco de teste.")

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import (
    Baterias,
    Drones,
    Equipamentos,
    EstoquePeca,
    ManutencaoEquipamento,
    ManutencaoPecaUso,
    Prefeitura,
    Usuario,
)

APP = create_app()
PREFEITURA_SLUG = "prefeitura-teste"
FIXTURE = "DEMO-MANUTENCAO-V1"
DEMO_LOGIN = "fernando.almeida"
LEGACY_DEMO_LOGIN = "demo.manutencao"
DEMO_NAME = "Fernando Almeida"
SERIES = (f"{FIXTURE}-T10", f"{FIXTURE}-T25")


def run_seed():
    db_name = db.session.execute(text("select current_database()")).scalar()
    if (db_name or "").lower() != "neondb":
        raise RuntimeError("Seed bloqueado: o banco ativo não corresponde ao banco de teste esperado.")

    prefeitura = Prefeitura.query.filter_by(slug=PREFEITURA_SLUG).first()
    if not prefeitura or not prefeitura.ativa or "teste" not in prefeitura.nome.casefold():
        raise RuntimeError("Seed bloqueado: prefeitura de teste não encontrada ou inativa.")

    account = Usuario.query.filter_by(login=DEMO_LOGIN).first()
    legacy_demo = Usuario.query.filter_by(login=LEGACY_DEMO_LOGIN).first()
    if account and (account.tipo_usuario != "manutencao" or account.nome_uvis != DEMO_NAME):
        raise RuntimeError("Seed bloqueado: o login fernando.almeida já pertence a outro cadastro.")
    if account and legacy_demo:
        raise RuntimeError("Seed bloqueado: há conflito entre a conta de demonstração antiga e a atual.")
    if account is None:
        account = legacy_demo

    # Remove only prior rows carrying this fixture's exact identifiers.
    old_drones = Drones.query.filter(Drones.numero_serie.in_(SERIES)).all()
    old_ids = [row.id for row in old_drones]
    if old_ids:
        ManutencaoPecaUso.query.filter(ManutencaoPecaUso.drone_id.in_(old_ids)).delete(synchronize_session=False)
        ManutencaoEquipamento.query.filter(ManutencaoEquipamento.drone_id.in_(old_ids)).delete(synchronize_session=False)
        EstoquePeca.query.filter(EstoquePeca.observacoes == FIXTURE).delete(synchronize_session=False)
        for battery in Baterias.query.filter(Baterias.drone_id.in_(old_ids)).all():
            db.session.delete(battery)
        for row in old_drones:
            db.session.delete(row)
        db.session.flush()
    else:
        # Also clean fixture stock if a previous run stopped before the drones were committed.
        EstoquePeca.query.filter(EstoquePeca.observacoes == FIXTURE).delete(synchronize_session=False)
    # A prior version of this seed deleted the joined battery row in bulk and
    # could leave its base equipment row behind. Delete only this fixed serial.
    db.session.execute(
        Equipamentos.__table__.delete().where(
            Equipamentos.numero_serie == f"BAT-{FIXTURE}",
            Equipamentos.tipo_equipamento == "baterias",
        )
    )

    password_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%_-"),
    ]
    password_chars.extend(
        secrets.choice(string.ascii_letters + string.digits + "!@#$%_-") for _ in range(16)
    )
    secrets.SystemRandom().shuffle(password_chars)
    password = "".join(password_chars)
    if account is None:
        account = Usuario(
            nome_uvis=DEMO_NAME,
            login=DEMO_LOGIN,
            tipo_usuario="manutencao",
            prefeitura_id=prefeitura.id,
            trabalha_oceano_azul=True,
            trabalha_agro=False,
        )
        db.session.add(account)
    account.nome_uvis = DEMO_NAME
    account.login = DEMO_LOGIN
    account.prefeitura_id = prefeitura.id
    account.tipo_usuario = "manutencao"
    account.trabalha_oceano_azul = True
    account.set_senha(password)
    db.session.flush()

    drone_t10 = Drones(
        tipo_equipamento="drones", status="Em Manutenção", modelo="T10",
        renomacao=f"DEMO T10 {FIXTURE}", categoria="Drone de demonstração",
        numero_serie=SERIES[0], prefeitura_id=prefeitura.id,
        registro_anatel=f"ANATEL-{FIXTURE}-T10", registro_anac=f"ANAC-{FIXTURE}-T10", pmd_kg=30.0,
    )
    drone_t25 = Drones(
        tipo_equipamento="drones", status="Ativo", modelo="T25",
        renomacao=f"DEMO T25 {FIXTURE}", categoria="Drone de demonstração",
        numero_serie=SERIES[1], prefeitura_id=prefeitura.id,
        registro_anatel=f"ANATEL-{FIXTURE}-T25", registro_anac=f"ANAC-{FIXTURE}-T25", pmd_kg=30.0,
    )
    db.session.add_all([drone_t10, drone_t25])
    db.session.flush()

    battery = Baterias(
        tipo_equipamento="baterias", status="Ativo", modelo="Bateria T10 Demo",
        renomacao=f"DEMO BAT {FIXTURE}", categoria="Bateria de demonstração",
        numero_serie=f"BAT-{FIXTURE}", prefeitura_id=prefeitura.id, ciclo=12, drone_id=drone_t10.id,
    )
    part_t10 = EstoquePeca(
        prefeitura_id=prefeitura.id, modelo_peca="Hélice de demonstração T10",
        modelos_compativeis="T10", prateleira_local="Armário DEMO · Prateleira A1",
        quantidade=4, status="disponivel_manutencao", observacoes=FIXTURE,
    )
    part_t25 = EstoquePeca(
        prefeitura_id=prefeitura.id, modelo_peca="Kit motor de demonstração T25",
        modelos_compativeis="T25", prateleira_local="Armário DEMO · Gaveta B2",
        quantidade=2, status="disponivel_manutencao", observacoes=FIXTURE,
    )
    db.session.add_all([battery, part_t10, part_t25])
    db.session.flush()

    open_record = ManutencaoEquipamento(
        prefeitura_id=prefeitura.id, drone_id=drone_t10.id, aberta_por_id=account.id,
        status="aberta", observacoes=FIXTURE,
        responsavel_avaria="Técnico Demo", responsavel_manutencao="Técnica Demo",
        piloto_responsavel_avaria="Piloto Demo", avarias_identificadas="Vibração de teste; registro fictício.",
        drone_testado=False, observacoes_teste="Aguardando teste de bancada.",
    )
    closed_record = ManutencaoEquipamento(
        prefeitura_id=prefeitura.id, drone_id=drone_t25.id, aberta_por_id=account.id,
        encerrada_por_id=account.id, status="encerrada", observacoes=FIXTURE,
        responsavel_avaria="Técnico Demo", responsavel_manutencao="Técnica Demo",
        piloto_responsavel_avaria="Piloto Demo", imagens_ocorrido="DEMO: sem imagens reais.",
        avarias_identificadas="Peça substituída; registro fictício.", drone_testado=True,
        observacoes_teste="Teste de bancada aprovado (demonstração).",
    )
    db.session.add_all([open_record, closed_record])
    db.session.flush()
    db.session.add(ManutencaoPecaUso(
        prefeitura_id=prefeitura.id, manutencao_id=closed_record.id,
        drone_id=drone_t25.id, peca_id=part_t25.id, usuario_id=account.id,
        quantidade_usada=1, observacoes=FIXTURE,
    ))
    part_t25.quantidade = 1

    db.session.commit()
    if not account.check_senha(password):
        raise RuntimeError("Não foi possível validar a senha do usuário demo.")
    print(f"Prefeitura de demonstração: {prefeitura.nome} (id={prefeitura.id})")
    print("Registros: 2 drones, 1 bateria, 2 peças, 2 manutenções, 1 peça usada")
    print(f"Login de teste: {DEMO_LOGIN}")
    print(f"Senha temporária: {password}")


with APP.app_context():
    try:
        run_seed()
    except Exception:
        db.session.rollback()
        raise
