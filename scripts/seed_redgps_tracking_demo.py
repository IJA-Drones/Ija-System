"""Populate the Neon test database with a safe, repeatable RedGPS fixture.

The script deliberately refuses the production Render database.  It also
requires an explicit opt-in because it writes test records:

    DATABASE_URL="$NEON_TEST_DATABASE_URL" \
      .venv/bin/flask --app app:create_app db upgrade
    IJA_ALLOW_TEST_SEED=1 NEON_TEST_DATABASE_URL="$NEON_TEST_DATABASE_URL" \
      .venv/bin/python scripts/seed_redgps_tracking_demo.py

The fixture is marked with ``is_demo`` and a deterministic ``chave_fixture``
prefix. Running it again replaces only its own tracking rows and updates the
same four vehicles, so the command is idempotent.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


FIXTURE_PREFIX = "neon-rastreamento-demo:"
DEFAULT_PREFEITURA_SLUG = "neon-rastreamento-demo"


def _database_url() -> str:
    if os.getenv("IJA_ALLOW_TEST_SEED") != "1":
        raise SystemExit(
            "Seed bloqueado: defina IJA_ALLOW_TEST_SEED=1 para confirmar que o banco e de teste."
        )

    value = (os.getenv("NEON_TEST_DATABASE_URL") or os.getenv("DATABASE_URL_TEST") or "").strip()
    if not value:
        raise SystemExit("Informe NEON_TEST_DATABASE_URL (ou DATABASE_URL_TEST) com a URL do Neon de teste.")

    host = (urlparse(value).hostname or "").lower()
    if not host.endswith(".neon.tech"):
        raise SystemExit("Seed bloqueado: a URL precisa apontar para um host *.neon.tech.")
    return value


DATABASE_URL = _database_url()
os.environ["DATABASE_URL"] = DATABASE_URL

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Equipe,
    Prefeitura,
    RastreamentoAlerta,
    RastreamentoHistorico,
    RastreamentoPosicao,
    Veiculos,
)


def _prefeitura(prefeitura_id: int | None):
    if prefeitura_id is not None:
        row = db.session.get(Prefeitura, prefeitura_id)
        if row is None:
            raise SystemExit(f"Prefeitura {prefeitura_id} nao encontrada no banco de teste.")
        return row

    row = Prefeitura.query.filter_by(slug=DEFAULT_PREFEITURA_SLUG).first()
    if row is None:
        row = Prefeitura(nome="Ija System · Rastreamento Demo", slug=DEFAULT_PREFEITURA_SLUG, ativa=True)
        db.session.add(row)
        db.session.flush()
    return row


def _vehicle(prefeitura, equipe, plate, model, operation, fleet, km):
    row = Veiculos.query.filter_by(placa=plate).first()
    if row is None:
        row = Veiculos(
            placa=plate,
            modelo=model,
            renomacao=plate,
            operacao=operation,
            frota=fleet,
            km_atual=km,
            numero_serie=f"DEMO-REDGPS-{plate}",
            categoria="rastreamento-demo",
            status="Ativo",
        )
        db.session.add(row)
        db.session.flush()
    row.prefeitura_id = prefeitura.id
    row.equipe_id = equipe.id
    row.modelo = model
    row.renomacao = plate
    row.operacao = operation
    row.frota = fleet
    row.km_atual = km
    row.status = "Ativo"
    return row


def _clear_fixture_rows():
    for model in (RastreamentoAlerta, RastreamentoHistorico, RastreamentoPosicao):
        model.query.filter(model.chave_fixture.like(f"{FIXTURE_PREFIX}%")).delete(synchronize_session=False)


def seed(prefeitura_id: int | None = None):
    app = create_app()
    with app.app_context():
        prefeitura = _prefeitura(prefeitura_id)
        equipe = Equipe.query.filter_by(prefeitura_id=prefeitura.id, nome_equipe="Equipe Demo RedGPS").first()
        if equipe is None:
            equipe = Equipe(
                prefeitura_id=prefeitura.id,
                nome_equipe="Equipe Demo RedGPS",
                descricao="Equipe fictícia para validar o painel de rastreamento.",
                regiao="DEMO",
                ativa=True,
            )
            db.session.add(equipe)
            db.session.flush()

        vehicles = {
            "DEMO-01": _vehicle(prefeitura, equipe, "DEMO-01", "Fiorino Demo", "PMSP", "PROPRIA", 42500),
            "DEMO-02": _vehicle(prefeitura, equipe, "DEMO-02", "Master Demo", "PMSP", "ALUGADA", 18740),
            "DEMO-03": _vehicle(prefeitura, equipe, "DEMO-03", "Saveiro Demo", "AGRO", "PROPRIA", 63820),
            "DEMO-04": _vehicle(prefeitura, equipe, "DEMO-04", "Kangoo Demo", "PMSP", "PROPRIA", 9200),
        }
        db.session.flush()

        _clear_fixture_rows()
        now = datetime.now().replace(second=0, microsecond=0)
        route = [
            (-23.5858, -46.6637), (-23.5841, -46.6596), (-23.5815, -46.6550),
            (-23.5775, -46.6509), (-23.5723, -46.6470), (-23.5678, -46.6482),
            (-23.5634, -46.6544), (-23.5598, -46.6582), (-23.5562, -46.6624),
        ]
        speeds = [0, 18, 26, 31, 0, 24, 42, 36, 32]
        demo_rows = []
        for index, ((latitude, longitude), speed) in enumerate(zip(route, speeds), start=1):
            reported = now - timedelta(minutes=(len(route) - index) * 5 + 5)
            demo_rows.append(
                RastreamentoHistorico(
                    veiculo_id=vehicles["DEMO-01"].id,
                    prefeitura_id=prefeitura.id,
                    latitude=latitude,
                    longitude=longitude,
                    velocidade_kmh=speed,
                    ignicao=speed > 0,
                    hodometro_km=42500 + index * 2.3,
                    reportado_em=reported,
                    provedor="RedGPS",
                    is_demo=True,
                    chave_fixture=f"{FIXTURE_PREFIX}history:DEMO-01:{index}",
                )
            )
        db.session.add_all(demo_rows)

        positions = [
            ("DEMO-01", route[-1][0], route[-1][1], 32, True, 42518.4, "São Paulo · localização fictícia", now),
            ("DEMO-02", -23.5491, -46.6375, 0, False, 18742.8, "São Paulo · localização fictícia", now - timedelta(minutes=2)),
            ("DEMO-03", -23.5910, -46.6844, 0, None, 63837, "São Paulo · última localização fictícia", now - timedelta(hours=2)),
        ]
        for index, (plate, latitude, longitude, speed, ignition, odometer, address, reported) in enumerate(positions, start=1):
            db.session.add(
                RastreamentoPosicao(
                    veiculo_id=vehicles[plate].id,
                    prefeitura_id=prefeitura.id,
                    latitude=latitude,
                    longitude=longitude,
                    velocidade_kmh=speed,
                    ignicao=ignition,
                    hodometro_km=odometer,
                    endereco=address,
                    reportado_em=reported,
                    provedor="RedGPS",
                    is_demo=True,
                    chave_fixture=f"{FIXTURE_PREFIX}position:{plate}:{index}",
                )
            )

        alerts = [
            ("DEMO-01", "Entrada em área de interesse", "O veículo entrou na área de operação de exemplo.", "baixa", now - timedelta(minutes=25)),
            ("DEMO-01", "Parada identificada", "Parada ilustrativa durante o percurso selecionado.", "media", now - timedelta(minutes=15)),
            ("DEMO-03", "Comunicação atrasada", "A última posição está fora do intervalo esperado.", "alta", now - timedelta(hours=2)),
        ]
        for index, (plate, alert_type, message, severity, reported) in enumerate(alerts, start=1):
            db.session.add(
                RastreamentoAlerta(
                    veiculo_id=vehicles[plate].id,
                    prefeitura_id=prefeitura.id,
                    tipo=alert_type,
                    severidade=severity,
                    mensagem=message,
                    reportado_em=reported,
                    resolvido=False,
                    provedor="RedGPS",
                    is_demo=True,
                    chave_fixture=f"{FIXTURE_PREFIX}alert:{plate}:{index}",
                )
            )

        db.session.commit()
        print(f"Fixture RedGPS criada no Neon de teste: prefeitura={prefeitura.id}, veiculos=4, historico=9, alertas=3")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefeitura-id", type=int, help="Usa uma prefeitura já existente em vez de criar a prefeitura demo.")
    args = parser.parse_args()
    try:
        seed(args.prefeitura_id)
    except Exception:
        # Never leave a partially seeded transaction open when a constraint or
        # connectivity error occurs; the caller gets the original traceback.
        db.session.rollback()
        raise
