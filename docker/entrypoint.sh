#!/usr/bin/env bash
# Migra o banco e sobe o gunicorn — mesmos parâmetros do Procfile (Render), com porta do EasyPanel.
set -euo pipefail

if [ "${DB_MIGRATE_ON_BOOT:-1}" = "1" ]; then
    flask --app app:create_app db upgrade
fi

exec gunicorn "app:create_app()" --config gunicorn.conf.py \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --max-requests "${GUNICORN_MAX_REQUESTS:-700}" \
    --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
    --access-logfile -
