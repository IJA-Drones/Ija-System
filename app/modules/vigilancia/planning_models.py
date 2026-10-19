"""Extensão do levantamento de campo: território e planejamento municipal."""

from app.extensions import db


class CampoQuarteirao(db.Model):
    __tablename__ = "vigilancia_campo_quarteiroes"
    prefeitura = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    bairro = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(80), nullable=False)
    imoveis = db.Column(db.Integer, nullable=False)
    referencia = db.Column(db.String(200), nullable=False)
    atualizado_por = db.Column(db.String(80), nullable=False)
    atualizado_em = db.Column(db.Float, nullable=False)
    __table_args__ = (db.CheckConstraint("imoveis > 0", name="ck_campo_quarteirao_imoveis"),)


class CampoPlano(db.Model):
    __tablename__ = "vigilancia_campo_planos"
    prefeitura = db.Column(db.Integer, primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    inicio = db.Column(db.Date, nullable=False)
    fim = db.Column(db.Date, nullable=False)
    responsavel = db.Column(db.String(120), nullable=False)
    fonte = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    versao = db.Column(db.Integer, nullable=False)
    historico = db.Column(db.JSON, nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "code"],
            ["vigilancia_campo_levantamentos.prefeitura", "vigilancia_campo_levantamentos.demo", "vigilancia_campo_levantamentos.code"], name="fk_campo_plano_levantamento"),
        db.CheckConstraint("status IN ('RASCUNHO','LIBERADO','ENCERRADO')", name="ck_campo_plano_status"),
        db.CheckConstraint("fim >= inicio", name="ck_campo_plano_periodo"),
    )


class CampoPlanoEstrato(db.Model):
    __tablename__ = "vigilancia_campo_plano_estratos"
    prefeitura = db.Column(db.Integer, primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    plano = db.Column(db.String(80), primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    imoveis = db.Column(db.Integer, nullable=False)
    meta = db.Column(db.Integer, nullable=False)
    criterio = db.Column(db.String(200), nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "plano"],
            ["vigilancia_campo_planos.prefeitura", "vigilancia_campo_planos.demo", "vigilancia_campo_planos.code"], name="fk_campo_estrato_plano"),
        db.CheckConstraint("imoveis > 0 AND meta > 0 AND meta <= imoveis", name="ck_campo_estrato_meta"),
    )


class CampoPlanoQuarteirao(db.Model):
    __tablename__ = "vigilancia_campo_plano_quarteiroes"
    prefeitura = db.Column(db.Integer, primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    plano = db.Column(db.String(80), primary_key=True)
    quarteirao = db.Column(db.String(80), primary_key=True)
    estrato = db.Column(db.String(80), nullable=False)
    meta = db.Column(db.Integer, nullable=False)
    agente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    territorio = db.Column(db.JSON, nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "plano", "estrato"],
            ["vigilancia_campo_plano_estratos.prefeitura", "vigilancia_campo_plano_estratos.demo", "vigilancia_campo_plano_estratos.plano", "vigilancia_campo_plano_estratos.code"], name="fk_campo_quarteirao_estrato"),
        db.ForeignKeyConstraint(["prefeitura", "demo", "quarteirao"],
            ["vigilancia_campo_quarteiroes.prefeitura", "vigilancia_campo_quarteiroes.demo", "vigilancia_campo_quarteiroes.code"], name="fk_campo_quarteirao_rg"),
        db.CheckConstraint("meta > 0", name="ck_campo_plano_quarteirao_meta"),
    )


class CampoPlanoVisita(db.Model):
    __tablename__ = "vigilancia_campo_plano_visitas"
    prefeitura = db.Column(db.Integer, primary_key=True)
    demo = db.Column(db.Boolean, primary_key=True)
    origin = db.Column(db.String(10), primary_key=True)
    code = db.Column(db.String(80), primary_key=True)
    plano = db.Column(db.String(80), nullable=False)
    quarteirao = db.Column(db.String(80), nullable=False)
    autor = db.Column(db.String(80), nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["prefeitura", "demo", "origin", "code"],
            ["vigilancia_campo_inspecoes.prefeitura", "vigilancia_campo_inspecoes.demo", "vigilancia_campo_inspecoes.origin", "vigilancia_campo_inspecoes.code"], name="fk_campo_plano_visita_inspecao"),
        db.ForeignKeyConstraint(["prefeitura", "demo", "plano", "quarteirao"],
            ["vigilancia_campo_plano_quarteiroes.prefeitura", "vigilancia_campo_plano_quarteiroes.demo", "vigilancia_campo_plano_quarteiroes.plano", "vigilancia_campo_plano_quarteiroes.quarteirao"], name="fk_campo_plano_visita_quarteirao"),
    )


PLANNING_TABLES = [model.__table__ for model in (
    CampoQuarteirao, CampoPlano, CampoPlanoEstrato, CampoPlanoQuarteirao, CampoPlanoVisita)]
