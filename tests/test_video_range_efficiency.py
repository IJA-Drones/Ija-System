"""Video seeking must stop consuming upstream as soon as the range is sent."""
import pytest
from flask import Flask
from app.shared import skybox
from app.modules.piloto_os import routes


class Upstream:
    headers = {'Content-Length': '16', 'Content-Type': 'video/mp4'}

    def __init__(self):
        self.reads = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        for chunk in (b'abcd', b'efgh', b'ijkl', b'mnop'):
            self.reads += 1
            yield chunk


@pytest.mark.parametrize('builder', [
    skybox._build_range_response_from_full_upstream,
    routes._build_webdav_range_response_from_full_upstream,
])
@pytest.mark.parametrize('requested,expected,reads', [
    ('bytes=0-3', b'abcd', 1),
    ('bytes=5-6', b'fg', 2),
    ('bytes=-4', b'mnop', 4),
])
def test_range_fallback_does_not_read_an_extra_chunk(builder, requested, expected, reads):
    app = Flask(__name__)
    upstream = Upstream()
    with app.test_request_context('/'):
        response = builder(upstream, 'video.mp4', requested)
        assert response.status_code == 206
        assert b''.join(response.response) == expected
        assert response.content_length == len(expected)
        assert upstream.reads == reads
        assert upstream.closed


@pytest.mark.parametrize('builder', [
    skybox._build_range_response_from_full_upstream,
    routes._build_webdav_range_response_from_full_upstream,
])
def test_video_disconnect_closes_upstream(builder):
    app = Flask(__name__)
    upstream = Upstream()
    with app.test_request_context('/'):
        response = builder(upstream, 'video.mp4', 'bytes=0-15')
        iterator = iter(response.response)
        assert next(iterator) == b'abcd'
        response.close()
        assert upstream.closed
        assert upstream.reads == 1


@pytest.mark.parametrize('backend', ['skybox', 'webdav'])
def test_partial_video_read_uses_one_request_and_forwards_cache_headers(monkeypatch, backend):
    app = Flask(__name__)
    upstream = Upstream()
    upstream.status_code = 206
    upstream.headers = {'Content-Length': '4', 'Content-Range': 'bytes 4-7/16',
                        'Content-Type': 'video/mp4', 'ETag': '"v1"'}
    upstream.iter_content = lambda chunk_size: iter([b'efgh'])
    calls = []

    def get(*args, **kwargs):
        calls.append(kwargs)
        return upstream

    if backend == 'skybox':
        monkeypatch.setattr(skybox, 'skybox_enabled', lambda: True)
        monkeypatch.setattr(skybox, '_request', get)
    else:
        monkeypatch.setattr(routes, '_webdav_config', lambda: ('https://example.invalid', None))
        monkeypatch.setattr(routes, '_webdav_url_for_remote_path', lambda path: 'https://example.invalid/video.mp4')
        monkeypatch.setattr(routes.requests, 'get', get)

    with app.test_request_context('/', headers={'If-None-Match': '"v0"'}):
        if backend == 'skybox':
            response = skybox.stream_skybox_file('skybox://video.mp4', 'bytes=4-7',
                conditional_headers={'If-None-Match': '"v0"'})
        else:
            response = routes._stream_webdav_file('webdav://video.mp4', 'bytes=4-7')
        assert b''.join(response.response) == b'efgh'
        assert response.status_code == 206
        assert response.headers['Content-Range'] == 'bytes 4-7/16'
        assert response.headers['ETag'] == '"v1"'
        assert len(calls) == 1
        assert calls[0]['stream'] is True
        assert calls[0]['headers'] == {'Range': 'bytes=4-7', 'If-None-Match': '"v0"'}
        assert upstream.closed
