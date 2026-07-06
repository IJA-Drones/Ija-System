import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import (
    DjiFlightKmlRoute,
    Drones,
    Equipe,
    OrdemServico,
    Pilotos,
    Solicitacao,
    Usuario,
)


DEMO_TAG = "DEMO-KML-OS"
DEMO_ROUTE_CODE = "DEMO-KML-OS-ROTA-001"


def ensure_kml_column():
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("ordens_servico")}
    if "dji_kml_route_id" not in columns:
        db.session.execute(text("ALTER TABLE ordens_servico ADD COLUMN dji_kml_route_id INTEGER"))
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_ordens_servico_dji_kml_route_id ON ordens_servico (dji_kml_route_id)")
        )
        db.session.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'fk_ordens_servico_dji_kml_route_id_dji_flight_kml_routes'
                    ) THEN
                        ALTER TABLE ordens_servico
                        ADD CONSTRAINT fk_ordens_servico_dji_kml_route_id_dji_flight_kml_routes
                        FOREIGN KEY (dji_kml_route_id) REFERENCES dji_flight_kml_routes(id);
                    END IF;
                END $$;
                """
            )
        )
        db.session.commit()


def first_or_create(model, defaults=None, **filters):
    row = model.query.filter_by(**filters).first()
    if row:
        return row
    row = model(**filters, **(defaults or {}))
    db.session.add(row)
    db.session.flush()
    return row


def ensure_demo_records():
    now = datetime.now()
    scheduled_date = date.today()
    route_time = datetime.combine(scheduled_date, time(9, 30))

    uvis = first_or_create(
        Usuario,
        login="demo_kml_uvis",
        defaults={
            "nome_uvis": "UVIS Demo KML",
            "senha_hash": "demo-seed-nao-usar-login",
            "tipo_usuario": "uvis",
            "regiao": "DEMO",
        },
    )

    piloto = first_or_create(
        Pilotos,
        nome_piloto="Piloto Demo KML",
        defaults={"regiao": "DEMO", "telefone": "(11) 90000-0000"},
    )

    equipe = first_or_create(
        Equipe,
        nome_equipe="Equipe Demo KML",
        defaults={"descricao": "Equipe criada para visualizar OS com KML.", "regiao": "DEMO", "ativa": True},
    )

    drone = first_or_create(
        Drones,
        numero_serie="DEMO-KML-DRONE-001",
        defaults={
            "tipo_equipamento": "drones",
            "status": "Ativo",
            "modelo": "DJI Agras Demo",
            "renomacao": "DEMO-KML-01",
            "categoria": "pulverizacao",
            "ano_fabricacao": 2026,
            "equipe_id": equipe.id,
            "registro_anatel": "ANATEL-DEMO-KML",
            "registro_anac": "ANAC-DEMO-KML",
            "pmd_kg": 25.0,
        },
    )
    drone.equipe_id = equipe.id

    points = [
        {"lat": -23.550520, "lng": -46.633308, "alt": 760},
        {"lat": -23.550130, "lng": -46.632340, "alt": 762},
        {"lat": -23.549620, "lng": -46.633020, "alt": 761},
        {"lat": -23.550040, "lng": -46.633880, "alt": 763},
        {"lat": -23.550520, "lng": -46.633308, "alt": 760},
    ]
    route = DjiFlightKmlRoute.query.filter_by(route_code=DEMO_ROUTE_CODE).first()
    if not route:
        route = DjiFlightKmlRoute(
            route_code=DEMO_ROUTE_CODE,
            original_filename="demo_kml_os_rota_001.kml",
            stored_filename="demo_kml_os_rota_001.kml",
            stored_path="dji-flight-routes/demo_kml_os_rota_001.kml",
            file_sha256=hashlib.sha256(DEMO_ROUTE_CODE.encode("utf-8")).hexdigest(),
            point_count=len(points),
            points_json=json.dumps(points),
        )
        db.session.add(route)
    route.aircraft_name = drone.renomacao
    route.pilot_name = piloto.nome_piloto
    route.flight_controller_id = "DEMO-FC-KML"
    route.route_timestamp = route_time
    route.mode_selection = "Demo"
    route.flight_time_raw = "00:12:35"
    route.task_area = 1.75
    route.spray_amount = 8.4
    route.route_color = "ff2d7d46"
    route.route_width = 4
    route.point_count = len(points)
    route.points_json = json.dumps(points)

    solicitacao = Solicitacao.query.filter_by(protocolo=DEMO_TAG).first()
    if not solicitacao:
        solicitacao = Solicitacao(
            data_agendamento=scheduled_date,
            hora_agendamento=time(9, 0),
            foco="Criadouro demo com rota KML",
            cep="01001-000",
            logradouro="Praca da Se",
            bairro="Se",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=uvis.id,
            equipe_id=equipe.id,
            piloto_id=piloto.id,
            protocolo=DEMO_TAG,
        )
        db.session.add(solicitacao)
    solicitacao.status = "CONCLUIDO"
    solicitacao.tipo_operacao = "Tratamento"
    solicitacao.tipo_visita = "Rotina"
    solicitacao.tipo_imovel = "Publico"
    solicitacao.altura_voo = "10m"
    solicitacao.numero = "s/n"
    solicitacao.complemento = "Registro de demonstracao KML"
    solicitacao.latitude = "-23.550520"
    solicitacao.longitude = "-46.633308"
    solicitacao.observacao = "OS demonstrativa para visualizar o vinculo com rota KML."
    solicitacao.equipe_id = equipe.id
    solicitacao.piloto_id = piloto.id
    solicitacao.usuario_id = uvis.id

    db.session.flush()

    ordem = OrdemServico.query.filter_by(solicitacao_id=solicitacao.id).first()
    if not ordem:
        ordem = OrdemServico(solicitacao_id=solicitacao.id, equipe_id=equipe.id)
        db.session.add(ordem)
    ordem.equipe_id = equipe.id
    ordem.identificador_os = "OS-DEMO-KML-001"
    ordem.respondido_por = piloto.nome_piloto
    ordem.respondido_em = now
    ordem.situacao_aplicacao = "MONITORADO E LARVICIDA APLICADO"
    ordem.larva_visualizada = "SIM"
    ordem.retornar_proxima_semana_monitorar_larvas = "NAO"
    ordem.distrito_administrativo = "DEMO"
    ordem.nome_rf_ace_responsavel_os = "ACE Demo KML - RF 000000"
    ordem.criadouro_os_tipo_volume = "Criadouro demo - 250 L"
    ordem.data_aplicacao = scheduled_date
    ordem.hora_inicio_aplicacao = time(9, 10)
    ordem.hora_termino_aplicacao = time(9, 30)
    ordem.tratamento_adicional_realizado = "NAO"
    ordem.descricao_produto = "BTI WDG Demo"
    ordem.formulacao_produto = "WDG"
    ordem.dosagem_g_10l = "500"
    ordem.tipo_aplicacao = "Pulverizacao"
    ordem.quantidade_produto_administrada_ml = 840.0
    ordem.pulverizacao_area_l_ha = 10.0
    ordem.quantidade_imagens_registradas = 3
    ordem.quantidade_videos_registradas = 1
    ordem.ponta_pulverizacao = "XR 11002"
    ordem.temperatura_c = 24.5
    ordem.umidade_relativa_pct = 68.0
    ordem.velocidade_vento_kmh = 6.2
    ordem.observacoes = "OS demonstrativa com KML vinculado para validar relatorios."
    ordem.piloto = piloto.nome_piloto
    ordem.auxiliar = "Auxiliar Demo KML"
    ordem.proprietario_ou_preposto = "Responsavel Demo"
    ordem.drone_id = drone.id
    ordem.drone_denominacao = drone.renomacao
    ordem.drone_modelo = drone.modelo
    ordem.drone_numero_serie = drone.numero_serie
    ordem.drone_registro_anatel = drone.registro_anatel
    ordem.drone_registro_anac = drone.registro_anac
    ordem.prefixo_aeronave_pulverizacao = drone.renomacao
    ordem.dji_kml_route_id = route.id

    db.session.commit()
    return solicitacao, ordem, route


def main():
    app = create_app()
    with app.app_context():
        ensure_kml_column()
        solicitacao, ordem, route = ensure_demo_records()
        print("DEMO_KML_OS_SEEDED")
        print(f"solicitacao_id={solicitacao.id}")
        print(f"ordem_id={ordem.id}")
        print(f"identificador_os={ordem.identificador_os}")
        print(f"kml_route_id={route.id}")
        print(f"route_code={route.route_code}")
        print(f"relatorio_os_url=/relatorios-os?protocolo={DEMO_TAG}")
        print(f"os_form_url=/admin/os/{solicitacao.id}/formulario")


if __name__ == "__main__":
    main()
