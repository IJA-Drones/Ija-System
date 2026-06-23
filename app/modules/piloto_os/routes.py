import json
import mimetypes
import os
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote, unquote, urlsplit

import requests
from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import lazyload
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import OrdemServico, Solicitacao
from app.modules.piloto_os.dosagem import build_piloto_dosagem_context, salvar_piloto_dosagem_planejada
from app.modules.piloto_os.exporters import build_admin_os_excel_v2_export, build_admin_os_pdf_v2_export
from app.modules.piloto_os.service import (
    PilotoOsError,
    build_admin_os_form_context,
    build_piloto_os_form_context,
    build_piloto_os_context,
    build_piloto_os_historico_context,
    concluir_os_piloto,
    get_os_complementary_image_path_for_user,
    get_os_principal_image_path_for_user,
    get_os_video_path_for_user,
    get_piloto_drone_payload,
    is_piloto_os_user,
    salvar_admin_os_form,
    salvar_piloto_os_form,
)
from app.shared.access import ADMIN_PANEL_VIEW_TYPES, can_access_regiao
from app.shared.skybox import (
    SkyboxError,
    build_os_video_remote_path,
    build_skybox_marker,
    is_skybox_path,
    stream_skybox_file,
)


WEBDAV_MARKER_PREFIX = "webdav://"
DEFAULT_WEBDAV_CONNECT_TIMEOUT_SECONDS = 30
DEFAULT_WEBDAV_TRANSFER_TIMEOUT_SECONDS = 3600
DEFAULT_WEBDAV_UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
MEDIA_STORAGE_UNAVAILABLE_MESSAGE = (
    "Nao foi possivel acessar o armazenamento de midias agora. "
    "Tente novamente em instantes."
)
MEDIA_DATABASE_ERROR_MESSAGE = (
    "A midia foi processada, mas nao foi possivel atualizar o registro da OS. "
    "Atualize a pagina e tente novamente."
)
MEDIA_UNEXPECTED_ERROR_MESSAGE = (
    "Nao foi possivel concluir esta acao agora. "
    "Tente novamente em instantes."
)
VIDEO_BACKGROUND_UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
VIDEO_BACKGROUND_UPLOAD_JOBS = {}
VIDEO_BACKGROUND_UPLOAD_LOCK = threading.Lock()
VIDEO_BACKGROUND_UPLOAD_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("VIDEO_BACKGROUND_UPLOAD_WORKERS", "2"))
)


def _require_piloto():
    if not is_piloto_os_user(current_user):
        abort(403)


def _safe_local_redirect(default_endpoint):
    target = (request.form.get("next") or request.args.get("next") or "").strip()
    parsed = urlsplit(target)

    if target.startswith("/") and not target.startswith("//") and not parsed.scheme and not parsed.netloc:
        return redirect(target)

    return redirect(url_for(default_endpoint))


def _require_admin_os_view():
    if getattr(current_user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
        abort(403)


def _require_admin_os_export():
    if getattr(current_user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
        abort(403)


def _ensure_os_region_access(os_id):
    solicitacao = (
        Solicitacao.query
        .options(
            db.selectinload(Solicitacao.usuario),
        )
        .get_or_404(os_id)
    )
    pedido_regiao = getattr(getattr(solicitacao, "usuario", None), "regiao", None)
    if not can_access_regiao(current_user, pedido_regiao):
        abort(403)


def _query_args_without_page():
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args


def _send_local_os_media(media_path, *, as_attachment=False):
    static_root = os.path.abspath(os.path.join(current_app.root_path, "static"))
    abs_path = os.path.abspath(os.path.join(static_root, str(media_path or "").replace("/", os.sep)))
    if os.path.commonpath([static_root, abs_path]) != static_root:
        abort(404)
    if not os.path.isfile(abs_path):
        abort(404)

    return send_file(
        abs_path,
        mimetype=mimetypes.guess_type(abs_path)[0] or "application/octet-stream",
        as_attachment=as_attachment,
        download_name=os.path.basename(abs_path),
        conditional=True,
    )


def _send_os_media(media_path, *, as_attachment=False):
    if _is_webdav_path(media_path):
        try:
            return _stream_webdav_file(media_path, request.headers.get("Range"), as_attachment=as_attachment)
        except requests.RequestException:
            current_app.logger.exception("Erro ao servir midia da OS pelo WebDAV.")
            abort(404)

    if is_skybox_path(media_path):
        try:
            return stream_skybox_file(media_path, request.headers.get("Range"), as_attachment=as_attachment)
        except SkyboxError:
            current_app.logger.exception("Erro ao servir midia da OS pelo Skybox.")
            abort(404)

    return _send_local_os_media(media_path, as_attachment=as_attachment)


def _setting(*names):
    for name in names:
        value = current_app.config.get(name) or os.getenv(name)
        if value:
            return value
    return None


def _setting_int(name, default):
    raw_value = current_app.config.get(name) or os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _webdav_timeout():
    connect_timeout = _setting_int(
        "WEBDAV_CONNECT_TIMEOUT_SECONDS",
        DEFAULT_WEBDAV_CONNECT_TIMEOUT_SECONDS,
    )
    transfer_timeout = _setting_int(
        "WEBDAV_TRANSFER_TIMEOUT_SECONDS",
        DEFAULT_WEBDAV_TRANSFER_TIMEOUT_SECONDS,
    )
    return connect_timeout, None if transfer_timeout <= 0 else transfer_timeout


def _webdav_upload_chunk_size():
    return _setting_int(
        "WEBDAV_UPLOAD_CHUNK_SIZE_BYTES",
        DEFAULT_WEBDAV_UPLOAD_CHUNK_SIZE_BYTES,
    )


def _webdav_config():
    base_url = (_setting("WEBDAV_URL", "SKYBOX_WEBDAV_URL") or "").strip().rstrip("/")
    username = (_setting("WEBDAV_USER", "SKYBOX_USERNAME") or "").strip()
    password = _setting("WEBDAV_PASS", "SKYBOX_APP_PASSWORD") or ""
    if not base_url or not username or not password:
        raise RuntimeError("WEBDAV_URL, WEBDAV_USER e WEBDAV_PASS precisam estar configurados.")
    return base_url, (username, password)


def _is_webdav_path(value):
    return str(value or "").startswith(WEBDAV_MARKER_PREFIX)


def _media_content_type(remote_path, upstream_content_type=None):
    guessed = mimetypes.guess_type(remote_path)[0]
    upstream = (upstream_content_type or "").split(";", 1)[0].strip().lower()
    if guessed and upstream in {"", "application/octet-stream", "binary/octet-stream"}:
        return guessed
    return upstream_content_type or guessed or "application/octet-stream"


def _clean_webdav_remote_path(value):
    parts = [part.strip() for part in str(value or "").replace("\\", "/").split("/") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        abort(404)
    return "/".join(parts)


def _webdav_base_dir():
    return _clean_webdav_remote_path(
        _setting("WEBDAV_BASE_DIR", "SKYBOX_BASE_DIR") or "dados ordens de servi\u00e7o"
    )


def _build_webdav_os_remote_path(os_id, file_name=None):
    parts = [_webdav_base_dir(), str(os_id)]
    if file_name:
        parts.append(file_name)
    return "/".join(part for part in parts if part)


def _build_webdav_marker(os_id, file_name):
    return f"{WEBDAV_MARKER_PREFIX}{_build_webdav_os_remote_path(os_id, file_name)}"


def _webdav_remote_path_from_marker(value):
    remote_path = str(value or "")[len(WEBDAV_MARKER_PREFIX):].replace("\\", "/")
    remote_path = _clean_webdav_remote_path(remote_path)
    if not remote_path:
        abort(404)
    return remote_path


def _webdav_url_for_remote_path(remote_path):
    base_url, _auth = _webdav_config()
    encoded = "/".join(quote(part, safe="") for part in str(remote_path or "").split("/") if part)
    return f"{base_url}/{encoded}" if encoded else base_url


def _delete_webdav_file(value):
    _base_url, auth = _webdav_config()
    remote_path = _webdav_remote_path_from_marker(value)
    response = requests.delete(
        _webdav_url_for_remote_path(remote_path),
        auth=auth,
        timeout=_webdav_timeout(),
    )
    if response.status_code not in (200, 202, 204, 404):
        raise requests.RequestException(f"Falha ao remover arquivo do WebDAV ({response.status_code}).")


def _content_disposition(remote_path, *, as_attachment=False):
    disposition = "attachment" if as_attachment else "inline"
    return f'{disposition}; filename="{os.path.basename(remote_path)}"'


def _stream_webdav_file(value, range_header=None, *, as_attachment=False):
    _base_url, auth = _webdav_config()
    headers = {}
    if range_header:
        headers["Range"] = range_header

    remote_path = _webdav_remote_path_from_marker(value)
    upstream = requests.get(
        _webdav_url_for_remote_path(remote_path),
        auth=auth,
        headers=headers,
        stream=True,
        timeout=_webdav_timeout(),
    )
    if upstream.status_code == 404:
        upstream.close()
        abort(404)
    if upstream.status_code not in (200, 206):
        status_code = upstream.status_code
        upstream.close()
        raise requests.RequestException(f"Falha ao baixar arquivo do WebDAV ({status_code}).")

    if range_header and upstream.status_code == 200:
        ranged_response = _build_webdav_range_response_from_full_upstream(
            upstream,
            remote_path,
            range_header,
            as_attachment=as_attachment,
        )
        if ranged_response is not None:
            return ranged_response

    def generate():
        with upstream:
            for chunk in upstream.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk

    return current_app.response_class(
        generate(),
        status=upstream.status_code,
        headers={
            key: value
            for key, value in {
                "Content-Type": _media_content_type(remote_path, upstream.headers.get("Content-Type")),
                "Content-Length": upstream.headers.get("Content-Length"),
                "Content-Range": upstream.headers.get("Content-Range"),
                "Accept-Ranges": upstream.headers.get("Accept-Ranges") or "bytes",
                "Last-Modified": upstream.headers.get("Last-Modified"),
                "ETag": upstream.headers.get("ETag"),
                "Content-Disposition": _content_disposition(remote_path, as_attachment=as_attachment),
            }.items()
            if value
        },
        direct_passthrough=True,
    )


def _parse_range_header(range_header, total_size):
    if not range_header or not str(range_header).startswith("bytes="):
        return None
    if not total_size or total_size <= 0:
        return None

    range_value = str(range_header).split("=", 1)[1].split(",", 1)[0].strip()
    if "-" not in range_value:
        return None

    start_raw, end_raw = range_value.split("-", 1)
    try:
        if start_raw == "":
            suffix_length = int(end_raw)
            if suffix_length <= 0:
                return None
            start = max(total_size - suffix_length, 0)
            end = total_size - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else total_size - 1
    except ValueError:
        return None

    if start < 0 or start >= total_size:
        return None
    end = min(end, total_size - 1)
    if end < start:
        return None
    return start, end


def _build_webdav_range_response_from_full_upstream(upstream, remote_path, range_header, *, as_attachment=False):
    try:
        total_size = int(upstream.headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        total_size = 0

    parsed_range = _parse_range_header(range_header, total_size)
    if parsed_range is None:
        return None

    start, end = parsed_range
    response_length = end - start + 1
    content_type = _media_content_type(remote_path, upstream.headers.get("Content-Type"))

    def generate():
        remaining_skip = start
        remaining_send = response_length
        with upstream:
            for chunk in upstream.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if remaining_skip:
                    if len(chunk) <= remaining_skip:
                        remaining_skip -= len(chunk)
                        continue
                    chunk = chunk[remaining_skip:]
                    remaining_skip = 0
                if remaining_send <= 0:
                    break
                if len(chunk) > remaining_send:
                    chunk = chunk[:remaining_send]
                remaining_send -= len(chunk)
                yield chunk

    return current_app.response_class(
        generate(),
        status=206,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(response_length),
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Disposition": _content_disposition(remote_path, as_attachment=as_attachment),
        },
        direct_passthrough=True,
    )


def _build_upload_context(os_id):
    if getattr(current_user, "tipo_usuario", None) in ADMIN_PANEL_VIEW_TYPES:
        context = build_admin_os_form_context(current_user, os_id)
    else:
        _require_piloto()
        context = build_piloto_os_form_context(current_user, os_id)

    if context.get("modo_visualizacao"):
        abort(403)
    return context


def _media_error_response(message=MEDIA_UNEXPECTED_ERROR_MESSAGE, status=500):
    return jsonify({"success": False, "error": message}), status


def _build_stream_upload_file_name(os_id, media_prefix):
    encoded_name = (request.headers.get("X-File-Name") or "").strip()
    if not encoded_name:
        return None

    decoded_name = unquote(encoded_name).strip()
    original_file_name = secure_filename(decoded_name)
    if not original_file_name:
        return None

    _root, extension = os.path.splitext(original_file_name)
    if not extension:
        extension = mimetypes.guess_extension(request.headers.get("Content-Type") or "") or ""

    safe_prefix = secure_filename(str(media_prefix or "arquivo")).strip("_") or "arquivo"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return secure_filename(f"{safe_prefix}_os_{os_id}_{stamp}{extension.lower()}")


def _upload_request_stream_to_webdav(os_id, media_prefix):
    file_name = _build_stream_upload_file_name(os_id, media_prefix)
    if not file_name:
        return None, None, jsonify({"success": False, "error": "Header X-File-Name ausente ou invalido."}), 400

    _base_url, auth = _webdav_config()
    base_remote_path = _webdav_base_dir()
    folder_remote_path = _build_webdav_os_remote_path(os_id)
    file_remote_path = _build_webdav_os_remote_path(os_id, file_name)
    base_url = _webdav_url_for_remote_path(base_remote_path)
    folder_url = _webdav_url_for_remote_path(folder_remote_path)
    file_url = _webdav_url_for_remote_path(file_remote_path)
    content_type = _media_content_type(file_name, request.headers.get("Content-Type"))

    try:
        requests.request("MKCOL", base_url, auth=auth, timeout=_webdav_timeout())
        requests.request("MKCOL", folder_url, auth=auth, timeout=_webdav_timeout())
    except requests.RequestException:
        current_app.logger.info("MKCOL WebDAV ignorado para OS %s; a pasta pode ja existir.", os_id, exc_info=True)

    upload_headers = {"Content-Type": content_type}
    content_length = request.content_length
    if content_length is not None:
        upload_headers["Content-Length"] = str(content_length)

    def stream_chunks():
        chunk_size = max(64 * 1024, _webdav_upload_chunk_size())
        while True:
            chunk = request.stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

    class SizedRequestStream:
        def __iter__(self):
            return stream_chunks()

        def __len__(self):
            return int(content_length or 0)

    upload_body = SizedRequestStream() if content_length is not None else stream_chunks()

    try:
        response = requests.put(
            file_url,
            data=upload_body,
            headers=upload_headers,
            auth=auth,
            timeout=_webdav_timeout(),
        )
    except requests.Timeout:
        return None, None, jsonify({
            "success": False,
            "error": "Tempo limite ao enviar o arquivo para o WebDAV. O Skybox/Nextcloud demorou demais para receber os dados.",
        }), 504
    except requests.RequestException as exc:
        current_app.logger.exception("Falha de conexao no upload WebDAV da OS %s para %s", os_id, file_url)
        return None, None, jsonify({
            "success": False,
            "error": MEDIA_STORAGE_UNAVAILABLE_MESSAGE,
        }), 502
    if response.status_code not in (200, 201, 204):
        current_app.logger.warning(
            "Falha no upload WebDAV da OS %s para %s: status=%s body=%s",
            os_id,
            file_url,
            response.status_code,
            response.text[:500],
        )
        return None, None, jsonify({
            "success": False,
            "error": MEDIA_STORAGE_UNAVAILABLE_MESSAGE,
            "status_code": response.status_code,
        }), 502

    return file_name, file_url, None, None


def _build_ordem_servico_upload_stub(solicitacao):
    return OrdemServico(
        solicitacao_id=solicitacao.id,
        equipe_id=solicitacao.equipe_id,
        identificador_os="",
        respondido_por="",
        respondido_em=None,
        situacao_aplicacao="",
        larva_visualizada="",
        retornar_proxima_semana_monitorar_larvas="NAO",
        distrito_administrativo="",
        nome_rf_ace_responsavel_os="",
        criadouro_os_tipo_volume="",
        data_aplicacao=None,
        hora_inicio_aplicacao=None,
        hora_termino_aplicacao=None,
        tratamento_adicional_realizado="",
        quantos_quais="",
        descricao_produto="",
        formulacao_produto="",
        dosagem_g_10l="",
        tipo_aplicacao="",
        quantidade_produto_administrada_ml=None,
        pulverizacao_area_l_ha=None,
        prefixo_aeronave_pulverizacao="",
        prefixo_aeronave_monitoramento="",
        quantidade_videos_registradas=None,
        quantidade_imagens_registradas=None,
        ponta_pulverizacao="",
        temperatura_c=None,
        umidade_relativa_pct=None,
        velocidade_vento_kmh=None,
        motivo_nao_realizacao="",
        observacoes="",
        piloto="",
        assinatura_piloto="",
        auxiliar="",
        proprietario_ou_preposto="",
        assinatura_proprietario_ou_preposto="",
        drone_id=None,
        drone_monitoramento_id=None,
        drone_denominacao="",
        drone_modelo="",
        drone_numero_serie="",
        drone_registro_anatel="",
        drone_registro_anac="",
        drone_monitoramento_denominacao="",
        drone_monitoramento_modelo="",
        drone_monitoramento_numero_serie="",
        drone_monitoramento_registro_anatel="",
        drone_monitoramento_registro_anac="",
    )


def _query_ordem_servico_for_upload(solicitacao_id, *, lock=False):
    query = (
        OrdemServico.query
        .options(lazyload("*"))
        .filter_by(solicitacao_id=solicitacao_id)
    )
    if lock:
        query = query.with_for_update(of=OrdemServico)
    return query


def _video_upload_jobs_dir():
    path = os.path.join(current_app.instance_path, "video_upload_jobs")
    os.makedirs(path, exist_ok=True)
    return path


def _now_epoch():
    return time.time()


def _set_video_upload_job(job_id, **updates):
    with VIDEO_BACKGROUND_UPLOAD_LOCK:
        job = VIDEO_BACKGROUND_UPLOAD_JOBS.get(job_id)
        if not job:
            return None
        job.update(updates)
        job["updated_at"] = _now_epoch()
        return dict(job)


def _get_video_upload_job(job_id):
    with VIDEO_BACKGROUND_UPLOAD_LOCK:
        job = VIDEO_BACKGROUND_UPLOAD_JOBS.get(job_id)
        return dict(job) if job else None


def _build_video_upload_status_from_os(os_id):
    if getattr(current_user, "tipo_usuario", None) in ADMIN_PANEL_VIEW_TYPES:
        context = build_admin_os_form_context(current_user, os_id)
    else:
        context = build_piloto_os_form_context(current_user, os_id)

    ordem = context.get("ordem")
    if getattr(ordem, "video", None):
        return {
            "success": True,
            "job_id": None,
            "status": "success",
            "progress": 100,
            "message": "Video enviado com sucesso.",
            "os_id": os_id,
            "file_name": os.path.basename(str(ordem.video or "").replace("\\", "/")),
            "media_url": url_for("main.os_video", os_id=os_id),
        }

    return {
        "success": True,
        "job_id": None,
        "status": "uploading",
        "progress": 1,
        "message": "Video ainda em processamento. Voce pode continuar usando o sistema.",
        "os_id": os_id,
        "file_name": None,
        "media_url": None,
    }


def _create_video_upload_job(*, os_id, user_id, file_name, original_name, content_type, temp_path, total_bytes):
    job_id = uuid.uuid4().hex
    now = _now_epoch()
    with VIDEO_BACKGROUND_UPLOAD_LOCK:
        VIDEO_BACKGROUND_UPLOAD_JOBS[job_id] = {
            "id": job_id,
            "os_id": os_id,
            "user_id": user_id,
            "file_name": file_name,
            "original_name": original_name,
            "content_type": content_type,
            "temp_path": temp_path,
            "total_bytes": total_bytes,
            "status": "queued",
            "progress": 0,
            "message": "Video recebido. Aguardando envio para o Skybox.",
            "media_url": None,
            "created_at": now,
            "updated_at": now,
        }
    return job_id


def _save_video_request_to_temp(file_name):
    temp_path = os.path.join(_video_upload_jobs_dir(), f"{uuid.uuid4().hex}_{file_name}")
    total_bytes = 0
    chunk_size = max(64 * 1024, _webdav_upload_chunk_size())
    with open(temp_path, "wb") as temp_file:
        while True:
            chunk = request.stream.read(chunk_size)
            if not chunk:
                break
            temp_file.write(chunk)
            total_bytes += len(chunk)
    return temp_path, total_bytes


def _file_contains_bytes(path, needle, *, chunk_size=1024 * 1024):
    overlap = max(len(needle) - 1, 0)
    previous_tail = b""
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            data = previous_tail + chunk
            if needle in data:
                return True
            previous_tail = data[-overlap:] if overlap else b""
    return False


def _validate_uploaded_video_file(temp_path, file_name):
    extension = os.path.splitext(str(file_name or ""))[1].lower()
    if extension in {".mp4", ".mov", ".m4v"} and not _file_contains_bytes(temp_path, b"moov"):
        return "O arquivo de video chegou incompleto ou corrompido. Envie novamente o video original."

    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return None

    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                temp_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        current_app.logger.info("Validacao ffprobe ignorada para video %s.", file_name, exc_info=True)
        return None

    if result.returncode != 0:
        current_app.logger.warning(
            "Video invalido no upload %s: %s",
            file_name,
            (result.stderr or result.stdout or "").strip()[:500],
        )
        return "O arquivo de video chegou incompleto ou corrompido. Envie novamente o video original."

    return None


def _run_video_upload_job(app, job_id):
    with app.app_context():
        job = _get_video_upload_job(job_id)
        if not job:
            return

        temp_path = job["temp_path"]
        os_id = job["os_id"]
        file_name = job["file_name"]
        file_remote_path = build_os_video_remote_path(os_id, file_name)
        file_url = _webdav_url_for_remote_path(file_remote_path)
        total_bytes = max(1, int(job.get("total_bytes") or os.path.getsize(temp_path) or 1))

        try:
            _set_video_upload_job(
                job_id,
                status="uploading",
                progress=1,
                message="Enviando video para o Skybox em segundo plano.",
            )

            _base_url, auth = _webdav_config()
            try:
                parent_parts = []
                for part in file_remote_path.split("/")[:-1]:
                    parent_parts.append(part)
                    requests.request(
                        "MKCOL",
                        _webdav_url_for_remote_path("/".join(parent_parts)),
                        auth=auth,
                        timeout=_webdav_timeout(),
                    )
            except requests.RequestException:
                current_app.logger.info("MKCOL WebDAV ignorado para video em background da OS %s.", os_id, exc_info=True)

            uploaded_bytes = 0

            class ProgressFileStream:
                def __iter__(self):
                    nonlocal uploaded_bytes
                    with open(temp_path, "rb") as video_file:
                        while True:
                            chunk = video_file.read(VIDEO_BACKGROUND_UPLOAD_CHUNK_SIZE_BYTES)
                            if not chunk:
                                break
                            uploaded_bytes += len(chunk)
                            progress = min(95, max(1, int((uploaded_bytes / total_bytes) * 95)))
                            _set_video_upload_job(
                                job_id,
                                progress=progress,
                                message=f"Enviando video para o Skybox... {progress}%",
                            )
                            yield chunk

                def __len__(self):
                    return total_bytes

            response = requests.put(
                file_url,
                data=ProgressFileStream(),
                headers={
                    "Content-Type": job.get("content_type") or "application/octet-stream",
                    "Content-Length": str(total_bytes),
                },
                auth=auth,
                timeout=_webdav_timeout(),
            )
            if response.status_code not in (200, 201, 204):
                current_app.logger.warning(
                    "Falha no upload de video background da OS %s: status=%s body=%s",
                    os_id,
                    response.status_code,
                    response.text[:500],
                )
                raise RuntimeError("Falha ao enviar video para o Skybox.")

            _set_video_upload_job(job_id, progress=97, message="Atualizando registro da OS.")
            ordem, _error_response = _get_or_create_ordem_for_upload({"solicitacao": Solicitacao.query.get(os_id)}, lock=True)
            ordem.video = build_skybox_marker(file_remote_path)
            if not ordem.quantidade_videos_registradas or ordem.quantidade_videos_registradas < 1:
                ordem.quantidade_videos_registradas = 1
            db.session.commit()

            _set_video_upload_job(
                job_id,
                status="success",
                progress=100,
                message="Video enviado com sucesso.",
                media_url=f"/os/{os_id}/video",
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro no upload de video em background da OS %s.", os_id)
            _set_video_upload_job(
                job_id,
                status="error",
                message="Nao foi possivel concluir o envio do video.",
            )
        finally:
            try:
                if temp_path and os.path.isfile(temp_path):
                    os.remove(temp_path)
            except OSError:
                current_app.logger.info("Falha ignorada ao remover temporario de video %s.", temp_path, exc_info=True)


def _get_or_create_ordem_for_upload(context, *, lock=False):
    solicitacao = context["solicitacao"]
    solicitacao_id = solicitacao.id

    with db.session.no_autoflush:
        ordem = _query_ordem_servico_for_upload(solicitacao_id, lock=lock).first()
    if ordem:
        return ordem, None

    ordem = _build_ordem_servico_upload_stub(solicitacao)
    db.session.add(ordem)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        ordem = _query_ordem_servico_for_upload(solicitacao_id, lock=lock).first()
        if ordem is None:
            raise

    return ordem, None


def _parse_media_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _delete_os_media_path(os_id, media_path):
    if not media_path:
        return

    if _is_webdav_path(media_path):
        try:
            _delete_webdav_file(media_path)
        except requests.RequestException:
            current_app.logger.info("Falha ignorada ao remover arquivo WebDAV da OS %s.", os_id, exc_info=True)
        return

    if is_skybox_path(media_path):
        try:
            from app.shared.skybox import delete_skybox_file

            delete_skybox_file(media_path)
        except SkyboxError:
            current_app.logger.info("Falha ignorada ao remover arquivo Skybox da OS %s.", os_id, exc_info=True)
        return

    static_root = os.path.abspath(os.path.join(current_app.root_path, "static"))
    abs_path = os.path.abspath(os.path.join(static_root, str(media_path).replace("/", os.sep)))
    if os.path.commonpath([static_root, abs_path]) == static_root and os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            current_app.logger.info("Falha ignorada ao remover arquivo local da OS %s.", os_id, exc_info=True)


def _redirect_from_piloto_os_error(exc, *, os_id=None):
    if exc.redirect_endpoint in {"main.piloto_os_formulario_view", "main.piloto_os_dosagem"} and os_id is not None:
        return redirect(url_for(exc.redirect_endpoint, os_id=os_id))
    return redirect(url_for(exc.redirect_endpoint))


def register_routes(bp):
    @bp.route("/piloto/os", methods=["GET"], endpoint="piloto_os")
    @login_required
    def piloto_os():
        _require_piloto()

        google_maps_key = (
            os.getenv("KEY_API_GOOGLE_MAPS")
            or current_app.config.get("GOOGLE_MAPS_API_KEY", "")
        )

        try:
            context = build_piloto_os_context(current_user, request.args, google_maps_key)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        if context["sem_equipe_ativa"]:
            flash("Voce ainda nao esta vinculado a nenhuma equipe ativa.", "warning")

        return render_template(
            "piloto_os.html",
            pedidos=context["pedidos"],
            paginacao=context["paginacao"],
            status_ok=context["status_ok"],
            pilot_team_nome=context["pilot_team_nome"],
            pilot_team_regiao=context["pilot_team_regiao"],
            pilot_team_papel=context["pilot_team_papel"],
            pilot_regiao_principal=context["pilot_regiao_principal"],
            pilot_regiao_alternativa=context["pilot_regiao_alternativa"],
            google_maps_key=context["google_maps_key"],
            drones_equipe=context["drones_equipe"],
            baterias_equipe=context["baterias_equipe"],
            veiculos_equipe=context["veiculos_equipe"],
            busca=context["busca"],
            data_hoje=context["data_hoje"],
            pagination_args={k: v for k, v in request.args.items() if k != "page"},
        )

    @bp.route("/piloto/dosagem", methods=["GET"], endpoint="piloto_dosagem")
    @login_required
    def piloto_dosagem():
        _require_piloto()
        return render_template("piloto_dosagem.html", **build_piloto_dosagem_context(current_user))

    @bp.route("/piloto/os/<int:os_id>/dosagem", methods=["GET", "POST"], endpoint="piloto_os_dosagem")
    @login_required
    def piloto_os_dosagem(os_id):
        _require_piloto()

        if request.method == "POST":
            try:
                flash(
                    salvar_piloto_dosagem_planejada(
                        current_user,
                        os_id,
                        request.form.get("calculo_dosagem_planejado"),
                    ),
                    "success",
                )
                return redirect(url_for("main.piloto_os_dosagem", os_id=os_id))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                return _redirect_from_piloto_os_error(exc, os_id=os_id)

        try:
            return render_template(
                "piloto_dosagem.html",
                **build_piloto_dosagem_context(current_user, os_id=os_id),
            )
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return _redirect_from_piloto_os_error(exc, os_id=os_id)

    @bp.route("/piloto/os/historico", methods=["GET"], endpoint="piloto_os_historico")
    @login_required
    def piloto_os_historico():
        _require_piloto()

        try:
            context = build_piloto_os_historico_context(current_user, request.args)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return _redirect_from_piloto_os_error(exc)

        return render_template(
            "piloto_os_historico.html",
            **context,
        )

    @bp.route("/piloto/os/<int:os_id>/concluir", methods=["POST"], endpoint="piloto_concluir_os")
    @login_required
    def piloto_concluir_os(os_id):
        _require_piloto()

        try:
            flash(concluir_os_piloto(current_user, os_id), "success")
        except PilotoOsError as exc:
            flash(str(exc), exc.category)

        return _safe_local_redirect("main.piloto_os")

    @bp.route("/piloto/os/formulario", methods=["GET"], endpoint="piloto_os_formulario_redirect")
    @login_required
    def piloto_os_formulario_redirect():
        _require_piloto()

        os_id = request.args.get("os_id", type=int) or request.args.get("solicitacao_id", type=int)
        if not os_id:
            flash("Selecione uma OS para preencher o formulario.", "info")
            return redirect(url_for("main.piloto_os"))

        return redirect(url_for("main.piloto_os_formulario_view", os_id=os_id))

    @bp.route("/piloto/os/<int:os_id>/formulario", methods=["GET", "POST"], endpoint="piloto_os_formulario_view")
    @login_required
    def piloto_os_formulario_view(os_id):
        _require_piloto()

        try:
            context = build_piloto_os_form_context(current_user, os_id)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return _redirect_from_piloto_os_error(exc, os_id=os_id)

        if request.method == "POST":
            if context["modo_visualizacao"]:
                flash("Esta OS ja foi concluida e nao pode mais ser editada pelo piloto.", "warning")
                return redirect(url_for("main.piloto_os_formulario_view", os_id=os_id))

            try:
                flash(
                    salvar_piloto_os_form(
                        current_user,
                        os_id,
                        request.form,
                        request.files,
                        current_app.root_path,
                    ),
                    "success",
                )
                return redirect(url_for("main.piloto_os"))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                return _redirect_from_piloto_os_error(exc, os_id=os_id)
            except Exception:
                from app.extensions import db

                db.session.rollback()
                current_app.logger.exception("Erro ao salvar formulario da OS %s", os_id)
                flash("Erro ao salvar o formulario. Verifique os campos e tente novamente.", "danger")

        return render_template(
            "piloto_os_formulario.html",
            **context,
            url_voltar=url_for("main.piloto_os"),
            form_action=url_for("main.piloto_os_formulario_view", os_id=os_id),
        )

    @bp.route("/os/<int:os_id>/video", methods=["GET"], endpoint="os_video")
    @login_required
    def os_video(os_id):
        try:
            video_path = get_os_video_path_for_user(current_user, os_id)
        except PilotoOsError as exc:
            abort(404 if "video" in str(exc).lower() else 403)

        return _send_os_media(video_path, as_attachment=request.args.get("download") == "1")

    @bp.route("/os/<int:os_id>/imagem-principal", methods=["GET"], endpoint="os_imagem_principal")
    @login_required
    def os_imagem_principal(os_id):
        try:
            image_path = get_os_principal_image_path_for_user(current_user, os_id)
        except PilotoOsError as exc:
            abort(404 if "foto" in str(exc).lower() or "imagem" in str(exc).lower() else 403)

        return _send_os_media(image_path)

    @bp.route("/os/<int:os_id>/imagem-complementar/<int:image_index>", methods=["GET"], endpoint="os_imagem_complementar")
    @login_required
    def os_imagem_complementar(os_id, image_index):
        try:
            image_path = get_os_complementary_image_path_for_user(current_user, os_id, image_index)
        except PilotoOsError as exc:
            abort(404 if "imagem" in str(exc).lower() else 403)

        return _send_os_media(image_path)

    @bp.route("/piloto/api/drone/<int:drone_id>", methods=["GET"], endpoint="piloto_api_drone")
    @login_required
    def piloto_api_drone(drone_id):
        _require_piloto()

        try:
            return jsonify(get_piloto_drone_payload(current_user, drone_id))
        except PilotoOsError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/api/os/<int:os_id>/upload-stream", methods=["PUT"], endpoint="os_upload_stream")
    @login_required
    def os_upload_stream(os_id):
        try:
            context = _build_upload_context(os_id)
            _ordem_existente, error_response = _get_or_create_ordem_for_upload(context)
            if error_response is not None:
                return error_response
            db.session.commit()

            file_name, file_url, error_response, error_status = _upload_request_stream_to_webdav(os_id, "principal")
            if error_response is not None:
                return error_response, error_status

            ordem, error_response = _get_or_create_ordem_for_upload(context, lock=True)
            if error_response is not None:
                return error_response

            ordem.imagem_principal = _build_webdav_marker(os_id, file_name)
            if not ordem.quantidade_imagens_registradas or ordem.quantidade_imagens_registradas < 1:
                ordem.quantidade_imagens_registradas = 1
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Upload concluido com sucesso.",
                "file_name": file_name,
                "webdav_url": file_url,
                "media_url": url_for("main.os_imagem_principal", os_id=os_id),
            }), 201
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel no upload principal da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco no upload principal da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro no upload stream da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/os/<int:os_id>/upload-video-stream", methods=["PUT"], endpoint="os_upload_video_stream")
    @login_required
    def os_upload_video_stream(os_id):
        try:
            context = _build_upload_context(os_id)
            _ordem_existente, error_response = _get_or_create_ordem_for_upload(context)
            if error_response is not None:
                return error_response
            db.session.commit()

            file_name, file_url, error_response, error_status = _upload_request_stream_to_webdav(os_id, "video")
            if error_response is not None:
                return error_response, error_status

            ordem, error_response = _get_or_create_ordem_for_upload(context, lock=True)
            if error_response is not None:
                return error_response

            ordem.video = _build_webdav_marker(os_id, file_name)
            if not ordem.quantidade_videos_registradas or ordem.quantidade_videos_registradas < 1:
                ordem.quantidade_videos_registradas = 1
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Upload do video concluido com sucesso.",
                "file_name": file_name,
                "webdav_url": file_url,
                "media_url": url_for("main.os_video", os_id=os_id),
            }), 201
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel no upload de video da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco no upload de video da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro no upload stream do video da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/os/<int:os_id>/upload-video-background", methods=["PUT"], endpoint="os_upload_video_background")
    @login_required
    def os_upload_video_background(os_id):
        try:
            context = _build_upload_context(os_id)
            _ordem_existente, error_response = _get_or_create_ordem_for_upload(context)
            if error_response is not None:
                return error_response
            db.session.commit()

            file_name = _build_stream_upload_file_name(os_id, "video")
            if not file_name:
                return _media_error_response("Header X-File-Name ausente ou invalido.", 400)

            original_name = secure_filename(unquote((request.headers.get("X-File-Name") or "").strip()))
            content_type = _media_content_type(file_name, request.headers.get("Content-Type"))
            expected_bytes = request.content_length
            temp_path, total_bytes = _save_video_request_to_temp(file_name)
            if total_bytes <= 0:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                return _media_error_response("Arquivo de video vazio ou invalido.", 400)
            if expected_bytes is not None and int(expected_bytes) != int(total_bytes):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                return _media_error_response(
                    "O upload do video foi interrompido antes de terminar. Envie o arquivo novamente.",
                    400,
                )
            validation_error = _validate_uploaded_video_file(temp_path, file_name)
            if validation_error:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                return _media_error_response(validation_error, 400)

            job_id = _create_video_upload_job(
                os_id=os_id,
                user_id=getattr(current_user, "id", None),
                file_name=file_name,
                original_name=original_name or file_name,
                content_type=content_type,
                temp_path=temp_path,
                total_bytes=total_bytes,
            )
            VIDEO_BACKGROUND_UPLOAD_EXECUTOR.submit(
                _run_video_upload_job,
                current_app._get_current_object(),
                job_id,
            )

            return jsonify({
                "success": True,
                "message": "Video recebido. O envio para o Skybox continuara em segundo plano.",
                "job_id": job_id,
                "os_id": os_id,
                "file_name": file_name,
                "progress": 0,
            }), 202
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel no upload background de video da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco ao preparar upload background de video da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao iniciar upload background de video da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/video-upload-jobs/<job_id>", methods=["GET"], endpoint="video_upload_job_status")
    @login_required
    def video_upload_job_status(job_id):
        job = _get_video_upload_job(job_id)
        if not job:
            fallback_os_id = request.args.get("os_id", type=int)
            if fallback_os_id:
                try:
                    return jsonify(_build_video_upload_status_from_os(fallback_os_id))
                except PilotoOsError:
                    abort(403)

            return jsonify({
                "success": False,
                "error": "Upload de video nao encontrado.",
                "status": "missing",
            }), 404

        current_user_id = getattr(current_user, "id", None)
        if job.get("user_id") != current_user_id and getattr(current_user, "tipo_usuario", None) not in ADMIN_PANEL_VIEW_TYPES:
            abort(403)

        return jsonify({
            "success": True,
            "job_id": job["id"],
            "status": job["status"],
            "progress": int(job.get("progress") or 0),
            "message": job.get("message") or "",
            "os_id": job.get("os_id"),
            "file_name": job.get("file_name"),
            "media_url": job.get("media_url"),
        })

    @bp.route("/api/os/<int:os_id>/upload-complementary-stream", methods=["PUT"], endpoint="os_upload_complementary_stream")
    @login_required
    def os_upload_complementary_stream(os_id):
        try:
            context = _build_upload_context(os_id)
            ordem, error_response = _get_or_create_ordem_for_upload(context)
            if error_response is not None:
                return error_response
            db.session.commit()

            imagens = _parse_media_list(getattr(ordem, "outras_imagens", None))
            image_index = len(imagens) + 1
            file_name, file_url, error_response, error_status = _upload_request_stream_to_webdav(os_id, f"complementar_{image_index}")
            if error_response is not None:
                db.session.rollback()
                return error_response, error_status

            ordem, error_response = _get_or_create_ordem_for_upload(context, lock=True)
            if error_response is not None:
                return error_response

            imagens = _parse_media_list(getattr(ordem, "outras_imagens", None))
            image_index = len(imagens) + 1
            imagens.append(_build_webdav_marker(os_id, file_name))
            ordem.outras_imagens = json.dumps(imagens, ensure_ascii=False)
            total_imagens = len(imagens) + (1 if getattr(ordem, "imagem_principal", None) else 0)
            if not ordem.quantidade_imagens_registradas or ordem.quantidade_imagens_registradas < total_imagens:
                ordem.quantidade_imagens_registradas = total_imagens
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Upload da imagem complementar concluido com sucesso.",
                "file_name": file_name,
                "webdav_url": file_url,
                "image_index": image_index,
                "media_url": url_for("main.os_imagem_complementar", os_id=os_id, image_index=image_index),
                "total_complementary_images": len(imagens),
            }), 201
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel no upload complementar da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco no upload complementar da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro no upload stream da imagem complementar da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/os/<int:os_id>/imagem-principal", methods=["DELETE"], endpoint="os_delete_principal_image")
    @login_required
    def os_delete_principal_image(os_id):
        try:
            context = _build_upload_context(os_id)
            ordem = context.get("ordem")
            image_path = getattr(ordem, "imagem_principal", None) if ordem else None
            if not image_path:
                return jsonify({"success": False, "error": "Foto principal nao encontrada."}), 404

            _delete_os_media_path(os_id, image_path)
            ordem.imagem_principal = None
            imagens = _parse_media_list(getattr(ordem, "outras_imagens", None))
            ordem.quantidade_imagens_registradas = len(imagens) or None
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Foto principal removida com sucesso.",
                "total_images": len(imagens),
            })
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel ao remover foto principal da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco ao remover foto principal da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover foto principal da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/os/<int:os_id>/video", methods=["DELETE"], endpoint="os_delete_video")
    @login_required
    def os_delete_video(os_id):
        try:
            context = _build_upload_context(os_id)
            ordem = context.get("ordem")
            video_path = getattr(ordem, "video", None) if ordem else None
            if not video_path:
                return jsonify({"success": False, "error": "Video nao encontrado."}), 404

            _delete_os_media_path(os_id, video_path)
            ordem.video = None
            ordem.quantidade_videos_registradas = None
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Video removido com sucesso.",
            })
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel ao remover video da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco ao remover video da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover video da OS %s", os_id)
            return _media_error_response()

    @bp.route("/api/os/<int:os_id>/imagem-complementar/<int:image_index>", methods=["DELETE"], endpoint="os_delete_complementary_image")
    @login_required
    def os_delete_complementary_image(os_id, image_index):
        try:
            context = _build_upload_context(os_id)
            ordem = context.get("ordem")
            imagens = _parse_media_list(getattr(ordem, "outras_imagens", None) if ordem else None)
            index = int(image_index) - 1
            if index < 0 or index >= len(imagens):
                return jsonify({"success": False, "error": "Imagem complementar nao encontrada."}), 404

            removed_path = imagens.pop(index)
            _delete_os_media_path(os_id, removed_path)

            ordem.outras_imagens = json.dumps(imagens, ensure_ascii=False) if imagens else None
            total_imagens = len(imagens) + (1 if getattr(ordem, "imagem_principal", None) else 0)
            ordem.quantidade_imagens_registradas = total_imagens or None
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Imagem complementar removida com sucesso.",
                "removed_index": image_index,
                "total_complementary_images": len(imagens),
            })
        except RuntimeError:
            db.session.rollback()
            current_app.logger.exception("Configuracao de armazenamento indisponivel ao remover imagem complementar da OS %s", os_id)
            return _media_error_response(MEDIA_STORAGE_UNAVAILABLE_MESSAGE, 500)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro de banco ao remover imagem complementar da OS %s", os_id)
            return _media_error_response(MEDIA_DATABASE_ERROR_MESSAGE, 500)
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao remover imagem complementar da OS %s", os_id)
            return _media_error_response()

    @bp.route("/admin/os/<int:os_id>/formulario", methods=["GET", "POST"], endpoint="admin_os_formulario_view")
    @login_required
    def admin_os_formulario_view(os_id):
        _require_admin_os_view()

        if request.method == "POST":
            try:
                flash(
                    salvar_admin_os_form(
                        current_user,
                        os_id,
                        request.form,
                        request.files,
                        current_app.root_path,
                    ),
                    "success",
                )
                return redirect(url_for("main.admin_os_formulario_view", os_id=os_id))
            except PilotoOsError as exc:
                flash(str(exc), exc.category)
                if exc.redirect_endpoint == "main.admin_os_formulario_view":
                    return redirect(url_for("main.admin_os_formulario_view", os_id=os_id))
                return redirect(url_for(exc.redirect_endpoint))
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Erro ao salvar formulario admin da OS %s", os_id)
                flash("Erro ao salvar o formulario. Verifique os campos e tente novamente.", "danger")

        try:
            context = build_admin_os_form_context(current_user, os_id)
        except PilotoOsError as exc:
            flash(str(exc), exc.category)
            return redirect(url_for(exc.redirect_endpoint))

        return render_template(
            "piloto_os_formulario.html",
            **context,
            url_voltar=url_for("main.admin_historico_os"),
            form_action=url_for("main.admin_os_formulario_view", os_id=os_id),
        )

    @bp.route("/admin/os/<int:os_id>/export/pdf/v2", methods=["GET"], endpoint="admin_export_os_pdf_v2")
    @login_required
    def admin_export_os_pdf_v2(os_id):
        _require_admin_os_export()
        _ensure_os_region_access(os_id)

        caminho_pdf, download_name = build_admin_os_pdf_v2_export(os_id, request.args)
        return send_file(
            caminho_pdf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )

    @bp.route("/admin/os/<int:os_id>/export/excel/v2", methods=["GET"], endpoint="admin_export_os_excel_v2")
    @login_required
    def admin_export_os_excel_v2(os_id):
        _require_admin_os_export()
        _ensure_os_region_access(os_id)

        output, download_name = build_admin_os_excel_v2_export(os_id, request.args)
        return send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
