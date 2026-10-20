"""Conteúdo editorial e cópias de divulgação, separados dos registros operacionais."""
from datetime import datetime, timezone

from app.extensions import db


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AcaoPublica(db.Model):
    __tablename__ = 'acoes_publicas'
    id = db.Column(db.String(32), primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey('prefeituras.id'), nullable=False)
    origem_os_id = db.Column(db.Integer, db.ForeignKey('solicitacoes.id', ondelete='SET NULL'))
    demo = db.Column(db.Boolean, nullable=False)
    titulo = db.Column(db.String(160), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    bairro = db.Column(db.String(120), nullable=False, default='')
    inicio = db.Column(db.Date, nullable=False)
    fim = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.Text, nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='RASCUNHO')
    publicado = db.Column(db.Boolean, nullable=False, default=False)
    publicacao = db.Column(db.JSON)
    versao = db.Column(db.Integer, nullable=False, default=1)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    criado_em = db.Column(db.DateTime, nullable=False, default=now)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=now)
    publicado_em = db.Column(db.DateTime)
    prefeitura = db.relationship('Prefeitura')
    midias = db.relationship('AcaoPublicaMidia', order_by='AcaoPublicaMidia.criado_em', lazy='selectin')
    __mapper_args__ = {'version_id_col': versao}
    __table_args__ = (
        db.CheckConstraint("status IN ('RASCUNHO','EM_REVISAO','PUBLICADO','RETIRADO')", name='ck_acoes_publicas_status'),
        db.CheckConstraint('fim >= inicio', name='ck_acoes_publicas_periodo'),
        db.UniqueConstraint('id', 'prefeitura_id', name='uq_acoes_publicas_municipio'),
        db.Index('ix_acoes_publicas_municipio_demo', 'prefeitura_id', 'demo', 'atualizado_em'),
        db.Index('ix_acoes_publicas_publicadas', 'publicado', 'demo', 'publicado_em'),
    )


class AcaoPublicaMidia(db.Model):
    __tablename__ = 'acoes_publicas_midias'
    id = db.Column(db.String(32), primary_key=True)
    acao_id = db.Column(db.String(32), nullable=False)
    prefeitura_id = db.Column(db.Integer, nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    mime = db.Column(db.String(40), nullable=False)
    legenda = db.Column(db.String(240), nullable=False, default='')
    sha256 = db.Column(db.String(64), nullable=False)
    tamanho = db.Column(db.Integer, nullable=False)
    selecionada = db.Column(db.Boolean, nullable=False, default=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    criado_em = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (
        db.ForeignKeyConstraint(['acao_id', 'prefeitura_id'], ['acoes_publicas.id', 'acoes_publicas.prefeitura_id'], name='fk_acao_midia_municipio'),
        db.Index('ix_acoes_midias_acao', 'acao_id'),
    )


class AcaoPublicaEvento(db.Model):
    __tablename__ = 'acoes_publicas_eventos'
    id = db.Column(db.Integer, primary_key=True)
    acao_id = db.Column(db.String(32), nullable=False)
    prefeitura_id = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    usuario_nome = db.Column(db.String(150), nullable=False)
    evento = db.Column(db.String(30), nullable=False)
    versao = db.Column(db.Integer, nullable=False)
    conteudo = db.Column(db.JSON, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (
        db.ForeignKeyConstraint(['acao_id', 'prefeitura_id'], ['acoes_publicas.id', 'acoes_publicas.prefeitura_id'], name='fk_acao_evento_municipio'),
        db.Index('ix_acoes_eventos_acao', 'acao_id', 'id'),
    )
