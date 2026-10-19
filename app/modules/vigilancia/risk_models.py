"""Snapshots municipais imutáveis, sem dados pessoais ou duplicação de casos."""
from app.extensions import db


class RiscoAnalise(db.Model):
    __tablename__ = "vigilancia_risco_analises"
    id = db.Column(db.String(32), primary_key=True)
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=False)
    demo = db.Column(db.Boolean, nullable=False)
    actor = db.Column(db.String(80), nullable=False)
    fonte = db.Column(db.String(200), nullable=False)
    criado = db.Column(db.Float, nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    report = db.Column(db.JSON, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("prefeitura", "demo", "digest", name="uq_risco_analise_snapshot"),
        db.Index("ix_risco_analise_prefeitura_demo", "prefeitura", "demo"),
    )
