import os
import unittest
from datetime import datetime, time, timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from flask import Flask, request
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Abastecimento,
    AuditoriaUsuario,
    Equipe,
    LimpezaVeiculo,
    LimpezaVeiculoAlertaCiencia,
    LogVeiculo,
    OrdemServico,
    Prefeitura,
    Solicitacao,
    Usuario,
    Veiculos,
)
from app.modules.veiculos import service as veiculos_service
from app.modules.veiculos.service import (
    build_veiculo_media_skybox_path,
    build_piloto_veiculos_context,
    build_veiculos_deleted_logs_context,
    delete_veiculo_log,
    encerrar_turno_piloto,
    iniciar_turno_piloto,
    registrar_abastecimento_turno_piloto,
    build_limpeza_alertas_admin_context,
    build_limpeza_alertas_operacionais_context,
    confirmar_alerta_limpeza_operacional,
    update_veiculo,
    update_veiculo_log_km,
)


class VeiculosOperationalScopeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        prefeitura = Prefeitura(id=1, nome="Prefeitura Teste", slug="prefeitura-teste")
        self.equipe = Equipe(nome_equipe="PLOA 23", regiao="SUL", ativa=True, prefeitura_id=1)
        db.session.add_all([prefeitura, self.equipe])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _novo_veiculo(self, **overrides):
        data = {
            "tipo_equipamento": "veiculos",
            "status": "Ativo",
            "modelo": "FIORINO",
            "ano_fabricacao": 2024,
            "renomacao": "ABC1D23",
            "frota": "PROPRIA",
            "operacao": "PMSP",
            "placa": "ABC1D23",
            "km_atual": 1000,
            "equipe_id": self.equipe.id,
            "prefeitura_id": None,
        }
        data.update(overrides)
        veiculo = Veiculos(**data)
        db.session.add(veiculo)
        db.session.commit()
        return veiculo

    def test_equipe_oceano_sees_legacy_vehicle_linked_by_team_id_without_prefeitura(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        context = build_piloto_veiculos_context(user)

        self.assertTrue(context["piloto_vinculado"])
        self.assertEqual([item.id for item in context["veiculos"]], [veiculo.id])

    def test_update_vehicle_inherits_prefeitura_from_selected_team(self):
        veiculo = self._novo_veiculo(equipe_id=None)

        update_veiculo(
            veiculo,
            {
                "modelo": "FIORINO",
                "ano_fabricacao": 2024,
                "frota": "PROPRIA",
                "operacao": "PMSP",
                "placa": "ABC1D23",
                "responsavel": None,
                "equipe_id": self.equipe.id,
                "km_atual": 1000,
                "km_prox_revisao": None,
                "status": "Ativo",
                "revisao_marcada_em": None,
                "revisao_obs": None,
            },
        )

        self.assertEqual(veiculo.prefeitura_id, 1)

    def test_pilot_vehicle_context_uses_last_closed_km_as_initial_reference(self):
        veiculo = self._novo_veiculo(km_atual=1200)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1234,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        context = build_piloto_veiculos_context(user)
        referencia = context["km_inicial_referencias"][veiculo.id]

        self.assertEqual(referencia["km"], 1234)
        self.assertEqual(referencia["origem"], "ultimo_fechamento")
        self.assertEqual(referencia["log_id"], log.id)

    def test_cleaning_alert_reaches_operational_inbox_after_14_days(self):
        veiculo = self._novo_veiculo(criado_em=datetime.now() - timedelta(days=30))
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1010,
            check_diario=True,
        )
        db.session.add(log)
        db.session.flush()
        db.session.add(
            LimpezaVeiculo(
                log_veiculo_id=log.id,
                veiculo_id=veiculo.id,
                equipe_id=self.equipe.id,
                data_hora=datetime.now() - timedelta(days=15),
                limpeza_realizada=True,
                tipo_limpeza="completa",
                valor_total=80,
            )
        )
        usuario = Usuario(
            nome_uvis="Equipe PLOA 23",
            login="equipe-alerta",
            senha_hash="x",
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
            trabalha_oceano_azul=True,
        )
        db.session.add(usuario)
        db.session.commit()

        context = build_limpeza_alertas_operacionais_context(usuario)

        self.assertEqual(len(context["alertas"]), 1)
        self.assertEqual(context["alertas"][0]["veiculo"].id, veiculo.id)
        self.assertEqual(context["total_pendentes"], 1)

    def test_operational_user_can_confirm_cleaning_alert(self):
        veiculo = self._novo_veiculo(criado_em=datetime.now() - timedelta(days=16))
        usuario = Usuario(
            nome_uvis="Equipe PLOA 23",
            login="equipe-confirma",
            senha_hash="x",
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
            trabalha_oceano_azul=True,
        )
        db.session.add(usuario)
        db.session.commit()

        message = confirmar_alerta_limpeza_operacional(usuario, veiculo.id)

        ciencia = LimpezaVeiculoAlertaCiencia.query.one()
        self.assertEqual(message, "Ciencia do alerta de limpeza registrada.")
        self.assertEqual(ciencia.usuario_id, usuario.id)
        self.assertEqual(ciencia.veiculo_id, veiculo.id)
        self.assertEqual(ciencia.prazo_dias, 14)
        self.assertIsNotNone(ciencia.reconhecido_em)

    def test_admin_cleaning_alert_after_21_days_shows_operational_ack(self):
        veiculo = self._novo_veiculo(criado_em=datetime.now() - timedelta(days=30))
        usuario_equipe = Usuario(
            nome_uvis="Equipe PLOA 23",
            login="equipe-admin-ciencia",
            senha_hash="x",
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
            trabalha_oceano_azul=True,
        )
        usuario_admin = Usuario(
            nome_uvis="Admin OA",
            login="admin-oa",
            senha_hash="x",
            tipo_usuario="admin",
            prefeitura_id=1,
            trabalha_oceano_azul=True,
        )
        db.session.add_all([usuario_equipe, usuario_admin])
        db.session.commit()
        confirmar_alerta_limpeza_operacional(usuario_equipe, veiculo.id)

        context = build_limpeza_alertas_admin_context(usuario_admin)

        self.assertEqual(context["total_alertas"], 1)
        self.assertEqual(context["alertas"][0]["veiculo"].id, veiculo.id)
        self.assertEqual(context["total_atores"], 1)
        self.assertEqual(context["total_cientes"], 1)
        self.assertEqual(context["alertas"][0]["atores"][0]["usuario"].id, usuario_equipe.id)
        self.assertIsNotNone(context["alertas"][0]["atores"][0]["ciencia"])

    def test_admin_cleaning_alert_excludes_agro_vehicles(self):
        self._novo_veiculo(
            placa="AGR1A21",
            renomacao="AGR1A21",
            operacao="AGRO",
            criado_em=datetime.now() - timedelta(days=45),
            prefeitura_id=1,
        )
        usuario_admin = Usuario(
            nome_uvis="Admin OA",
            login="admin-oa-agro-filter",
            senha_hash="x",
            tipo_usuario="admin",
            prefeitura_id=1,
            trabalha_oceano_azul=True,
        )
        db.session.add(usuario_admin)
        db.session.commit()

        context = build_limpeza_alertas_admin_context(usuario_admin)

        self.assertEqual(context["total_alertas"], 0)

    def test_start_shift_rejects_initial_km_different_from_last_closed_shift(self):
        veiculo = self._novo_veiculo(km_atual=1300)
        db.session.add(
            LogVeiculo(
                veiculo_id=veiculo.id,
                equipe_id=self.equipe.id,
                km_inicial=1000,
                km_final=1234,
                check_diario=True,
            )
        )
        db.session.commit()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        with TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(veiculos_service.VeiculoTurnoError, "KM inicial travado em 1234 km"):
                iniciar_turno_piloto(
                    user,
                    veiculo.id,
                    {"km_inicial": "1300", "assinatura_b64": "data:image/png;base64,abc"},
                    {
                        "foto_painel": FileStorage(
                            stream=BytesIO(b"inicio"),
                            filename="inicio.png",
                            content_type="image/png",
                        ),
                    },
                    tmp_dir,
                )

    def test_start_shift_rejects_initial_km_different_from_current_km_when_no_closed_shift(self):
        veiculo = self._novo_veiculo(km_atual=1300)
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )

        with TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(veiculos_service.VeiculoTurnoError, "KM inicial travado em 1300 km"):
                iniciar_turno_piloto(
                    user,
                    veiculo.id,
                    {"km_inicial": "1301", "assinatura_b64": "data:image/png;base64,abc"},
                    {
                        "foto_painel": FileStorage(
                            stream=BytesIO(b"inicio"),
                            filename="inicio.png",
                            content_type="image/png",
                        ),
                    },
                    tmp_dir,
                )

    def test_update_vehicle_log_km_recalculates_vehicle_current_km(self):
        veiculo = self._novo_veiculo(km_atual=324507, prefeitura_id=1)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=32457,
            km_final=324507,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        message = update_veiculo_log_km(
            user,
            log.id,
            {"km_inicial": "32457", "km_final": "32457"},
        )

        db.session.refresh(log)
        db.session.refresh(veiculo)
        self.assertEqual(message, f"Log #{log.id} corrigido com sucesso.")
        self.assertEqual(log.km_inicial, 32457)
        self.assertEqual(log.km_final, 32457)
        self.assertEqual(veiculo.km_atual, 32457)

    def test_vehicle_km_parser_accepts_thousand_separator_and_decimal_km(self):
        self.assertEqual(veiculos_service._parse_km_form("32,000"), 32000)
        self.assertEqual(veiculos_service._parse_km_form("32.000"), 32000)
        self.assertEqual(veiculos_service._parse_km_form("32000,0"), 32000)
        self.assertEqual(veiculos_service._parse_km_form("32000,5"), 32000.5)
        self.assertEqual(veiculos_service._parse_km_form("32.000,5"), 32000.5)
        self.assertEqual(veiculos_service._parse_km_form("32,000.5"), 32000.5)

        with self.assertRaises(ValueError):
            veiculos_service._parse_km_form("32a000")

    def test_update_vehicle_log_km_accepts_decimal_km(self):
        veiculo = self._novo_veiculo(km_atual=32337, prefeitura_id=1)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=32337,
            km_final=32340,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        message = update_veiculo_log_km(
            user,
            log.id,
            {"km_inicial": "32337", "km_final": "32337,6"},
        )

        db.session.refresh(log)
        db.session.refresh(veiculo)
        self.assertEqual(message, f"Log #{log.id} corrigido com sucesso.")
        self.assertEqual(log.km_final, 32337.6)
        self.assertEqual(veiculo.km_atual, 32337.6)

    def test_update_vehicle_log_km_can_correct_fuel_amount_with_decimal_comma(self):
        veiculo = self._novo_veiculo(km_atual=1030, prefeitura_id=1)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1030,
            check_diario=True,
        )
        db.session.add(log)
        db.session.flush()
        abastecimento = Abastecimento(
            log_veiculo_id=log.id,
            data_hora=datetime(2026, 7, 2, 9, 0),
            km_registro=1020,
            tipo_abastecimento="Veiculo",
            litros=10,
            valor_total=14024,
            foto_nf_path="uploads/veiculos/notas/teste.png",
        )
        db.session.add(abastecimento)
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        message = update_veiculo_log_km(
            user,
            log.id,
            {
                "km_inicial": "1000",
                "km_final": "1030",
                f"abastecimento_{abastecimento.id}_km": "1020",
                f"abastecimento_{abastecimento.id}_valor": "140,24",
            },
        )

        db.session.refresh(abastecimento)
        self.assertEqual(message, f"Log #{log.id} corrigido com sucesso.")
        self.assertEqual(abastecimento.valor_total, 140.24)

    def test_admin_can_delete_vehicle_log_and_recalculate_current_km(self):
        veiculo = self._novo_veiculo(km_atual=1030, prefeitura_id=1)
        older_log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1010,
            check_diario=True,
            data_registro=datetime(2026, 7, 1, 8, 0),
        )
        newer_log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1010,
            km_final=1030,
            check_diario=True,
            data_registro=datetime(2026, 7, 2, 8, 0),
        )
        db.session.add_all([older_log, newer_log])
        db.session.flush()
        db.session.add(
            Abastecimento(
                log_veiculo_id=newer_log.id,
                data_hora=datetime(2026, 7, 2, 9, 0),
                km_registro=1020,
                tipo_abastecimento="Veiculo",
                litros=10,
                valor_total=100,
                foto_nf_path="uploads/veiculos/notas/teste.png",
            )
        )
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        message = delete_veiculo_log(user, newer_log.id)

        db.session.refresh(veiculo)
        self.assertEqual(message, f"Log #{newer_log.id} removido com sucesso.")
        self.assertIsNone(db.session.get(LogVeiculo, newer_log.id))
        self.assertEqual(Abastecimento.query.count(), 0)
        self.assertEqual(veiculo.km_atual, 1010)
        audit_log = AuditoriaUsuario.query.filter_by(endpoint="main.deletar_log_veiculo.snapshot").one()
        self.assertIn(f'"log_id": {newer_log.id}', audit_log.query_string)
        self.assertIn('"placa": "ABC1D23"', audit_log.query_string)
        self.assertIn('"total_valor_abastecido": 100', audit_log.query_string)

    def test_non_admin_cannot_delete_vehicle_log(self):
        veiculo = self._novo_veiculo(km_atual=1030, prefeitura_id=1)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1030,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="operario", prefeitura_id=1)

        with self.assertRaises(PermissionError):
            delete_veiculo_log(user, log.id)

        db.session.rollback()
        self.assertIsNotNone(db.session.get(LogVeiculo, log.id))
        self.assertEqual(AuditoriaUsuario.query.count(), 0)

    def test_dev_can_view_deleted_vehicle_log_history_from_existing_audit_table(self):
        db.session.add(
            AuditoriaUsuario(
                usuario_nome="Admin",
                usuario_login="admin",
                tipo_usuario="admin",
                metodo="POST",
                tipo_evento="EXCLUSAO",
                endpoint="main.deletar_log_veiculo.snapshot",
                path="/veiculos/logs/10/deletar",
                query_string=(
                    '{"log_id": 10, "veiculo": {"placa": "ABC1D23", "modelo": "FIORINO"}, '
                    '"operador": {"equipe_nome": "PLOA 01"}, '
                    '"turno": {"km_inicial": 1000, "km_final": 1010, "km_rodado": 10}, '
                    '"totais": {"qtd_abastecimentos": 1, "total_valor_abastecido": 100}, '
                    '"abastecimentos": []}'
                ),
                status_code=200,
            )
        )
        db.session.commit()

        with self.app.test_request_context("/admin/veiculos/logs-excluidos?q=ABC1D23"):
            context = build_veiculos_deleted_logs_context("dev", request.args)

        self.assertEqual(context["paginacao"].total, 1)
        self.assertEqual(context["logs_excluidos"][0]["snapshot"]["log_id"], 10)
        self.assertEqual(context["logs_excluidos"][0]["veiculo"]["placa"], "ABC1D23")

    def test_non_dev_cannot_view_deleted_vehicle_log_history(self):
        with self.app.test_request_context("/admin/veiculos/logs-excluidos"):
            with self.assertRaises(PermissionError):
                build_veiculos_deleted_logs_context("admin", request.args)

    def test_closing_shift_rejects_more_than_500_km_in_turn(self):
        veiculo = self._novo_veiculo(km_atual=1000)
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(veiculos_service.VeiculoTurnoError, "500 km por turno"):
                encerrar_turno_piloto(
                    user,
                    veiculo.id,
                    {"km_final": "1601", "qtd_fazendas_enderecos": "1", "observacao": ""},
                    {
                        "foto_painel_final": FileStorage(stream=BytesIO(b"fim"), filename="fim.png", content_type="image/png"),
                    },
                    tmp_dir,
                )

    def test_vehicle_local_media_path_resolves_to_skybox_path(self):
        self.assertEqual(
            build_veiculo_media_skybox_path(
                "uploads/veiculos/paineis/painel_inicial_ABC1D23_2026-07-08_09-23-31-123.jpg",
                "ABC1D23",
            ),
            "registros abastecimento/ABC1D23/2026-07-08/foto do painel/painel_inicial_ABC1D23_2026-07-08_09-23-31-123.jpg",
        )

    def test_vehicle_photo_upload_uses_skybox_only_when_enabled(self):
        self.app.config.update(
            SKYBOX_WEBDAV_URL="https://skybox.example/remote.php/dav/files/user",
            SKYBOX_USERNAME="user",
            SKYBOX_APP_PASSWORD="secret",
            SKYBOX_BASE_DIR="base",
        )
        captured = []
        original_upload = veiculos_service.upload_file_to_skybox

        def fake_upload(file_storage, remote_path):
            file_storage.stream.seek(0)
            captured.append((remote_path, file_storage.stream.read()))
            return f"skybox://{remote_path}"

        veiculos_service.upload_file_to_skybox = fake_upload
        try:
            with TemporaryDirectory() as tmp_dir:
                storage = FileStorage(
                    stream=BytesIO(b"foto-painel"),
                    filename="painel.jpg",
                    content_type="image/jpeg",
                )

                media_path = veiculos_service._salvar_upload_veiculo(
                    storage,
                    tmp_dir,
                    "paineis",
                    "painel_inicial",
                    "ABC1D23",
                    copiar_skybox=True,
                )

                self.assertRegex(
                    media_path,
                    r"^skybox://registros abastecimento/ABC1D23/\d{4}-\d{2}-\d{2}/foto do painel/painel_inicial_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.jpg$",
                )
                self.assertFalse(os.path.exists(os.path.join(tmp_dir, "static", "uploads", "veiculos", "paineis")))
        finally:
            veiculos_service.upload_file_to_skybox = original_upload

        self.assertEqual(len(captured), 1)
        self.assertRegex(
            captured[0][0],
            r"^registros abastecimento/ABC1D23/\d{4}-\d{2}-\d{2}/foto do painel/painel_inicial_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.jpg$",
        )
        self.assertEqual(captured[0][1], b"foto-painel")

    def test_vehicle_logs_list_keeps_cards_aggregated_while_table_is_paginated(self):
        veiculo = self._novo_veiculo(prefeitura_id=1)
        for index in range(25):
            log = LogVeiculo(
                veiculo_id=veiculo.id,
                equipe_id=self.equipe.id,
                km_inicial=1000 + index,
                km_final=1001 + index,
                check_diario=True,
                data_registro=datetime(2026, 7, 1, 8, 0) + timedelta(days=index),
            )
            db.session.add(log)
            db.session.flush()
            db.session.add(
                Abastecimento(
                    log_veiculo_id=log.id,
                    data_hora=log.data_registro,
                    km_registro=1001 + index,
                    tipo_abastecimento="Gerador" if index == 0 else "Veiculo",
                    litros=1,
                    valor_total=10,
                    foto_nf_path="uploads/veiculos/notas/teste.png",
                )
            )
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="admin", prefeitura_id=1)

        with self.app.test_request_context("/veiculos/logs?page=1"):
            context = veiculos_service.list_veiculos_logs("admin", request.args, user=user)

        self.assertEqual(context["total_logs"], 25)
        self.assertEqual(context["total_abastecido"], 250)
        self.assertEqual(len(context["logs"]), 20)
        self.assertEqual(context["veiculos_timeline"][0]["total_logs"], 25)
        self.assertEqual(context["veiculos_timeline"][0]["total_km"], 25)
        self.assertEqual(context["veiculos_timeline"][0]["total_gasto"], 250)
        self.assertEqual(context["veiculos_timeline"][0]["total_gasto_veiculo"], 240)
        self.assertEqual(context["veiculos_timeline"][0]["total_gasto_gerador"], 10)
        self.assertEqual(context["veiculos_timeline"][0]["total_abastecimentos"], 25)
        self.assertEqual(context["veiculos_timeline"][0]["total_abastecimentos_veiculo"], 24)
        self.assertEqual(context["veiculos_timeline"][0]["total_abastecimentos_gerador"], 1)

    def test_vehicle_log_detail_shows_automatic_returns_for_audit_profiles(self):
        veiculo = self._novo_veiculo(prefeitura_id=1)
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=1010,
            check_diario=True,
            data_registro=datetime(2026, 7, 31, 8, 0),
        )
        uvis = Usuario(
            nome_uvis="UVIS Teste",
            login="uvis-teste",
            senha_hash="x",
            tipo_usuario="uvis",
            prefeitura_id=1,
        )
        db.session.add_all([log, uvis])
        db.session.flush()
        solicitacao = Solicitacao(
            prefeitura_id=1,
            data_agendamento=datetime(2026, 7, 31).date(),
            hora_agendamento=time(9, 0),
            foco="Aedes",
            cep="00000-000",
            logradouro="Rua Teste",
            numero="123",
            bairro="Centro",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=uvis.id,
            equipe_id=self.equipe.id,
            status="CONCLUIDO",
            gerada_automaticamente=True,
        )
        db.session.add(solicitacao)
        db.session.flush()
        db.session.add(
            OrdemServico(
                solicitacao_id=solicitacao.id,
                equipe_id=self.equipe.id,
                identificador_os="OS-RET-1",
                data_aplicacao=datetime(2026, 7, 31).date(),
            )
        )
        db.session.commit()
        user = SimpleNamespace(tipo_usuario="visualizar", prefeitura_id=1)

        with self.app.test_request_context(f"/veiculos/logs/veiculo/{veiculo.id}"):
            context = veiculos_service.build_veiculo_logs_detalhe_context("visualizar", veiculo.id, request.args, user=user)

        turno = context["timeline"]["dias"][0]["turnos"][0]
        self.assertTrue(context["can_view_retorno_automatico_audit"])
        self.assertEqual(turno["retornos_automaticos_count"], 1)
        self.assertEqual(turno["retornos_automaticos"][0]["id"], solicitacao.id)
        self.assertIn("Rua Teste", turno["retornos_automaticos"][0]["endereco"])

    def test_fuel_record_requires_and_saves_panel_photo(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            message = registrar_abastecimento_turno_piloto(
                user,
                veiculo.id,
                {
                    "km_abastecimento": "1010,3",
                    "litros": "20",
                    "valor_abastecimento": "100",
                    "tipo_abastecimento": "Veiculo",
                },
                {
                    "foto_nf": FileStorage(stream=BytesIO(b"nf"), filename="nf.png", content_type="image/png"),
                    "foto_painel_abastecimento": FileStorage(stream=BytesIO(b"painel"), filename="painel.png", content_type="image/png"),
                },
                tmp_dir,
            )

            abastecimento = Abastecimento.query.one()
            self.assertEqual(message, "Abastecimento registrado com sucesso!")
            self.assertRegex(
                abastecimento.foto_nf_path,
                r"^uploads/veiculos/notas/nf_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )
            self.assertRegex(
                abastecimento.foto_painel_path,
                r"^uploads/veiculos/paineis/painel_abastecimento_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )
            db.session.refresh(veiculo)
            self.assertEqual(veiculo.km_atual, 1000)

    def test_fuel_record_accepts_brazilian_decimal_comma(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            registrar_abastecimento_turno_piloto(
                user,
                veiculo.id,
                {
                    "km_abastecimento": "1010,3",
                    "litros": "40,5",
                    "valor_abastecimento": "1.402,40",
                    "tipo_abastecimento": "Veiculo",
                },
                {
                    "foto_nf": FileStorage(stream=BytesIO(b"nf"), filename="nf.png", content_type="image/png"),
                    "foto_painel_abastecimento": FileStorage(stream=BytesIO(b"painel"), filename="painel.png", content_type="image/png"),
                },
                tmp_dir,
            )

        abastecimento = Abastecimento.query.one()
        self.assertEqual(abastecimento.km_registro, 1010.3)
        self.assertEqual(abastecimento.litros, 40.5)
        self.assertEqual(abastecimento.valor_total, 1402.40)

    def test_fuel_record_rejects_more_than_500_km_from_shift_initial(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(veiculos_service.VeiculoTurnoError, "500 km por turno"):
                registrar_abastecimento_turno_piloto(
                    user,
                    veiculo.id,
                    {
                        "km_abastecimento": "1501",
                        "litros": "20",
                        "valor_abastecimento": "100",
                        "tipo_abastecimento": "Veiculo",
                    },
                    {
                        "foto_nf": FileStorage(stream=BytesIO(b"nf"), filename="nf.png", content_type="image/png"),
                        "foto_painel_abastecimento": FileStorage(stream=BytesIO(b"painel"), filename="painel.png", content_type="image/png"),
                    },
                    tmp_dir,
                )

    def test_closing_shift_rejects_final_km_lower_than_fuel_km(self):
        veiculo = self._novo_veiculo(km_atual=1000)
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            registrar_abastecimento_turno_piloto(
                user,
                veiculo.id,
                {
                    "km_abastecimento": "1500",
                    "litros": "20",
                    "valor_abastecimento": "100",
                    "tipo_abastecimento": "Veiculo",
                },
                {
                    "foto_nf": FileStorage(stream=BytesIO(b"nf"), filename="nf.png", content_type="image/png"),
                    "foto_painel_abastecimento": FileStorage(stream=BytesIO(b"painel"), filename="painel.png", content_type="image/png"),
                },
                tmp_dir,
            )
            with self.assertRaisesRegex(veiculos_service.VeiculoTurnoError, "KM do abastecimento"):
                encerrar_turno_piloto(
                    user,
                    veiculo.id,
                    {"km_final": "1020", "qtd_fazendas_enderecos": "2", "observacao": ""},
                    {
                        "foto_painel_final": FileStorage(stream=BytesIO(b"fim"), filename="fim.png", content_type="image/png"),
                    },
                    tmp_dir,
                )

            db.session.refresh(log)
            db.session.refresh(veiculo)
            self.assertEqual(log.km_inicial, 1000)
            self.assertIsNone(log.km_final)
            self.assertEqual(veiculo.km_atual, 1000)

    def test_closing_shift_requires_and_saves_final_panel_photo(self):
        veiculo = self._novo_veiculo()
        user = SimpleNamespace(
            tipo_usuario="equipe_oceano",
            codigo_setor=str(self.equipe.id),
            prefeitura_id=1,
        )
        log = LogVeiculo(
            veiculo_id=veiculo.id,
            equipe_id=self.equipe.id,
            km_inicial=1000,
            km_final=None,
            check_diario=True,
        )
        db.session.add(log)
        db.session.commit()

        with TemporaryDirectory() as tmp_dir:
            message = encerrar_turno_piloto(
                user,
                veiculo.id,
                {"km_final": "1020", "qtd_fazendas_enderecos": "2", "observacao": ""},
                {
                    "foto_painel_final": FileStorage(stream=BytesIO(b"fim"), filename="fim.png", content_type="image/png"),
                },
                tmp_dir,
            )

            db.session.refresh(log)
            self.assertEqual(message, "Turno encerrado com sucesso!")
            self.assertRegex(
                log.foto_painel_final_path,
                r"^uploads/veiculos/paineis/painel_fechamento_ABC1D23_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.png$",
            )


if __name__ == "__main__":
    unittest.main()
