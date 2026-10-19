"""Tabelas de campo no mesmo PostgreSQL configurado para o IJA."""

from app.extensions import db


class CampoLote(db.Model):
    __tablename__ = "vigilancia_campo_lotes"
    id = db.Column(db.String(32), primary_key=True)
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=False)
    demo = db.Column(db.Boolean, nullable=False)
    actor = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(120), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    layout = db.Column(db.String(80), nullable=False)
    original = db.Column(db.LargeBinary, nullable=False)
    created = db.Column(db.Float, nullable=False)
    confirmed = db.Column(db.Float)
    status = db.Column(db.String(20), nullable=False)
    report = db.Column(db.JSON, nullable=False)
    inserted = db.Column(db.Integer, nullable=False, server_default="0")
    reused = db.Column(db.Integer, nullable=False, server_default="0")
    __table_args__ = (
        db.CheckConstraint("status IN ('VALIDADO','REJEITADO','CONCLUIDO')", name="ck_campo_lote_status"),
        db.UniqueConstraint("prefeitura", "demo", "actor", "sha256", "source", name="uq_campo_lote_origem"),
        db.UniqueConstraint("id", "prefeitura", "demo", name="uq_campo_lote_escopo"),
        db.Index("ix_campo_lote_prefeitura_data", "prefeitura", "created"),
    )


class CampoImovel(db.Model):
    __tablename__ = "vigilancia_campo_imoveis"
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    bairro = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(80), nullable=False)


class CampoLevantamento(db.Model):
    __tablename__ = "vigilancia_campo_levantamentos"
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    code = db.Column(db.String(80), primary_key=True)


class CampoInspecao(db.Model):
    __tablename__ = "vigilancia_campo_inspecoes"
    prefeitura = db.Column(db.Integer, primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    origin = db.Column(db.String(10), primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    property_code = db.Column(db.String(80), nullable=False)
    survey_code = db.Column(db.String(80))
    stratum = db.Column(db.String(80), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "property_code"],
                                ["vigilancia_campo_imoveis.prefeitura", "vigilancia_campo_imoveis.demo", "vigilancia_campo_imoveis.code"], name="fk_campo_inspecao_imovel"),
        db.ForeignKeyConstraint(["prefeitura", "demo", "survey_code"],
                                ["vigilancia_campo_levantamentos.prefeitura", "vigilancia_campo_levantamentos.demo", "vigilancia_campo_levantamentos.code"], name="fk_campo_inspecao_levantamento"),
    )


class CampoLoteInspecao(db.Model):
    __tablename__ = "vigilancia_campo_lote_inspecoes"
    batch_id = db.Column(db.String(32), primary_key=True)
    prefeitura = db.Column(db.Integer, nullable=False)
    demo = db.Column(db.Boolean, nullable=False)
    origin = db.Column(db.String(10), primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    source_line = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["batch_id", "prefeitura", "demo"],
                                ["vigilancia_campo_lotes.id", "vigilancia_campo_lotes.prefeitura", "vigilancia_campo_lotes.demo"], name="fk_campo_lote_inspecao_lote"),
        db.ForeignKeyConstraint(["prefeitura", "demo", "origin", "code"],
                                ["vigilancia_campo_inspecoes.prefeitura", "vigilancia_campo_inspecoes.demo", "vigilancia_campo_inspecoes.origin", "vigilancia_campo_inspecoes.code"], name="fk_campo_lote_inspecao_registro"),
    )


FIELD_TABLES = [model.__table__ for model in (CampoLote, CampoImovel, CampoLevantamento, CampoInspecao, CampoLoteInspecao)]


class CampoOsReferencia(db.Model):
    __tablename__ = "vigilancia_campo_os"
    batch_id = db.Column(db.String(32), db.ForeignKey("vigilancia_campo_lotes.id", ondelete="CASCADE"), primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id", ondelete="SET NULL"), index=True)


FIELD_OS_TABLES = [CampoOsReferencia.__table__]
