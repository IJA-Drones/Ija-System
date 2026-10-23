# syntax=docker/dockerfile:1
# Ija-System — imagem de deploy para o EasyPanel (build direto deste Dockerfile no servidor,
# ARM64/Ubuntu). Sem Docker Hub: o painel clona o repositório e constrói aqui.
#
# Duas etapas: "build" resolve as dependências Python (compila o que não tiver wheel ARM64, como o
# pyreaddbc do SINAN/DATASUS) num virtualenv; "runtime" leva só esse venv + o código sobre Debian slim
# com as bibliotecas de sistema do WeasyPrint (PDFs) e o ffmpeg (conversão de vídeo da OS).
#
# Configuração no EasyPanel (aba Environment) — nenhum .env entra na imagem:
#   DATABASE_URL, SECRET_KEY e as demais chaves listadas em .env.example
#   (OPENAI_API_KEY, REPORT_SMTP_*, VAPID_*, FCM_SERVICE_ACCOUNT_JSON, TELEGRAM_*, KAPSO_*, PUBLIC_BASE_URL...).
# Volumes recomendados (sem eles os arquivos somem a cada redeploy):
#   /app/upload-files  anexos, fotos/vídeos de focos e imóveis pendentes, denúncias
#   /app/instance      estado local da aplicação
# Porta exposta: 8000. Healthcheck: /healthz. O banco é migrado na subida (DB_MIGRATE_ON_BOOT=0 desliga).

ARG PYTHON_VERSION=3.12

# ------------------------------------------------------------------ build
FROM python:${PYTHON_VERSION}-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

# ------------------------------------------------------------------ runtime
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
# WeasyPrint precisa de pango/harfbuzz; tini repassa SIGTERM ao gunicorn no stop do container;
# curl serve ao HEALTHCHECK; ffmpeg converte os vídeos enviados pelo piloto (piloto_os).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 shared-mime-info \
       fonts-dejavu-core fonts-liberation ffmpeg tini curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app
COPY . .
# bundle de CSS gerado na imagem (a subida não escreve em app/static)
RUN python scripts/build_css_bundle.py \
    && mkdir -p /app/upload-files /app/instance

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "docker/entrypoint.sh"]
