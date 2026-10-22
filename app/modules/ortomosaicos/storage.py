"""Private working storage for multipart uploads and raster subprocesses."""
import os
import shutil
import tempfile
from pathlib import Path

from flask import Request, current_app, jsonify


RESERVE_BYTES = 256 * 1024 * 1024


class TemporaryStorageError(RuntimeError):
    pass


def working_root():
    configured = (current_app.config.get('ORTHOMOSAIC_TEMP_DIR') or '').strip()
    # Use the existing private application filesystem, not Render's separately
    # capped /tmp volume. This is scratch space; durable files remain in Skybox.
    path = Path(configured) if configured else Path(current_app.instance_path) / 'ortomosaicos-tmp'
    if not path.is_absolute():
        raise TemporaryStorageError('ORTHOMOSAIC_TEMP_DIR deve ser um caminho absoluto no disco de trabalho.')
    path = path.resolve()
    if current_app.static_folder and path.is_relative_to(Path(current_app.static_folder).resolve()):
        raise TemporaryStorageError('O disco de trabalho dos levantamentos deve ficar fora da pasta pública.')
    if os.environ.get('RENDER', '').lower() == 'true' and path.is_relative_to(Path('/tmp').resolve()):
        raise TemporaryStorageError('Configure a pasta de trabalho dos levantamentos fora de /tmp no Render.')
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise TemporaryStorageError('Não foi possível acessar o disco de trabalho dos levantamentos. Verifique a montagem e as permissões.') from exc
    return path


def require_space(folder, additional_bytes=0):
    if shutil.disk_usage(folder).free < max(0, additional_bytes) + RESERVE_BYTES:
        raise TemporaryStorageError(
            'Espaço insuficiente no disco de trabalho para este levantamento. '
            'Libere espaço de trabalho no servidor e tente novamente.')


class TemporaryUpload:
    """Named, seekable upload reused by inspection instead of making a second copy."""
    def __init__(self, root):
        self.file = tempfile.NamedTemporaryFile(mode='w+b', prefix='ija-orto-receive-', suffix='.tif', dir=root)
        self.ortho_upload_path = Path(self.file.name)
        self.root = root
        self.unchecked_bytes = 0

    def __getattr__(self, name):
        return getattr(self.file, name)

    def write(self, data):
        # Check throughout uploads with unknown length, and competing requests.
        if self.unchecked_bytes <= 0:
            require_space(self.root, len(data))
            self.unchecked_bytes = 1024 * 1024
        self.unchecked_bytes -= len(data)
        return self.file.write(data)


class OrthomosaicRequest(Request):
    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        if self.endpoint != 'main.ortomosaico_upload':
            return super()._get_file_stream(total_content_length, content_type, filename, content_length)
        root = working_root()
        require_space(root, total_content_length or 0)
        stream = TemporaryUpload(root)
        self.__dict__.setdefault('_ortho_upload_streams', []).append(stream)
        return stream

    def close(self):
        # Also covers interrupted/malformed multipart bodies that never populate files.
        try:
            super().close()
        finally:
            for stream in self.__dict__.pop('_ortho_upload_streams', []):
                stream.close()


def register_storage(app):
    app.request_class = OrthomosaicRequest

    @app.errorhandler(TemporaryStorageError)
    def storage_error(exc):
        return jsonify(error=str(exc)), 507
