import gzip
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dropbox
from apscheduler.schedulers.background import BackgroundScheduler


TIMEZONE = "America/Sao_Paulo"
TZ = ZoneInfo(TIMEZONE)
# Preserve the historical local backup folder under app/backup.
BACKUP_DIR = Path(__file__).resolve().parents[2] / "backup"

scheduler = BackgroundScheduler(timezone=TIMEZONE)
_scheduler_started = False
_backup_state = {
    "running": False,
    "last_file": None,
    "last_error": None,
    "started_at": None,
    "finished_at": None,
}


def upload_to_dropbox(file_path):
    app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
    app_secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()

    print(f"DEBUG: Tentando Dropbox com Key: {app_key[:4]}... / Secret: {app_secret[:4]}...")

    if not all([app_key, app_secret, refresh_token]):
        print("ERRO: Faltam variaveis de ambiente do Dropbox no Render.")
        return False

    zipped_file = file_path.with_suffix(file_path.suffix + ".gz")

    try:
        with open(file_path, "rb") as source:
            with gzip.open(zipped_file, "wb") as target:
                shutil.copyfileobj(source, target)

        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token,
        )

        dest_path = f"/backups/{zipped_file.name}"
        with open(zipped_file, "rb") as handle:
            meta = dbx.files_upload(handle.read(), dest_path, mode=dropbox.files.WriteMode.overwrite)
            print(f" SUCESSO ABSOLUTO! Salvo em: {meta.path_display}")

        if zipped_file.exists():
            os.remove(zipped_file)
        if file_path.exists():
            os.remove(file_path)
        return True
    except Exception as exc:
        print(f"ERRO NO DROPBOX: {exc}")
        return False


def ensure_backup_dir():
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Pasta de backup criada em: {BACKUP_DIR}")


def backup_filename():
    stamp = datetime.now(TZ).strftime("%d-%m-%Y_%H-%M")
    project_name = os.getenv("PROJECT_NAME", "backup")
    environment = os.getenv("APP_ENV", "prod")
    return BACKUP_DIR / f"{project_name}_{environment}_{stamp}.sql"


def run_postgres_backup():
    database_url = os.getenv("DATABASE_URL")
    ensure_backup_dir()
    output_file = backup_filename()

    try:
        if not database_url:
            raise RuntimeError("DATABASE_URL nao configurada no .env ou no Render.")

        pg_dump_cmd = "pg_dump"
        if os.name == "nt":
            print("Windows detectado. Tentando backup real do banco remoto...")

        cmd = [
            pg_dump_cmd,
            "--no-owner",
            "--no-privileges",
            "--format=plain",
            "--file",
            str(output_file),
            database_url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, shell=(os.name == "nt"))

        if result.returncode != 0:
            if os.name == "nt":
                raise RuntimeError(
                    "O comando pg_dump falhou. Verifique se o PostgreSQL esta instalado no seu Nitro V15. "
                    f"Erro: {result.stderr}"
                )
            raise RuntimeError(f"pg_dump falhou no servidor: {result.stderr}")

        print(f"Backup SQL gerado com sucesso: {output_file.name}")

        if not upload_to_dropbox(output_file):
            print("O backup foi gerado, mas o envio ao Dropbox falhou.")

        return output_file
    except Exception as exc:
        print(f"Erro critico no backup real: {exc}")
        raise exc


def start_daily_backup_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return

    ensure_backup_dir()

    if scheduler.get_job("daily_backup_0500") is None:
        scheduler.add_job(
            run_postgres_backup,
            trigger="cron",
            hour=5,
            minute=0,
            id="daily_backup_0500",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if not scheduler.running:
        scheduler.start()

    _scheduler_started = True


def run_backup_async():
    try:
        _backup_state["running"] = True
        _backup_state["last_error"] = None
        _backup_state["started_at"] = datetime.now(TZ).isoformat()
        _backup_state["finished_at"] = None

        file_path = run_postgres_backup()
        _backup_state["last_file"] = f"Enviado para Nuvem: {file_path.name}.gz"
    except Exception as exc:
        _backup_state["last_error"] = str(exc)
    finally:
        _backup_state["running"] = False
        _backup_state["finished_at"] = datetime.now(TZ).isoformat()


def trigger_backup_async():
    if _backup_state["running"]:
        return False

    thread = threading.Thread(target=run_backup_async, daemon=True)
    thread.start()
    return True


def get_backup_state():
    return dict(_backup_state)


def list_backups():
    app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
    app_secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()

    backups = []
    try:
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token,
        )

        result = dbx.files_list_folder("/backups")

        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                backups.append(
                    {
                        "name": entry.name,
                        "path": entry.path_display,
                        "size_bytes": entry.size,
                        "modified_at": entry.client_modified.replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ),
                        "is_cloud": True,
                    }
                )
    except Exception as exc:
        print(f"Erro ao listar Dropbox (Pasta pode estar vazia): {exc}")
        ensure_backup_dir()
        files = sorted(BACKUP_DIR.glob("backup_*"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in files:
            status = path.stat()
            backups.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": status.st_size,
                    "modified_at": datetime.fromtimestamp(status.st_mtime, tz=TZ),
                    "is_cloud": False,
                }
            )

    backups.sort(key=lambda backup: backup["modified_at"], reverse=True)
    return backups
