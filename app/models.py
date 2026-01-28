from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import UserMixin

# -------------------------------------------------------------
# USUÁRIO (login do sistema)
# - UVIS também é um Usuario (tipo_usuario="uvis")
# - Piloto também é um Usuario (tipo_usuario="piloto") e aponta para Pilotos via piloto_id
# -------------------------------------------------------------
class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome_uvis = db.Column(db.String(100), nullable=False, index=True)
    regiao = db.Column(db.String(50), index=True)
    codigo_setor = db.Column(db.String(10))

    login = db.Column(db.String(50), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(200), nullable=False)

    # tipos esperados: "admin", "uvis", "operario", "visualizador", "piloto"
    tipo_usuario = db.Column(db.String(20), default="uvis", index=True)

    # ✅ vínculo opcional com Pilotos (somente quando tipo_usuario="piloto")
    piloto_id = db.Column(
        db.Integer,
        db.ForeignKey("pilotos.id"),
        nullable=True,
        index=True
    )
    piloto = db.relationship("Pilotos", lazy="joined")

    # Solicitações criadas por este usuário (normalmente UVIS cria)
    solicitacoes = db.relationship(
        "Solicitacao",
        back_populates="usuario",
        lazy="select"
    )

    # ✅ vínculos de pilotos que atendem esta UVIS (para filtro do piloto)
    vinculos_pilotos = db.relationship(
        "PilotoUvis",
        back_populates="uvis_usuario",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # ✅ NOVO: equipe da UVIS (até 5 pessoas) - 1 registro por membro
    equipe_uvis_membros = db.relationship(
        "EquipeUvis",
        back_populates="uvis_usuario",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="EquipeUvis.ordem"
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


# -------------------------------------------------------------
# EQUIPE UVIS (até 5 pessoas por UVIS)
# - 1 linha por membro
# - limite 5 via ordem 1..5 (CheckConstraint) + UniqueConstraint(uvis_usuario_id, ordem)
# -------------------------------------------------------------
class EquipeUvis(db.Model):
    __tablename__ = "equipe_uvis"

    id = db.Column(db.Integer, primary_key=True)

    uvis_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    # nome da equipe (agrupa membros)
    nome_equipe = db.Column(db.String(100), nullable=False, index=True)

    # slot fixo pra limitar em 5 DENTRO da equipe
    ordem = db.Column(db.Integer, nullable=False)

    # dados do membro
    nome = db.Column(db.String(100), nullable=False, index=True)
    funcao = db.Column(db.String(80))
    contato = db.Column(db.String(80))

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    uvis_usuario = db.relationship("Usuario", back_populates="equipe_uvis_membros")

    __table_args__ = (
        
        db.UniqueConstraint("uvis_usuario_id", "nome_equipe", "ordem", name="uq_equipe_uvis_equipe_slot"),

        db.CheckConstraint("ordem >= 1 AND ordem <= 5", name="ck_equipe_uvis_ordem_1_5"),

        db.Index("ix_equipe_uvis_uvis", "uvis_usuario_id"),
        db.Index("ix_equipe_uvis_uvis_equipe", "uvis_usuario_id", "nome_equipe"),
        db.Index("ix_equipe_uvis_uvis_equipe_ordem", "uvis_usuario_id", "nome_equipe", "ordem"),
    )


# -------------------------------------------------------------
# PILOTOS (cadastro do piloto)
# -------------------------------------------------------------
class Pilotos(db.Model):
    __tablename__ = "pilotos"

    id = db.Column(db.Integer, primary_key=True, index=True)

    nome_piloto = db.Column(db.String(100), nullable=False, index=True)
    regiao = db.Column(db.String(20))
    telefone = db.Column(db.String(20))

    # ✅ Solicitações atribuídas ao piloto
    solicitacoes = db.relationship(
        "Solicitacao",
        back_populates="piloto",
        lazy="select"
    )

    # ✅ UVIS que este piloto atende (vínculo N:N via PilotoUvis)
    vinculos_uvis = db.relationship(
        "PilotoUvis",
        back_populates="piloto",
        lazy="select",
        cascade="all, delete-orphan"
    )


# -------------------------------------------------------------
# VÍNCULO PILOTO ↔ UVIS (N:N)
# - serve para: "piloto ver somente as UVIS ligadas a ele"
# - e para reforçar segurança: piloto só vê OS de UVIS que ele atende
# -------------------------------------------------------------
class PilotoUvis(db.Model):
    __tablename__ = "piloto_uvis"

    id = db.Column(db.Integer, primary_key=True)

    piloto_id = db.Column(
        db.Integer,
        db.ForeignKey("pilotos.id"),
        nullable=False,
        index=True
    )

    uvis_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False,
        index=True
    )

    piloto = db.relationship("Pilotos", back_populates="vinculos_uvis")
    uvis_usuario = db.relationship("Usuario", back_populates="vinculos_pilotos")

    __table_args__ = (
        db.UniqueConstraint("piloto_id", "uvis_usuario_id", name="uq_piloto_uvis"),
        db.Index("ix_piloto_uvis_piloto", "piloto_id"),
        db.Index("ix_piloto_uvis_uvis", "uvis_usuario_id"),
    )


# -------------------------------------------------------------
# SOLICITAÇÃO / ORDEM DE SERVIÇO
# -------------------------------------------------------------
class Solicitacao(db.Model):
    __tablename__ = "solicitacoes"

    id = db.Column(db.Integer, primary_key=True)

    # ----------------------
    # Dados Básicos e Data
    # ----------------------
    data_agendamento = db.Column(db.Date, nullable=False, index=True)
    hora_agendamento = db.Column(db.Time, nullable=False)

    foco = db.Column(db.String(50), nullable=False, index=True)

    # ----------------------
    # Detalhes Operacionais
    # ----------------------
    tipo_visita = db.Column(db.String(50), index=True)
    altura_voo = db.Column(db.String(20), index=True)

    criadouro = db.Column(db.Boolean, default=False)
    apoio_cet = db.Column(db.Boolean, default=False)

    observacao = db.Column(db.Text)

    # ----------------------
    # Endereço
    # ----------------------
    cep = db.Column(db.String(9), nullable=False)
    logradouro = db.Column(db.String(150), nullable=False)
    bairro = db.Column(db.String(100), nullable=False, index=True)
    cidade = db.Column(db.String(100), nullable=False, index=True)
    uf = db.Column(db.String(2), nullable=False, index=True)

    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))

    # Geolocalização
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))

    # Anexos
    anexo_path = db.Column(db.String(255))
    anexo_nome = db.Column(db.String(255))

    # ----------------------
    # Controle Admin
    # ----------------------
    protocolo = db.Column(db.String(50), index=True)
    justificativa = db.Column(db.String(255))

    data_criacao = db.Column(
        db.DateTime,
        default=datetime.now,
        index=True
    )

    status = db.Column(
        db.String(30),
        default="EM ANÁLISE",
        index=True
    )

    # UVIS (usuário) que criou/abriu a OS
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )
    usuario = db.relationship(
        "Usuario",
        back_populates="solicitacoes"
    )

    # Piloto responsável (para dashboard/agenda do piloto)
    piloto_id = db.Column(
        db.Integer,
        db.ForeignKey("pilotos.id"),
        nullable=True,
        index=True
    )
    piloto = db.relationship(
        "Pilotos",
        back_populates="solicitacoes"
    )

    # Equipe responsável (novo)
    equipe_id = db.Column(
        db.Integer,
        db.ForeignKey("equipes.id"),
        nullable=True,
        index=True
    )
    equipe = db.relationship("Equipe", lazy="joined")

    __table_args__ = (
        db.Index("ix_solicitacao_data_status", "data_criacao", "status"),
        db.Index("ix_solicitacao_usuario_data", "usuario_id", "data_criacao"),
        db.Index("ix_solicitacao_piloto_data", "piloto_id", "data_criacao"),
        db.Index("ix_solicitacao_agenda", "data_agendamento", "hora_agendamento"),
    )


# -------------------------------------------------------------
# NOTIFICAÇÕES
# -------------------------------------------------------------
class Notificacao(db.Model):
    __tablename__ = "notificacoes"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    titulo = db.Column(db.String(140), nullable=False)
    mensagem = db.Column(db.Text)
    link = db.Column(db.String(255))

    criada_em = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False,
        index=True
    )

    lida_em = db.Column(db.DateTime, index=True)
    apagada_em = db.Column(db.DateTime, index=True)


# -------------------------------------------------------------
# CLIENTES
# -------------------------------------------------------------
class Clientes(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True, index=True)

    nome_cliente = db.Column(db.String(100), nullable=False, index=True)

    documento = db.Column(db.String(50), unique=True, nullable=False, index=True)

    contato = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100), index=True)
    endereco = db.Column(db.String(255))


# -------------------------------------------------------------
# EQUIPES
# - Uma equipe tem exatamente 2 membros: 1 PILOTO e 1 AUXILIAR
# - A associação fica em EquipePiloto (pivot) com campo "papel"
# -------------------------------------------------------------
class Equipe(db.Model):
    __tablename__ = "equipes"

    id = db.Column(db.Integer, primary_key=True, index=True)

    nome_equipe = db.Column(db.String(100), nullable=False, index=True)
    descricao = db.Column(db.Text)

    regiao = db.Column(db.String(20), index=True)  # opcional (ajuda filtro)
    ativa = db.Column(db.Boolean, default=True, nullable=False, index=True)

    criada_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    membros = db.relationship(
        "EquipePiloto",
        back_populates="equipe",
        lazy="select",
        cascade="all, delete-orphan"
    )

    @property
    def piloto_titular(self):
        return next((m.piloto for m in self.membros if m.papel == "piloto"), None)

    @property
    def piloto_auxiliar(self):
        return next((m.piloto for m in self.membros if m.papel == "auxiliar"), None)


# -------------------------------------------------------------
# VÍNCULO EQUIPE <-> PILOTOS (com papel)
# - papel: "piloto" | "auxiliar"
# -------------------------------------------------------------
class EquipePiloto(db.Model):
    __tablename__ = "equipe_pilotos"

    id = db.Column(db.Integer, primary_key=True)

    equipe_id = db.Column(
        db.Integer,
        db.ForeignKey("equipes.id"),
        nullable=False,
        index=True
    )

    piloto_id = db.Column(
        db.Integer,
        db.ForeignKey("pilotos.id"),
        nullable=False,
        index=True
    )

    # papel na equipe: "piloto" (titular) ou "auxiliar"
    papel = db.Column(db.String(20), nullable=False, index=True)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    equipe = db.relationship("Equipe", back_populates="membros")
    piloto = db.relationship("Pilotos", lazy="joined")

    __table_args__ = (
        # impede duplicar o mesmo piloto na mesma equipe
        db.UniqueConstraint("equipe_id", "piloto_id", name="uq_equipe_piloto_unico"),

        # garante 1 único "piloto" por equipe e 1 único "auxiliar" por equipe
        db.UniqueConstraint("equipe_id", "papel", name="uq_equipe_papel_unico"),

        db.Index("ix_equipe_pilotos_equipe", "equipe_id"),
        db.Index("ix_equipe_pilotos_piloto", "piloto_id"),
        db.Index("ix_equipe_pilotos_papel", "papel"),
    )
