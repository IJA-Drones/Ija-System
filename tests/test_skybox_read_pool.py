from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from flask import Flask
from app.shared import skybox


@pytest.fixture
def pooled(monkeypatch):
    app = Flask(__name__)
    app.config.update(SKYBOX_WEBDAV_URL='https://storage.invalid/dav',
                      SKYBOX_USERNAME='test', SKYBOX_APP_PASSWORD='test-only')
    sessions, calls = [], []
    class Session:
        def __init__(self):
            self.cookies = {'previous': 'cookie'}
            self.closed = False
            sessions.append(self)
        def close(self): self.closed = True
        def request(self, method, url, **kwargs):
            assert not self.cookies
            calls.append((self, method, url, kwargs))
            self.cookies['previous'] = 'cookie'
            return 'response'
    monkeypatch.setattr(skybox, '_read_connections', threading.local())
    monkeypatch.setattr(skybox.requests, 'Session', Session)
    return app, sessions, calls


def test_ranges_reuse_session_without_retaining_cookies(pooled):
    app, sessions, calls = pooled
    with app.app_context():
        for i in range(3):
            assert skybox._request('GET', 'private/cog.tif', reuse_connection=True,
                headers={'Range': f'bytes={i*100}-{i*100+99}'}, stream=True) == 'response'
    assert len(sessions) == 1
    assert all(c[3]['timeout'] == skybox.REQUEST_TIMEOUT and c[3]['stream'] for c in calls)
    assert calls[-1][3]['headers']['Range'] == 'bytes=200-299'


def test_configuration_change_closes_old_connection(pooled):
    app, sessions, calls = pooled
    with app.app_context():
        skybox._request('HEAD', 'cog.tif', reuse_connection=True)
        app.config['SKYBOX_APP_PASSWORD'] = 'rotated-test-only'
        skybox._request('HEAD', 'cog.tif', reuse_connection=True)
    assert len(sessions) == 2 and sessions[0].closed
    assert calls[-1][3]['auth'][1] == 'rotated-test-only'


def test_sessions_are_not_shared_between_concurrent_threads(pooled):
    app, sessions, _ = pooled
    barrier = threading.Barrier(2)
    def read():
        with app.app_context():
            skybox._request('GET', 'cog.tif', reuse_connection=True)
            barrier.wait(timeout=5)
            skybox._request('GET', 'cog.tif', reuse_connection=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: read(), range(2)))
    assert len(sessions) == 2


def test_unrelated_requests_and_mutations_keep_existing_transport(pooled, monkeypatch):
    app, sessions, _ = pooled
    requests = []
    monkeypatch.setattr(skybox.requests, 'request', lambda *a, **kw: requests.append((a,kw)))
    with app.app_context():
        skybox._request('GET', 'other-file')
        skybox._request('PUT', 'other-file', reuse_connection=True)
    assert len(requests) == 2 and not sessions
