"""Execuções da migração de dados legados (extração, validação e carga)."""

from app.extensions import db


class Migracao(db.Model):
    __tablename__ = "vigilancia_migracoes"
    id = db.Column(db.String(32), primary_key=True)
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=False)
    demo = db.Column(db.Boolean, nullable=False)
    actor = db.Column(db.String(80), nullable=False)
    destino = db.Column(db.String(20), nullable=False)
    fonte = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(120), nullable=False)
    formato = db.Column(db.String(10), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    original = db.Column(db.LargeBinary, nullable=False)
    extraido = db.Column(db.LargeBinary, nullable=False)
    adequado = db.Column(db.LargeBinary)
    etapa = db.Column(db.String(20), nullable=False)
    extracao = db.Column(db.JSON, nullable=False)
    mapeamento = db.Column(db.JSON)
    relatorio = db.Column(db.JSON)
    resultado = db.Column(db.JSON)
    criado = db.Column(db.Float, nullable=False)
    atualizado = db.Column(db.Float, nullable=False)
    __table_args__ = (
        db.CheckConstraint("destino IN ('visitas','sinan','quarteiroes')", name="ck_migracao_destino"),
        db.CheckConstraint("etapa IN ('EXTRAIDO','VALIDADO','CONCLUIDO')", name="ck_migracao_etapa"),
        db.Index("ix_migracao_prefeitura_data", "prefeitura", "criado"),
    )
