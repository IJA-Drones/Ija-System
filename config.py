import os

class Config:
    # Gera uma chave secreta aleatória ou usa uma fixa
    SECRET_KEY = os.environ.get('SECRET_KEY')
    uri = os.environ.get('DATABASE_URL')
    KEY_API_GOOGLE_MAPS = os.environ.get('KEY_API_GOOGLE_MAPS')
    
    # Caminho do Banco de Dados

    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    # configuração sqlalchemy
    SQLALCHEMY_DATABASE_URI = uri
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-secreta-de-backup')