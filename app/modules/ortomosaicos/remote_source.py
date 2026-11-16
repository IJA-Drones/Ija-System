"""Read verified large originals through bounded GDAL HTTP ranges, never a disk copy."""
import base64
import os
from itertools import islice
from contextlib import contextmanager
from pathlib import Path

from app.shared import skybox


@contextmanager
def remote_source(row, folder, verified_etag):
    path = skybox.remote_path_from_marker(row.original_path)
    # Pin all range requests to the exact object whose SHA-256 was verified.
    if not verified_etag or verified_etag.startswith('W/') or '\n' in verified_etag or '\r' in verified_etag:
        raise ValueError('O Skybox não forneceu uma versão estável do original para leitura parcial.')
    with skybox._request('GET', path, headers={'Range': 'bytes=0-15', 'If-Match': verified_etag}, stream=True) as response:
        if (response.status_code != 206
                or response.headers.get('Content-Range') != f'bytes 0-15/{row.tamanho_bytes}'
                or response.headers.get('ETag') != verified_etag):
            raise ValueError('O Skybox não confirmou a leitura parcial da versão verificada do original.')
        if sum(len(chunk) for chunk in islice(response.iter_content(16), 2)) != 16:
            raise ValueError('A leitura parcial do original retornou tamanho inválido.')
    username, password = skybox._auth()
    authorization = base64.b64encode(f'{username}:{password}'.encode()).decode('ascii')
    headers = Path(folder) / '.skybox-headers'
    # Never put credentials in URLs, argv, logs, or persistent raster metadata.
    with open(headers, 'x', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        stream.write(f'Authorization: Basic {authorization}\nIf-Match: {verified_etag}\n')
    try:
        yield '/vsicurl/' + skybox._remote_url(path), {
            'GDAL_HTTP_HEADER_FILE': str(headers),
            'CPL_VSIL_CURL_AUTHORIZATION_HEADER_ALLOWED_IF_REDIRECT': 'NO',
            'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
            'CPL_VSIL_CURL_ALLOWED_EXTENSIONS': '.tif,.tiff',
            'GDAL_HTTP_MULTIRANGE': 'SERIAL',
            'GDAL_HTTP_MAX_RETRY': '3', 'GDAL_HTTP_RETRY_DELAY': '2',
            'GDAL_HTTP_CONNECTTIMEOUT': '30', 'GDAL_HTTP_TIMEOUT': '120',
            'CPL_VSIL_CURL_CHUNK_SIZE': str(1024 * 1024),
            'CPL_VSIL_CURL_CACHE_SIZE': str(128 * 1024 * 1024),
            'VSI_CACHE': 'FALSE',
        }
    finally:
        headers.unlink(missing_ok=True)
