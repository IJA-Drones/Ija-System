from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# -------------------------------------------------------------
# USUÁRIO
# -------------------------------------------------------------
class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome_uvis = db.Column(db.String(100), nullable=False)
    regiao = db.Column(db.String(50))
    codigo_setor = db.Column(db.String(10))

    login = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)

    tipo_usuario = db.Column(db.String(20), default='uvis')

    solicitacoes = db.relationship(
        "Solicitacao",
        backref="autor",
        lazy="select"
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


# -------------------------------------------------------------
# SOLICITAÇÃO DE VOO
# -------------------------------------------------------------
class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'

    id = db.Column(db.Integer, primary_key=True)

    # ----------------------
    # Dados Básicos e Data
    # ----------------------
    data_agendamento = db.Column(db.Date, nullable=False)
    hora_agendamento = db.Column(db.Time, nullable=False)
    foco = db.Column(db.String(50), nullable=False)

    # ----------------------
    # Detalhes Operacionais (NOVOS)
    # ----------------------
    tipo_visita = db.Column(db.String(50))  # Monitoramento, Aedes, Culex
    altura_voo = db.Column(db.String(20))   # 10m, 20m, 30m, 40m
    
    # Perguntas Sim/Não (Salvo como True/False no banco)
    criadouro = db.Column(db.Boolean, default=False) 
    apoio_cet = db.Column(db.Boolean, default=False)
    
    observacao = db.Column(db.Text)         # Texto livre maior

    # ----------------------
    # Endereço
    # ----------------------
    cep = db.Column(db.String(9), nullable=False)
    logradouro = db.Column(db.String(150), nullable=False)
    bairro = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    uf = db.Column(db.String(2), nullable=False)
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))

    # Gealocalização
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))

    # ----------------------
    # Controle Admin
    # ----------------------
    protocolo = db.Column(db.String(50))
    justificativa = db.Column(db.String(255))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="EM ANÁLISE")

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )
    
class Notificacao(db.Model):
    __tablename__ = "notificacoes"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    titulo = db.Column(db.String(140), nullable=False)
    mensagem = db.Column(db.Text)
    link = db.Column(db.String(255))

    criada_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    lida_em = db.Column(db.DateTime)
