"""Resource, atomicity and ownership checks against disposable SINAN stores."""

import csv
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from app.modules.vigilancia import sinan, sinan_import, sinan_routes
from app.modules.vigilancia.sinan_store import BusyError, Store


SCOPE = {"disease": "dengue", "ibge": "3550308", "year": 2026}


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "private" / "sinan.sqlite")


def new_job(store, owner="admin", kind="api", **kwargs):
    return store.create(owner, kind=kind, **SCOPE, **kwargs)[0]


def page(count=10, offset=0, finished=False):
    return {"records": [{"week": "202601", "classification": "10", "residence": "local"}] * count,
            "finished": finished, "next_offset": None if finished else offset + count}


def test_single_global_worker_across_connections_and_owners(store):
    def create(owner):
        try:
            return new_job(store, owner)
        except BusyError:
            return None
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(create, ["a", "b", "c", "d"]))
    assert sum(value is not None for value in results) == 1
    with Store(store.path).connection() as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] == 1


def test_api_complete_aggregates_all_pages_and_reimport_is_not_summed(store):
    for _ in range(2):
        job = new_job(store)
        calls = []
        def fetch(**values):
            calls.append(values["offset"])
            return page() if values["offset"] == 0 else page(2, 10, True)
        sinan_import.run_api(store, job, SCOPE, fetch_page=fetch, delay=0)
        saved = store.get(job, "admin")
        assert saved["status"] == "completed"
        assert saved["summary"]["total"] == 12
        assert saved["summary"]["groups"] == [{"week": "202601", "classification": "10", "residence": "local", "count": 12}]
        assert calls == [0, 10]
    assert store.list("admin", **SCOPE)["current_id"] == job


def test_failure_and_partial_refresh_preserve_previous_completed_snapshot(store):
    old = new_job(store)
    sinan_import.run_api(store, old, SCOPE, fetch_page=lambda **_: page(1, 0, True), delay=0)
    partial = new_job(store)
    sinan_import.run_api(store, partial, SCOPE, fetch_page=lambda **_: page(), max_records=10, delay=0)
    assert store.get(partial, "admin")["status"] == "partial"
    assert store.get(partial, "admin")["count"] == 10
    failed = new_job(store)
    with patch.object(sinan, "fetch_page", side_effect=sinan.SinanError("Fonte indisponível")):
        sinan_import.run_api(store, failed, SCOPE, delay=0)
    assert store.get(failed, "admin")["status"] == "failed"
    assert store.get(failed, "admin")["summary"] == {}
    assert store.list("admin", **SCOPE)["current_id"] == old


def test_cancel_during_fetch_discards_late_page_and_releases_worker(store):
    job = new_job(store)
    def fetch(**_):
        store.cancel(job, "admin")
        return page(1, 0, True)
    sinan_import.run_api(store, job, SCOPE, fetch_page=fetch, delay=0)
    assert store.get(job, "admin")["status"] == "cancelled"
    assert store.get(job, "admin")["summary"] == {}
    assert new_job(store)


def test_default_import_stops_at_100_without_fetching_an_eleventh_page(store):
    job = new_job(store)
    offsets = []
    def fetch(**values):
        offsets.append(values['offset'])
        return page(offset=values['offset'])
    sinan_import.run_api(store, job, SCOPE, fetch_page=fetch, delay=0)
    saved = store.get(job, 'admin')
    assert offsets == list(range(0, 100, 10))
    assert saved['status'] == 'partial'
    assert saved['count'] == saved['summary']['total'] == 100
    assert '100 registros' in saved['message']


def test_csv_accepts_100_and_rejects_101_atomically(store):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';')
    writer.writerow(sinan_import.COLUMNS)
    for index in range(100):
        writer.writerow((f'DEMO-{index}', 'dengue', '3550308', 2026, '202601', 'suspeito', -23.55, -46.63))
    content = stream.getvalue().encode()
    job = new_job(store, kind='csv', demo=True)
    sinan_import.run_cases(store, job, SCOPE, content, True)
    assert store.get(job, 'admin')['count'] == 100
    assert len(store.cases(job, 'admin')) == 100
    writer.writerow(('DEMO-100', 'dengue', '3550308', 2026, '202601', 'suspeito', -23.55, -46.63))
    overflow = new_job(store, kind='csv', demo=True)
    sinan_import.run_cases(store, overflow, SCOPE, stream.getvalue().encode(), True)
    assert store.get(overflow, 'admin')['status'] == 'failed'
    assert store.cases(overflow, 'admin') == []
    assert len(store.cases(job, 'admin')) == 100


def test_restart_expiration_fences_late_worker_result(store):
    old = new_job(store)
    with store.connection() as db:
        db.execute("UPDATE jobs SET updated=? WHERE id=?", (time.time() - 100, old))
    fresh = new_job(store)
    store.finish(old, "completed", {"total": 99})
    assert store.get(old, "admin")["status"] == "failed"
    assert store.get(fresh, "admin")["status"] == "running"


def test_time_budget_and_empty_read_are_distinguished(store):
    job = new_job(store)
    with patch.object(sinan, "fetch_page") as fetch:
        sinan_import.run_api(store, job, SCOPE, max_seconds=0)
        fetch.assert_not_called()
    assert store.get(job, "admin")["status"] == "partial"
    job = new_job(store)
    sinan_import.run_api(store, job, SCOPE, fetch_page=lambda **_: page(0, 0, True), delay=0)
    assert store.get(job, "admin")["status"] == "completed"
    assert store.get(job, "admin")["count"] == 0


def csv_bytes(**replace):
    sample = sinan_import.sample_csv(SCOPE)
    reader = csv.DictReader(io.StringIO(sample.lstrip("\ufeff")), delimiter=";")
    rows = list(reader)
    rows[-1].update(replace)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sinan_import.COLUMNS, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


@pytest.mark.parametrize("bad", [
    {"latitude": "nan"}, {"longitude": "inf"}, {"latitude": "91"}, {"longitude": "0"},
    {"municipio_ibge": "2610905"}, {"doenca": "zika"}, {"ano": "2025"},
    {"semana": "202654"}, {"classificacao": ""}, {"referencia": "DEMO-001"},
    {"referencia": "=HYPERLINK(example)"}, {"referencia": "<script>"},
])
def test_invalid_csv_is_atomic_and_does_not_publish_earlier_valid_rows(store, bad):
    job = new_job(store, kind="csv", demo=True)
    sinan_import.run_cases(store, job, SCOPE, csv_bytes(**bad), True)
    assert store.get(job, "admin")["status"] == "failed"
    assert store.cases(job, "admin") == []
    assert store.get(job, "admin")["summary"] == {}


def test_size_rows_headers_and_demo_labels_are_enforced():
    with pytest.raises(ValueError, match="1 MiB"):
        sinan_import.parse_cases(b"a" * (sinan_import.MAX_BYTES + 1), SCOPE, True)
    with pytest.raises(ValueError, match="colunas"):
        sinan_import.parse_cases(b"nome,cpf,endereco\nprivate,private,private", SCOPE, True)
    with pytest.raises(ValueError, match="fictícios"):
        sinan_import.parse_cases(csv_bytes(), SCOPE, False)
    with patch.object(sinan_import, "MAX_CASES", 1), pytest.raises(ValueError, match="limite"):
        sinan_import.parse_cases(csv_bytes(), SCOPE, True)


def test_csv_persists_and_duplicate_file_reuses_lot_without_new_thread(store):
    content = csv_bytes()
    with patch.object(threading.Thread, "start") as start:
        job, existing = sinan_import.start(store, "admin", SCOPE, content=content, demo=True)
        assert not existing
        start.assert_called_once()
    sinan_import.run_cases(store, job, SCOPE, content, True)
    reloaded = Store(store.path)
    assert len(reloaded.cases(job, "admin")) == 2
    assert reloaded.cases(job, "other") == []
    assert reloaded.get(job, "other") is None
    with patch.object(threading.Thread, "start") as start:
        repeated, existing = sinan_import.start(reloaded, "admin", SCOPE, content=content, demo=True)
        assert existing and repeated == job
        start.assert_not_called()


def test_export_is_bounded_saved_data_with_provenance_and_no_network(store):
    job = new_job(store, kind="csv", demo=True)
    sinan_import.run_cases(store, job, SCOPE, csv_bytes(), True)
    with patch.object(sinan.requests, "get") as network:
        output = "".join(sinan_import.export_rows(store.get(job, "admin"), store.cases(job, "admin")))
        network.assert_not_called()
    rows = list(csv.DictReader(io.StringIO(output.lstrip("\ufeff")), delimiter=";"))
    assert len(rows) == 2
    assert all(row["demonstracao"] == "sim" and row["situacao"] == "completed" for row in rows)
    assert rows[0]["latitude"].startswith("-23.")
    assert "importado_em_utc" in rows[0]


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="isolated-import", SINAN_STORAGE_PATH=str(tmp_path / "imports.sqlite"))
    class User(UserMixin):
        def __init__(self, user_id):
            self.id = user_id
            self.tipo_usuario = "uvis" if user_id == "uvis" else "admin"
    manager = LoginManager(app)
    manager.user_loader(User)
    app.jinja_loader = ChoiceLoader([DictLoader({"base.html": "{% block content %}{% endblock %}"}), FileSystemLoader("app/templates")])
    bp = Blueprint("main", __name__)
    bp.add_url_rule("/relatorios", endpoint="relatorios", view_func=lambda: "ok")
    sinan_routes.register_routes(bp)
    app.register_blueprint(bp)
    return app


def login(client, user="admin"):
    with client.session_transaction() as session:
        session["_user_id"] = user
        session["_fresh"] = True
        session["_ija_csrf"] = "test-csrf"


HEADERS = {"X-CSRFToken": "test-csrf"}
BASE = "/api/vigilancia/sinan/importacoes"


def test_routes_auth_csrf_and_enabled_gate_before_worker(app):
    client = app.test_client()
    with patch.object(sinan_import, "start") as start:
        assert client.post(BASE, json=SCOPE).status_code == 401
        login(client, "uvis")
        assert client.post(BASE, json=SCOPE, headers=HEADERS).status_code == 403
        login(client)
        assert client.post(BASE, json=SCOPE).status_code == 403
        assert client.post(BASE, json={**SCOPE, "url": "https://other"}, headers=HEADERS).status_code == 400
        app.config["SINAN_IMPORT_ENABLED"] = False
        assert client.post(BASE, json=SCOPE, headers=HEADERS).status_code == 404
        start.assert_not_called()


def test_http_start_conflict_status_cancel_and_no_store(app):
    client = app.test_client()
    login(client)
    with patch.object(threading.Thread, "start"):
        response = client.post(BASE, json=SCOPE, headers=HEADERS)
        assert response.status_code == 202
        job_id = response.json["job"]["id"]
        assert client.post(BASE, json=SCOPE, headers=HEADERS).status_code == 409
    response = client.get(BASE, query_string=SCOPE)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert len(response.json["jobs"]) == 1
    assert "owner" not in response.json["jobs"][0]
    assert client.get(f"{BASE}/{job_id}/exportar.csv").status_code == 409
    assert client.post(f"{BASE}/{job_id}/cancelar", headers=HEADERS).json["job"]["cancel"] is True


def test_foreign_user_cannot_read_map_export_or_cancel_any_lot(app):
    store = Store(app.config["SINAN_STORAGE_PATH"])
    job_id = new_job(store, "None:admin", kind="csv", demo=True)
    sinan_import.run_cases(store, job_id, SCOPE, csv_bytes(), True)
    client = app.test_client()
    login(client, "other")
    for suffix in ("", "/mapa", "/exportar.csv"):
        assert client.get(f"{BASE}/{job_id}{suffix}").status_code == 404
    assert client.post(f"{BASE}/{job_id}/cancelar", headers=HEADERS).status_code == 404
    assert client.get(BASE, query_string=SCOPE).json["jobs"] == []
    login(client)
    data = client.get(f"{BASE}/{job_id}/mapa").json
    assert data["demo"] is True and len(data["points"]) == 2
    assert client.get(f"{BASE}/{job_id}/exportar.csv").status_code == 200


def test_upload_payload_limit_and_authorization(app):
    client = app.test_client()
    login(client)
    def upload(content, **extra):
        return client.post("/api/vigilancia/sinan/casos", headers=HEADERS,
                           data={**SCOPE, "demo": "true", **extra, "file": (io.BytesIO(content), "cases.csv")})
    with patch.object(threading.Thread, "start"):
        assert upload(b"a" * (sinan_import.MAX_BYTES + 1)).status_code == 413
        assert upload(csv_bytes(), demo="false").status_code == 400
        assert upload(csv_bytes()).status_code == 202


def test_api_map_has_only_municipal_aggregate_never_fabricated_case_points(app):
    store = Store(app.config["SINAN_STORAGE_PATH"])
    job = new_job(store, "None:admin")
    sinan_import.run_api(store, job, SCOPE, fetch_page=lambda **_: page(1, 0, True), delay=0)
    client = app.test_client()
    login(client)
    data = client.get(f"{BASE}/{job}/mapa").json
    assert data["count"] == 1 and data["kind"] == "api" and data["points"] == []


def test_real_background_thread_returns_without_waiting_for_source_and_can_be_cancelled(app):
    entered, release = threading.Event(), threading.Event()
    def fetch(**_):
        entered.set()
        release.wait(3)
        return page(1, 0, True)
    client = app.test_client()
    login(client)
    with patch.object(sinan, "fetch_page", side_effect=fetch):
        response = client.post(BASE, json=SCOPE, headers=HEADERS)
        try:
            assert response.status_code == 202
            assert entered.wait(1)
            job_id = response.json["job"]["id"]
            # The HTTP response and this independent read are available while
            # the only worker is still waiting on an external service.
            assert client.get(f"{BASE}/{job_id}").json["job"]["status"] == "running"
            assert client.post(f"{BASE}/{job_id}/cancelar", headers=HEADERS).status_code == 200
        finally:
            release.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            job = client.get(f"{BASE}/{job_id}").json["job"]
            if job["status"] != "running":
                break
            time.sleep(.01)
        assert job["status"] == "cancelled"


def test_oversized_body_is_rejected_before_global_form_processing(app):
    entered = []
    @app.before_request
    def other_module():
        entered.append(True)
    client = app.test_client()
    response = client.post("/api/vigilancia/sinan/casos", data=b"x" * (sinan_import.MAX_BYTES + 65537), content_type="application/octet-stream")
    assert response.status_code == 413
    assert entered == []


def test_api_export_preserves_partial_flag_and_snapshot_source(store):
    job_id = new_job(store)
    sinan_import.run_api(store, job_id, SCOPE, fetch_page=lambda **_: page(), max_records=10, delay=0)
    output = "".join(sinan_import.export_rows(store.get(job_id, "admin")))
    data = list(csv.DictReader(io.StringIO(output.lstrip("\ufeff")), delimiter=";"))
    assert data[0]["situacao"] == "partial"
    assert data[0]["fonte"] == sinan.DISEASES["dengue"]["api_url"]
    assert data[0]["quantidade"] == "10"


def test_current_completed_snapshot_stays_accessible_after_ten_failed_refreshes(store):
    current = new_job(store)
    store.finish(current, "completed", {"total": 1})
    for _ in range(11):
        job = new_job(store)
        store.finish(job, "failed")
    listing = store.list("admin", **SCOPE)
    assert len(listing["jobs"]) == 10
    assert current in [job["id"] for job in listing["jobs"]]
