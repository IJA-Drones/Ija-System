import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import DjiFlightKmlRoute, Drones, Equipe, OrdemServico, Pilotos, Solicitacao, Usuario


DEMO_PREFIX = "REAL-KML"
MAX_ROUTES = 10


def slug(value):
    value = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-")
    return value[:40] or "ROTA"


def first_or_create(model, defaults=None, **filters):
    row = model.query.filter_by(**filters).first()
    if row:
        return row
    row = model(**filters, **(defaults or {}))
    db.session.add(row)
    db.session.flush()
    return row


def route_first_point(route):
    try:
        points = json.loads(route.points_json or "[]")
    except Exception:
        points = []
    if not points:
        return "", ""
    point = points[0] or {}
    return str(point.get("lat") or ""), str(point.get("lng") or "")


def ensure_base_records():
    uvis = first_or_create(
        Usuario,
        login="demo_rotas_reais_uvis",
        defaults={
            "nome_uvis": "UVIS Rotas Reais KML",
            "senha_hash": "demo-seed-nao-usar-login",
            "tipo_usuario": "uvis",
            "regiao": "DEMO",
        },
    )
    equipe = first_or_create(
        Equipe,
        nome_equipe="Equipe Rotas Reais KML",
        defaults={
            "descricao": "Equipe criada para visualizar rotas KML reais vinculadas a OS.",
            "regiao": "DEMO",
            "ativa": True,
        },
    )
    return uvis, equipe


def ensure_piloto(route):
    nome = (route.pilot_name or "Piloto Rota KML").strip()
    piloto = Pilotos.query.filter(Pilotos.nome_piloto == nome).first()
    if piloto:
        return piloto
    piloto = Pilotos(nome_piloto=nome, regiao="DEMO", telefone="")
    db.session.add(piloto)
    db.session.flush()
    return piloto


def ensure_drone(route, equipe):
    aircraft = (route.aircraft_name or "AERONAVE-KML").strip()
    serial = f"{DEMO_PREFIX}-DRONE-{slug(aircraft)}"
    drone = Drones.query.filter_by(numero_serie=serial).first()
    if not drone:
        drone = Drones(
            tipo_equipamento="drones",
            status="Ativo",
            modelo="DJI KML Real",
            renomacao=aircraft,
            categoria="pulverizacao",
            ano_fabricacao=2026,
            equipe_id=equipe.id,
            numero_serie=serial,
            registro_anatel=f"ANATEL-{slug(aircraft)}",
            registro_anac=f"ANAC-{slug(aircraft)}",
            pmd_kg=25.0,
        )
        db.session.add(drone)
        db.session.flush()
    drone.equipe_id = equipe.id
    drone.renomacao = aircraft
    return drone


def upsert_os_for_route(route, uvis, equipe):
    piloto = ensure_piloto(route)
    drone = ensure_drone(route, equipe)
    lat, lng = route_first_point(route)

    route_dt = route.route_timestamp or datetime.combine(date.today(), time(9, 0))
    start_dt = route_dt - timedelta(minutes=15)
    end_dt = route_dt + timedelta(minutes=15)
    protocolo = f"{DEMO_PREFIX}-{route.route_code}"

    solicitacao = Solicitacao.query.filter_by(protocolo=protocolo).first()
    if not solicitacao:
        solicitacao = Solicitacao(
            data_agendamento=route_dt.date(),
            hora_agendamento=start_dt.time().replace(second=0, microsecond=0),
            foco=f"Rota KML real {route.route_code}",
            cep="01001-000",
            logradouro="Endereco gerado pela rota KML",
            bairro="Referencia KML",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=uvis.id,
            equipe_id=equipe.id,
            piloto_id=piloto.id,
            protocolo=protocolo,
        )
        db.session.add(solicitacao)

    solicitacao.status = "CONCLUIDO"
    solicitacao.data_agendamento = route_dt.date()
    solicitacao.hora_agendamento = start_dt.time().replace(second=0, microsecond=0)
    solicitacao.tipo_operacao = "Tratamento"
    solicitacao.tipo_visita = "Rotina"
    solicitacao.tipo_imovel = "Publico"
    solicitacao.altura_voo = "10m"
    solicitacao.numero = "s/n"
    solicitacao.complemento = f"OS criada para visualizar a rota KML real {route.route_code}"
    solicitacao.latitude = lat
    solicitacao.longitude = lng
    solicitacao.observacao = "Solicitacao demo criada a partir de KML real importado."
    solicitacao.usuario_id = uvis.id
    solicitacao.equipe_id = equipe.id
    solicitacao.piloto_id = piloto.id
    db.session.flush()

    ordem = OrdemServico.query.filter_by(solicitacao_id=solicitacao.id).first()
    if not ordem:
        ordem = OrdemServico(solicitacao_id=solicitacao.id, equipe_id=equipe.id)
        db.session.add(ordem)

    ordem.equipe_id = equipe.id
    ordem.identificador_os = f"OS-{DEMO_PREFIX}-{route.route_code}"
    ordem.respondido_por = piloto.nome_piloto
    ordem.respondido_em = route_dt + timedelta(minutes=20)
    ordem.situacao_aplicacao = "MONITORADO E LARVICIDA APLICADO"
    ordem.larva_visualizada = "SIM"
    ordem.retornar_proxima_semana_monitorar_larvas = "NAO"
    ordem.distrito_administrativo = "DEMO"
    ordem.nome_rf_ace_responsavel_os = "ACE Demo Rotas Reais - RF 000000"
    ordem.criadouro_os_tipo_volume = f"Criadouro da rota {route.route_code}"
    ordem.data_aplicacao = route_dt.date()
    ordem.hora_inicio_aplicacao = start_dt.time().replace(second=0, microsecond=0)
    ordem.hora_termino_aplicacao = end_dt.time().replace(second=0, microsecond=0)
    ordem.tratamento_adicional_realizado = "NAO"
    ordem.descricao_produto = "BTI WDG Demo"
    ordem.formulacao_produto = "WDG"
    ordem.dosagem_g_10l = "500"
    ordem.tipo_aplicacao = "Pulverizacao"
    ordem.quantidade_produto_administrada_ml = route.spray_amount or 0
    ordem.pulverizacao_area_l_ha = 10.0
    ordem.quantidade_imagens_registradas = 1
    ordem.quantidade_videos_registradas = 0
    ordem.ponta_pulverizacao = "XR 11002"
    ordem.temperatura_c = 24.0
    ordem.umidade_relativa_pct = 65.0
    ordem.velocidade_vento_kmh = 5.5
    ordem.observacoes = f"OS demo vinculada automaticamente a rota KML real {route.route_code}."
    ordem.piloto = piloto.nome_piloto
    ordem.auxiliar = ""
    ordem.proprietario_ou_preposto = "Responsavel Demo Rotas Reais"
    ordem.drone_id = drone.id
    ordem.drone_denominacao = drone.renomacao
    ordem.drone_modelo = drone.modelo
    ordem.drone_numero_serie = drone.numero_serie
    ordem.drone_registro_anatel = drone.registro_anatel
    ordem.drone_registro_anac = drone.registro_anac
    ordem.prefixo_aeronave_pulverizacao = drone.renomacao
    ordem.dji_kml_route_id = route.id
    return solicitacao, ordem


def main():
    app = create_app()
    with app.app_context():
        uvis, equipe = ensure_base_records()
        routes = (
            DjiFlightKmlRoute.query
            .filter(DjiFlightKmlRoute.route_code != "DEMO-KML-OS-ROTA-001")
            .order_by(DjiFlightKmlRoute.route_timestamp.desc(), DjiFlightKmlRoute.id.desc())
            .limit(MAX_ROUTES)
            .all()
        )
        created = []
        for route in routes:
            solicitacao, ordem = upsert_os_for_route(route, uvis, equipe)
            created.append((route, solicitacao, ordem))
        db.session.commit()

        print("REAL_KML_OS_SEEDED")
        print(f"total={len(created)}")
        for route, solicitacao, ordem in created:
            print(
                f"route_id={route.id} route_code={route.route_code} "
                f"solicitacao_id={solicitacao.id} ordem_id={ordem.id} os={ordem.identificador_os}"
            )
        print("relatorio_url=/relatorios-os?data_ini=2026-06-30&data_fim=2026-07-01&status=CONCLUIDO")


if __name__ == "__main__":
    main()
