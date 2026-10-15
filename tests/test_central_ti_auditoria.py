"""Permission-audit reader tests; all data lives in disposable in-memory SQLite."""

import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from unittest.mock import patch

import sqlalchemy as sa
from flask import template_rendered
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.routing import BuildError

from app.extensions import db
from app.models import CentralTiAuditoria, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.gestao_ti.catalog import AREA_CODES, PERMISSION_CODES
from tests import test_central_ti as central_base


AUDIT_URL = "/auditoria/permissoes"


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href")


class CentralTiAuditTests(unittest.TestCase):
    # Compose the existing isolated setup without inheriting and rerunning its tests.
    setUp = central_base.CentralTiTests.setUp
    tearDown = central_base.CentralTiTests.tearDown
    login = central_base.CentralTiTests.login

    def seed_event(self, *, perfil="admin", usuario="gestor_auditoria", criado_em=None,
                   antes=None, depois=None, versao_anterior=1):
        event = CentralTiAuditoria(
            lote=str(uuid4()), perfil_codigo=perfil,
            usuario_id=self.users["gestor_ti"].id, usuario_login=usuario,
            versao_anterior=versao_anterior, versao_nova=versao_anterior + 1,
            antes=antes if antes is not None else {"areas": [], "permissions": []},
            depois=depois if depois is not None else {"areas": ["prefeitura"], "permissions": ["prefeitura.relatorios.consultar"]},
            criado_em=criado_em or datetime(2026, 10, 15, 15, 0, 0),
        )
        db.session.add(event)
        db.session.commit()
        return event

    def configure(self, role, codes=()):
        configuration = CentralTiPerfilConfiguracao(
            perfil_codigo=role, versao=2, atualizado_por_id=self.users["dev"].id,
        )
        db.session.add(configuration)
        db.session.flush()
        db.session.add_all(CentralTiSelecao(perfil_codigo=role, codigo=code) for code in codes)
        db.session.commit()

    @contextmanager
    def rendered_context(self):
        contexts = []

        def record(sender, template, context, **extra):
            contexts.append(context)

        template_rendered.connect(record, self.app)
        try:
            yield contexts
        finally:
            template_rendered.disconnect(record, self.app)

    def page(self, query=None):
        with self.rendered_context() as contexts:
            response = self.client.get(AUDIT_URL, query_string=query or {})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
        self.assertTrue(contexts, "Audit page must render its shared-layout template.")
        return response, contexts[-1]

    def event_ids(self, context):
        pagination = context["paginacao"]
        return [event.id for event in pagination.items]

    def links(self, response):
        parser = _LinkParser()
        parser.feed(response.get_data(as_text=True))
        return parser.links

    def test_anonymous_is_redirected_to_login_without_cache(self):
        response = self.client.get(AUDIT_URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)
        self.assertTrue(response.cache_control.no_store)

    def test_dev_dashboard_tolerates_template_updated_before_server_restart(self):
        self.login("dev")
        original_url_for = self.app.url_for

        def old_server_url_for(endpoint, **values):
            if endpoint == "main.auditoria_permissoes":
                raise BuildError(endpoint, values, None)
            return original_url_for(endpoint, **values)

        old_processors = [
            processor for processor in self.app.template_context_processors[None]
            if processor.__name__ != "inject_permission_audit_access"
        ]
        with patch.dict(self.app.template_context_processors, {None: old_processors}), \
                patch.object(self.app, "url_for", side_effect=old_server_url_for):
            response = self.client.get("/dev")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(AUDIT_URL, self.links(response))

        updated_response = self.client.get("/dev")
        self.assertEqual(updated_response.status_code, 200)
        self.assertIn(AUDIT_URL, self.links(updated_response))

    def test_only_dev_and_director_can_read_with_central_flags_on_or_off(self):
        for enabled in (False, True):
            self.app.config.update(
                CENTRAL_TI_ENABLED=enabled, CENTRAL_TI_ENFORCE_PERMISSIONS=enabled,
            )
            for role in self.users:
                with self.subTest(enabled=enabled, role=role):
                    self.login(role)
                    response = self.client.get(AUDIT_URL)
                    self.assertEqual(response.status_code, 200 if role in {"dev", "diretor"} else 403)
                    self.assertTrue(response.cache_control.no_store)

    def test_empty_dynamic_director_configuration_cannot_revoke_the_fixed_reader(self):
        self.app.config["CENTRAL_TI_ENFORCE_PERMISSIONS"] = True
        self.configure("diretor")
        self.login("diretor")
        response, _ = self.page()
        self.assertTrue(response.cache_control.no_store)

    def test_granting_every_dynamic_permission_cannot_delegate_this_reader(self):
        self.app.config["CENTRAL_TI_ENFORCE_PERMISSIONS"] = True
        codes = sorted(PERMISSION_CODES | {f"area:{area}" for area in AREA_CODES})
        for role in self.users:
            if role in {"dev", "diretor"}:
                continue
            with self.subTest(role=role):
                self.configure(role, codes)
                self.login(role)
                self.assertEqual(self.client.get(AUDIT_URL).status_code, 403)
        self.assertEqual(CentralTiAuditoria.query.count(), 0)

    def test_get_only_reads_and_mutating_methods_are_unavailable(self):
        self.seed_event()
        self.login("dev")
        statements = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())

        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.page()
            head = self.client.head(AUDIT_URL)
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.data, b"")
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(method=method):
                    response = self.client.open(AUDIT_URL, method=method, json={"delete": True})
                    self.assertEqual(response.status_code, 405)
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertTrue(set(statements) <= {"SELECT"}, statements)
        self.assertEqual(CentralTiAuditoria.query.count(), 1)

    def test_human_readable_changes_author_versions_and_sao_paulo_timestamp(self):
        self.seed_event(
            perfil="prefeitura_admin", usuario="gestor_que_alterou",
            criado_em=datetime(2026, 10, 15, 13, 4, 5), versao_anterior=7,
            antes={"areas": ["prefeitura", "agro"], "permissions": [
                "prefeitura.relatorios.consultar", "prefeitura.relatorios.editar",
            ]},
            depois={"areas": ["prefeitura", "financeiro"], "permissions": [
                "prefeitura.relatorios.consultar", "prefeitura.relatorios.exportar",
            ]},
        )
        self.login("diretor")
        response, context = self.page()
        text = unescape(response.get_data(as_text=True))
        for expected in ("gestor_que_alterou", "Admin Prefeitura", "15/10/2026", "10:04:05",
                         "v7", "v8", "Prefeitura", "Relatórios", "Exportar", "Editar", "Agro", "Financeiro"):
            self.assertIn(expected, text)
        entry = context["entries"][0]
        self.assertCountEqual(entry["added"], ["Área: Financeiro", "Prefeitura · Relatórios · Exportar"])
        self.assertCountEqual(entry["removed"], ["Área: Agro", "Prefeitura · Relatórios · Editar"])

    def test_unknown_historical_codes_are_visible_but_html_is_escaped(self):
        malicious_login = '<img src=x onerror="alert(1)">'
        malicious_code = "<script>alert(1)</script>"
        self.seed_event(
            perfil="<b>perfil</b>", usuario=malicious_login,
            depois={"areas": ["area_antiga"], "permissions": [malicious_code]},
        )
        self.login("dev")
        response, _ = self.page()
        html = response.get_data(as_text=True)
        for literal in (malicious_login, malicious_code, "<b>perfil</b>"):
            self.assertNotIn(literal, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;b&gt;perfil&lt;/b&gt;", html)
        self.assertIn("area_antiga", html)

    def test_profile_and_responsible_filters_are_case_insensitive(self):
        expected = self.seed_event(perfil="admin", usuario="Gestor_MARIA")
        self.seed_event(perfil="piloto", usuario="gestor_maria")
        self.seed_event(perfil="admin", usuario="outro_gestor")
        self.login("dev")
        _, context = self.page({"perfil": "ADMIN", "usuario": "gEsToR_mArIa"})
        self.assertEqual(self.event_ids(context), [expected.id])

    def test_sql_like_wildcards_in_responsible_filter_are_literal(self):
        percent = self.seed_event(usuario="gestor%teste")
        underscore = self.seed_event(usuario="gestor_teste")
        self.seed_event(usuario="gestorXteste")
        self.login("dev")
        for value, expected in (("%", percent.id), ("_", underscore.id)):
            with self.subTest(value=value):
                _, context = self.page({"usuario": value})
                self.assertEqual(self.event_ids(context), [expected])

    def test_dates_include_the_entire_local_day_with_exclusive_next_midnight(self):
        local_start_utc = datetime(2026, 10, 15, 3, 0, 0)
        self.seed_event(criado_em=local_start_utc - timedelta(microseconds=1))
        first = self.seed_event(criado_em=local_start_utc)
        last = self.seed_event(criado_em=local_start_utc + timedelta(days=1, microseconds=-1))
        self.seed_event(criado_em=local_start_utc + timedelta(days=1))
        self.login("diretor")
        _, context = self.page({"data_inicio": "2026-10-15", "data_fim": "2026-10-15"})
        self.assertEqual(self.event_ids(context), [last.id, first.id])

    def test_invalid_dates_and_page_values_do_not_crash_or_mutate_data(self):
        self.seed_event()
        self.login("dev")
        for query in (
            {"data_inicio": "2026-02-30"},
            {"data_fim": "not-a-date"},
            {"data_inicio": "2026-10-16", "data_fim": "2026-10-15"},
            {"data_fim": "9999-12-31"},
            {"page": "not-a-number"},
            {"page": "-2"},
        ):
            with self.subTest(query=query):
                response, _ = self.page(query)
                self.assertTrue(response.cache_control.no_store)
        self.assertEqual(CentralTiAuditoria.query.count(), 1)

    def test_pagination_has_25_rows_stable_tiebreaker_and_preserves_filters(self):
        rows = [self.seed_event(usuario="paginacao_%") for _ in range(30)]
        self.login("dev")
        filters = {"perfil": "admin", "usuario": "%", "data_inicio": "2026-10-15", "data_fim": "2026-10-15"}
        response, first_context = self.page(filters)
        self.assertEqual(first_context["paginacao"].per_page, 25)
        self.assertEqual(self.event_ids(first_context), [row.id for row in reversed(rows[5:])])
        _, second_context = self.page({**filters, "page": "2"})
        self.assertEqual(self.event_ids(second_context), [row.id for row in reversed(rows[:5])])
        next_links = [parse_qs(urlsplit(link).query) for link in self.links(response)
                      if urlsplit(link).path == AUDIT_URL and parse_qs(urlsplit(link).query).get("page") == ["2"]]
        self.assertTrue(next_links, "The second page must be reachable without losing the active filters.")
        for key, value in filters.items():
            self.assertEqual(next_links[0].get(key), [value])

    def test_empty_results_render_normally(self):
        self.login("diretor")
        response, context = self.page()
        self.assertEqual(self.event_ids(context), [])
        self.assertEqual(context["paginacao"].total, 0)
        self.assertIn("Nenhum", response.get_data(as_text=True))

    def test_database_failure_is_unavailable_and_not_cacheable(self):
        self.login("dev")
        with patch("flask_sqlalchemy.query.Query.paginate", side_effect=SQLAlchemyError("test-only database failure")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.client.get(AUDIT_URL)
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.cache_control.no_store)
        self.assertNotIn("test-only database failure", response.get_data(as_text=True))

    def test_navigation_is_visible_to_dev_and_director_but_not_ti_manager(self):
        for role in ("dev", "diretor"):
            with self.subTest(role=role):
                self.login(role)
                response, _ = self.page()
                self.assertIn(AUDIT_URL, self.links(response))
        # Reading the history must not give the director permission to edit roles.
        self.assertEqual(self.client.get("/central-ti").status_code, 403)
        self.login("gestor_ti")
        response = self.client.get("/central-ti")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(AUDIT_URL, self.links(response))


if __name__ == "__main__":
    unittest.main()
