"""Stop a conversion before scratch usage can terminate the whole web service."""
import subprocess
import os
import re
import tempfile
import time
from pathlib import Path

from .storage import TemporaryStorageError, require_space


def directory_bytes(root):
    size = 0
    for path in Path(root).rglob('*'):
        try:
            if path.is_file() and not path.is_symlink():
                size += path.stat().st_size
        except FileNotFoundError:
            pass
    return size


def check_budget(root, limit):
    used = directory_bytes(root)
    if used > limit:
        raise TemporaryStorageError('O processamento atingiu o limite seguro de espaço temporário. '
                                    'O original permanece salvo no Skybox; use um disco de trabalho maior para este levantamento.')
    require_space(root)
    return used


def run(args, environment, scratch, root, limit):
    from .service import logger
    check_budget(root, limit)
    with tempfile.TemporaryFile(dir=scratch) as output, tempfile.TemporaryFile(dir=scratch) as errors:
        process = subprocess.Popen(args, stdout=output, stderr=errors, env=environment)
        last_log = 0
        try:
            while True:
                used = check_budget(root, limit)
                if time.monotonic() - last_log >= 30:
                    tail = os.pread(errors.fileno(), 8192, max(0, os.fstat(errors.fileno()).st_size - 8192)).decode('utf-8', errors='replace')
                    progress = re.findall(r'^ortho_stage (?:pixels windows=\d+ total=\d+|retry x=\d+ y=\d+ attempt=\d+|overviews)$', tail, re.M)
                    logger.info('ortho_process converting scratch_bytes=%s limit_bytes=%s progress=%s', used, limit, progress[-1] if progress else 'starting')
                    last_log = time.monotonic()
                try:
                    process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    pass  # Poll disk usage, not a job deadline.
            check_budget(root, limit)
            output.seek(0)
            errors.seek(0, 2)
            errors.seek(max(0, errors.tell() - 32768))
            return subprocess.CompletedProcess(args, process.returncode, output.read().decode('utf-8'),
                                               errors.read().decode('utf-8', errors='replace'))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
