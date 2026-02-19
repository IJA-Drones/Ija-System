import os

class Config:
    # Gera uma chave secreta aleatória ou usa uma fixa
    SECRET_KEY = os.environ.get('SECRET_KEY')
    uri = os.environ.get('DATABASE_URL')
    Maps_KEY_FRONT = os.getenv("KEY_API_GOOGLE_MAPS")

    # Dropbox Configs
    DROPBOX_APP_KEY = os.environ.get('DROPBOX_APP_KEY')
    DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET')
    DROPBOX_REFRESH_TOKEN = os.environ.get('DROPBOX_REFRESH_TOKEN')

    # Nova variável (sem restrição de site) apenas para o Geocode do Python
    Maps_KEY_BACK = os.getenv("GOOGLE_MAPS_KEY_BACK")
    
    # Caminho do Banco de Dados

    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # configuração sqlalchemy
    SQLALCHEMY_DATABASE_URI = uri
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY')