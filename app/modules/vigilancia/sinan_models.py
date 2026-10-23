"""Histórico e casos SINAN no banco configurado para o IJA."""

from app.extensions import db


class SinanJob(db.Model):
    __tablename__ = "vigilancia_sinan_lotes"
    id = db.Column(db.String(32), primary_key=True)
    owner = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    disease = db.Column(db.String(20), nullable=False)
    ibge = db.Column(db.String(7), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    demo = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False)
    created = db.Column(db.Float, nullable=False)
    updated = db.Column(db.Float, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    pages = db.Column(db.Integer, nullable=False, default=0)
    cancel = db.Column(db.Boolean, nullable=False, default=False)
    message = db.Column(db.Text, nullable=False, default="")
    summary = db.Column(db.JSON, nullable=False, default=dict)
    fingerprint = db.Column(db.String(64), nullable=False, default="")
    __table_args__ = (
        db.CheckConstraint("status IN ('running','completed','partial','failed','cancelled')", name="ck_sinan_lote_status"),
        db.CheckConstraint("kind IN ('api','csv','datasus')", name="ck_sinan_lote_kind"),
        db.Index("ix_sinan_owner_scope", "owner", "disease", "ibge", "year", "created"),
        db.Index("uq_sinan_worker", "status", unique=True,
                 postgresql_where=db.text("status = 'running'"), sqlite_where=db.text("status = 'running'")),
    )


class SinanCase(db.Model):
    __tablename__ = "vigilancia_sinan_casos"
    job_id = db.Column(db.String(32), db.ForeignKey("vigilancia_sinan_lotes.id", ondelete="CASCADE"), primary_key=True)
    reference = db.Column(db.String(80), primary_key=True)
    week = db.Column(db.String(6))
    classification = db.Column(db.String(30), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


SINAN_TABLES = [SinanJob.__table__, SinanCase.__table__]
