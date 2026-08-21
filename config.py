import os
import secrets
from dotenv import load_dotenv

# Adicione isso aqui para garantir que o config.py leia o .env antes de definir a classe
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    # Gera uma chave secreta aleatória ou usa uma fixa
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or os.environ.get("FLASK_SECRET_KEY")
        or ("dev-" + secrets.token_hex(32))
    )
    uri = os.environ.get('DATABASE_URL')
    Maps_KEY_FRONT = os.getenv("KEY_API_GOOGLE_MAPS")

    # Dropbox Configs
    DROPBOX_APP_KEY = os.environ.get('DROPBOX_APP_KEY')
    DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET')
    DROPBOX_REFRESH_TOKEN = os.environ.get('DROPBOX_REFRESH_TOKEN')
    SKYBOX_WEBDAV_URL = os.environ.get("SKYBOX_WEBDAV_URL")
    SKYBOX_USERNAME = os.environ.get("SKYBOX_USERNAME")
    SKYBOX_APP_PASSWORD = os.environ.get("SKYBOX_APP_PASSWORD")
    SKYBOX_BASE_DIR = os.environ.get("SKYBOX_BASE_DIR", "dados ordens de serviço")

    # Nova variável (sem restrição de site) apenas para o Geocode do Python
    Maps_KEY_BACK = os.getenv("GOOGLE_MAPS_KEY_BACK")
    
    # Caminho do Banco de Dados

    KEY_API_GOOGLE_MAPS = os.getenv("KEY_API_GOOGLE_MAPS")
    
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # configuração sqlalchemy
    SQLALCHEMY_DATABASE_URI = uri
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    USER_PRESENCE_UPDATE_INTERVAL_SECONDS = os.getenv(
        "USER_PRESENCE_UPDATE_INTERVAL_SECONDS",
        "60",
    )
    CSS_BUNDLE_AUTO_BUILD = os.getenv("CSS_BUNDLE_AUTO_BUILD", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
