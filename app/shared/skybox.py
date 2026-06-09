import mimetypes
import os
from urllib.parse import quote

import requests
from flask import Response, current_app, stream_with_context


SKYBOX_MARKER_PREFIX = "skybox://"
REQUEST_TIMEOUT = (15, 300)
STREAM_CHUNK_SIZE = 1024 * 1024


class SkyboxError(RuntimeError):
    pass


def skybox_enabled():
    return bool(_setting("SKYBOX_WEBDAV_URL") and _setting("SKYBOX_USERNAME") and _setting("SKYBOX_APP_PASSWORD"))


def is_skybox_path(value):
    return str(value or "").startswith(SKYBOX_MARKER_PREFIX)


def build_skybox_marker(remote_path):
    return f"{SKYBOX_MARKER_PREFIX}{_clean_remote_path(remote_path)}"


def remote_path_from_marker(value):
    value = str(value or "").strip()
    if not is_skybox_path(value):
        return _clean_remote_path(value)
    return _clean_remote_path(value[len(SKYBOX_MARKER_PREFIX):])


def upload_file_to_skybox(file_storage, remote_path):
    if not skybox_enabled():
        raise SkyboxError("Skybox nao esta configurado.")

    remote_path = _clean_remote_path(remote_path)
    _ensure_parent_collections(remote_path)

    stream = file_storage.stream
    try:
        stream.seek(0)
    except Exception:
        pass

    response = _request(
        "PUT",
        remote_path,
        data=stream,
        headers={"Content-Type": file_storage.mimetype or "application/octet-stream"},
    )
    if response.status_code not in (200, 201, 204):
        raise SkyboxError(f"Falha no upload do Skybox ({response.status_code}).")

    return build_skybox_marker(remote_path)


def delete_skybox_file(value):
    if not skybox_enabled():
        return

    response = _request("DELETE", remote_path_from_marker(value))
    if response.status_code in (200, 202, 204, 404):
        return
    raise SkyboxError(f"Falha ao remover arquivo do Skybox ({response.status_code}).")


def stream_skybox_file(value, range_header=None):
    if not skybox_enabled():
        raise SkyboxError("Skybox nao esta configurado.")

    remote_path = remote_path_from_marker(value)
    headers = {}
    if range_header:
        headers["Range"] = range_header

    upstream = _request("GET", remote_path, headers=headers, stream=True)
    if upstream.status_code == 404:
        upstream.close()
        raise SkyboxError("Arquivo nao encontrado no Skybox.")
    if upstream.status_code not in (200, 206):
        status_code = upstream.status_code
        upstream.close()
        raise SkyboxError(f"Falha ao baixar arquivo do Skybox ({status_code}).")

    response_headers = {}
    for header in ("Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"):
        if upstream.headers.get(header):
            response_headers[header] = upstream.headers[header]

    content_type = upstream.headers.get("Content-Type") or mimetypes.guess_type(remote_path)[0] or "application/octet-stream"
    response_headers["Content-Type"] = content_type
    response_headers.setdefault("Accept-Ranges", "bytes")
    response_headers["Content-Disposition"] = f'inline; filename="{os.path.basename(remote_path)}"'

    def generate():
        with upstream:
            for chunk in upstream.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                if chunk:
                    yield chunk

    return Response(
        stream_with_context(generate()),
        status=upstream.status_code,
        headers=response_headers,
        direct_passthrough=True,
    )


def _setting(name):
    return current_app.config.get(name) or os.getenv(name)


def _base_dir():
    return _clean_remote_path(_setting("SKYBOX_BASE_DIR") or "dados ordens de serviço")


def _clean_remote_path(value):
    parts = [part.strip() for part in str(value or "").replace("\\", "/").split("/") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        raise SkyboxError("Caminho remoto invalido.")
    return "/".join(parts)


def _remote_url(remote_path):
    base_url = (_setting("SKYBOX_WEBDAV_URL") or "").strip().rstrip("/")
    if not base_url:
        raise SkyboxError("URL WebDAV do Skybox ausente.")

    encoded = "/".join(quote(part, safe="") for part in _clean_remote_path(remote_path).split("/"))
    return f"{base_url}/{encoded}" if encoded else base_url


def _auth():
    username = (_setting("SKYBOX_USERNAME") or "").strip()
    password = _setting("SKYBOX_APP_PASSWORD") or ""
    if not username or not password:
        raise SkyboxError("Credenciais do Skybox ausentes.")
    return username, password


def _request(method, remote_path, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, _remote_url(remote_path), auth=_auth(), **kwargs)


def _ensure_parent_collections(remote_path):
    parts = _clean_remote_path(remote_path).split("/")[:-1]
    current = []
    for part in parts:
        current.append(part)
        response = _request("MKCOL", "/".join(current))
        if response.status_code in (201, 405):
            continue
        if response.status_code == 409:
            continue
        raise SkyboxError(f"Falha ao preparar pasta no Skybox ({response.status_code}).")


def build_os_media_remote_path(os_id, filename):
    return "/".join([_base_dir(), str(os_id), filename])


def build_os_video_remote_path(os_id, filename):
    return build_os_media_remote_path(os_id, filename)
