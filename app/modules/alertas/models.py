"""Alertas parametrizados e dispositivos de notificação (web push / FCM)."""

from datetime import datetime

from app.extensions import db


class DispositivoPush(db.Model):
    __tablename__ = "alertas_dispositivos"
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    canal = db.Column(db.String(10), nullable=False)  # webpush | fcm
    token = db.Column(db.Text, nullable=False)  # endpoint (web push) ou token FCM
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    subscription = db.Column(db.JSON, nullable=False, default=dict)  # chaves p256dh/auth do web push
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    bairro = db.Column(db.String(100))
    user_agent = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    falhas = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class AlertaRegra(db.Model):
    __tablename__ = "alertas_regras"
    FONTES = {"denuncias": "Relatos de foco (cidadão)", "relatos": "Relatos de saúde (caso suspeito)"}
    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=False, index=True)
    nome = db.Column(db.String(120), nullable=False)
    fonte = db.Column(db.String(20), nullable=False)
    bairro = db.Column(db.String(100))  # vazio = município inteiro
    janela_dias = db.Column(db.Integer, nullable=False, default=7)
    limiar = db.Column(db.Integer, nullable=False, default=3)
    raio_km = db.Column(db.Float, nullable=False, default=2.0)
    intervalo_horas = db.Column(db.Integer, nullable=False, default=24)
    notificar_app = db.Column(db.Boolean, nullable=False, default=True)
    notificar_email = db.Column(db.Boolean, nullable=False, default=False)
    notificar_push = db.Column(db.Boolean, nullable=False, default=True)
    notificar_telegram = db.Column(db.Boolean, nullable=False, default=True)
    emails = db.Column(db.Text)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)
    ultimo_disparo_em = db.Column(db.DateTime)
    disparos = db.relationship("AlertaDisparo", backref="regra", cascade="all, delete-orphan", order_by="desc(AlertaDisparo.criado_em)")


class AlertaDisparo(db.Model):
    __tablename__ = "alertas_disparos"
    id = db.Column(db.Integer, primary_key=True)
    regra_id = db.Column(db.Integer, db.ForeignKey("alertas_regras.id", ondelete="CASCADE"), nullable=False, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=False, index=True)
    valor = db.Column(db.Integer, nullable=False)
    limiar = db.Column(db.Integer, nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    bairro = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    teste = db.Column(db.Boolean, nullable=False, default=False)
    resultado = db.Column(db.JSON, nullable=False, default=dict)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
