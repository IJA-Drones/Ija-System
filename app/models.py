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

    # vínculo opcional com Pilotos (somente quando tipo_usuario="piloto")
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

    # vínculos de pilotos que atendem esta UVIS (para filtro do piloto)
    vinculos_pilotos = db.relationship(
        "PilotoUvis",
        back_populates="uvis_usuario",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # equipe da UVIS (até 5 pessoas) - 1 registro por membro
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

    # Solicitações atribuídas ao piloto
    solicitacoes = db.relationship(
        "Solicitacao",
        back_populates="piloto",
        lazy="select"
    )

    # UVIS que este piloto atende (vínculo N:N via PilotoUvis)
    vinculos_uvis = db.relationship(
        "PilotoUvis",
        back_populates="piloto",
        lazy="select",
        cascade="all, delete-orphan"
    )


# -------------------------------------------------------------
# VÍNCULO PILOTO ↔ UVIS (N:N)
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

    # Dados Básicos e Data
    data_agendamento = db.Column(db.Date, nullable=False, index=True)
    hora_agendamento = db.Column(db.Time, nullable=False)

    foco = db.Column(db.String(50), nullable=False, index=True)

    # Detalhes Operacionais
    tipo_visita = db.Column(db.String(50), index=True)
    altura_voo = db.Column(db.String(20), index=True)

    criadouro = db.Column(db.Boolean, default=False)
    apoio_cet = db.Column(db.Boolean, default=False)

    observacao = db.Column(db.Text)
    area_restrita = db.Column(db.Boolean, default=False, nullable=False)

    # Endereço
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
    perimetro_planejado = db.Column(db.Text)   # JSON com as coordenadas do desenho da UVIS
    perimetro_executado = db.Column(db.Text)   # JSON com o log real do drone (telemetria)

    # Anexos
    anexo_path = db.Column(db.String(255))
    anexo_nome = db.Column(db.String(255))

    # Controle Admin
    protocolo = db.Column(db.String(50), index=True)
    justificativa = db.Column(db.String(255))
    equipe_uvis_nome = db.Column(db.String(100), index=True)

    data_criacao = db.Column(db.DateTime, default=datetime.now, index=True)

    status = db.Column(db.String(30), default="EM ANÁLISE", index=True)

    # UVIS (usuário) que criou/abriu a OS
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )
    usuario = db.relationship("Usuario", back_populates="solicitacoes")

    # Piloto responsável
    piloto_id = db.Column(
        db.Integer,
        db.ForeignKey("pilotos.id"),
        nullable=True,
        index=True
    )
    piloto = db.relationship("Pilotos", back_populates="solicitacoes")

    # Equipe responsável
    equipe_id = db.Column(
        db.Integer,
        db.ForeignKey("equipes.id"),
        nullable=True,
        index=True
    )
    equipe = db.relationship("Equipe", lazy="joined")

    ordem_servico = db.relationship(
        "OrdemServico",
        back_populates="solicitacao",
        uselist=False,
        lazy="select",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index("ix_solicitacao_data_status", "data_criacao", "status"),
        db.Index("ix_solicitacao_usuario_data", "usuario_id", "data_criacao"),
        db.Index("ix_solicitacao_piloto_data", "piloto_id", "data_criacao"),
        db.Index("ix_solicitacao_agenda", "data_agendamento", "hora_agendamento"),
    )


# -------------------------------------------------------------
# ORDEM DE SERVICO (execucao do voo)
# -------------------------------------------------------------
class OrdemServico(db.Model):
    __tablename__ = "ordens_servico"

    id = db.Column(db.Integer, primary_key=True)

    # vínculo 1:1 com a solicitação original
    solicitacao_id = db.Column(
        db.Integer,
        db.ForeignKey("solicitacoes.id"),
        nullable=False,
        unique=True,
        index=True
    )

    # equipe executora
    equipe_id = db.Column(
        db.Integer,
        db.ForeignKey("equipes.id"),
        nullable=False,
        index=True
    )

    # campos do formulario Excel (aba: "formularios")
    identificador_os = db.Column(db.String(100), index=True)
    respondido_por = db.Column(db.String(150), index=True)
    respondido_em = db.Column(db.DateTime, index=True)

    situacao_aplicacao = db.Column(db.String(100), index=True)
    larva_visualizada = db.Column(db.String(20))
    retornar_proxima_semana_monitorar_larvas = db.Column(db.String(20))

    distrito_administrativo = db.Column(db.String(100))
    nome_rf_ace_responsavel_os = db.Column(db.String(200))
    criadouro_os_tipo_volume = db.Column(db.Text)

    data_aplicacao = db.Column(db.Date, index=True)
    hora_inicio_aplicacao = db.Column(db.Time)
    hora_termino_aplicacao = db.Column(db.Time)

    tratamento_adicional_realizado = db.Column(db.String(20))
    quantos_quais = db.Column(db.Text)

    descricao_produto = db.Column(db.String(200))
    formulacao_produto = db.Column(db.String(200))
    dosagem_g_10l = db.Column(db.String(50))

    tipo_aplicacao = db.Column(db.String(100), index=True)
    quantidade_produto_administrada_ml = db.Column(db.Float)

    pulverizacao_area_l_ha = db.Column(db.Float)
    pulverizacao_foco_tempo_estimado_segundos = db.Column(db.Float)
    pulverizacao_foco_l_min = db.Column(db.Float)

    prefixo_aeronave_pulverizacao = db.Column(db.String(100), index=True)
    prefixo_aeronave_monitoramento = db.Column(db.String(100), index=True)

    quantidade_imagens_registradas = db.Column(db.Integer)
    ponta_pulverizacao = db.Column(db.String(100))

    temperatura_c = db.Column(db.Float)
    umidade_relativa_pct = db.Column(db.Float)
    velocidade_vento_kmh = db.Column(db.Float)

    motivo_nao_realizacao = db.Column(db.String(255))
    observacoes = db.Column(db.Text)

    piloto = db.Column(db.String(150), index=True)
    assinatura_piloto = db.Column(db.Text)

    auxiliar = db.Column(db.String(150), index=True)

    proprietario_ou_preposto = db.Column(db.String(200))
    assinatura_proprietario_ou_preposto = db.Column(db.Text)

    # ----------------------------
    # Drone usado na OS (FK) + snapshot
    # ----------------------------
    drone_id = db.Column(db.Integer, db.ForeignKey("drones.id"), nullable=True, index=True)
    drone = db.relationship("Drones", lazy="joined")

    # snapshot dos dados do drone (para histórico)
    drone_renomacao = db.Column(db.String(100))
    drone_modelo = db.Column(db.String(100))
    drone_numero_serie = db.Column(db.String(100))
    drone_registro_anatel = db.Column(db.String(50))
    drone_registro_anac = db.Column(db.String(50))

    solicitacao = db.relationship("Solicitacao", back_populates="ordem_servico")
    equipe = db.relationship("Equipe", back_populates="ordens_servico")

    __table_args__ = (
        db.Index("ix_os_equipe", "equipe_id"),
        db.Index("ix_os_identificador", "identificador_os"),
        db.Index("ix_os_respondido_em", "respondido_em"),
        db.Index("ix_os_data_aplicacao", "data_aplicacao"),
        db.Index("ix_os_equipe_drone", "equipe_id", "drone_id"),
    )


# -------------------------------------------------------------
# NOTIFICACOES
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
# -------------------------------------------------------------
class Equipe(db.Model):
    __tablename__ = "equipes"

    id = db.Column(db.Integer, primary_key=True, index=True)

    nome_equipe = db.Column(db.String(100), nullable=False, index=True)
    descricao = db.Column(db.Text)

    regiao = db.Column(db.String(20), index=True)
    ativa = db.Column(db.Boolean, default=True, nullable=False, index=True)

    criada_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    membros = db.relationship(
        "EquipePiloto",
        back_populates="equipe",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # relacionamento com os equipamentos (Drones/Baterias/Veículos da equipe)
    equipamentos = db.relationship(
        "Equipamentos",
        back_populates="equipe",
        lazy="select"
    )

    ordens_servico = db.relationship(
        "OrdemServico",
        back_populates="equipe",
        lazy="select"
    )

    @property
    def piloto_titular(self):
        return next((m.piloto for m in self.membros if m.papel == "piloto"), None)

    @property
    def piloto_auxiliar(self):
        return next((m.piloto for m in self.membros if m.papel == "auxiliar"), None)


# -------------------------------------------------------------
# VÍNCULO EQUIPE <-> PILOTOS (com papel)
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
    papel = db.Column(db.String(20), nullable=False)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    equipe = db.relationship("Equipe", back_populates="membros")
    piloto = db.relationship("Pilotos", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("equipe_id", "piloto_id", name="uq_equipe_piloto_unico"),
        db.UniqueConstraint("equipe_id", "papel", name="uq_equipe_papel_unico"),
        db.Index("ix_equipe_pilotos_equipe", "equipe_id"),
        db.Index("ix_equipe_pilotos_piloto", "piloto_id"),
        db.Index("ix_equipe_pilotos_papel", "papel"),
    )


# -------------------------------------------------------------
# EQUIPAMENTOS (base) + subclasses (Drones, Baterias, Veículos)
# -------------------------------------------------------------
class Equipamentos(db.Model):
    __tablename__ = "equipamentos"

    id = db.Column(db.Integer, primary_key=True, index=True)

    tipo_equipamento = db.Column(db.String(50), nullable=False, index=True)

    # Status geral (ex: Ativo, Inativo, Em Manutenção)
    status = db.Column(db.String(20), default="Ativo", index=True)

    modelo = db.Column(db.String(100), nullable=False, index=True)

    # RENOMAÇÃO (ex: PLOA 19, ANDRE 020)
    renomacao = db.Column(db.String(100), nullable=False, index=True)

    categoria = db.Column(db.String(100))

    ano_fabricacao = db.Column(db.Integer)
    numero_serie = db.Column(db.String(100), unique=True, index=True)

    # Manutenção
    ultima_manutencao = db.Column(db.Date)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    # vínculo com a equipe
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id"), nullable=True, index=True)
    equipe = db.relationship("Equipe", back_populates="equipamentos")

    __mapper_args__ = {
        "polymorphic_identity": "equipamentos",
        "polymorphic_on": tipo_equipamento
    }


class Drones(Equipamentos):
    __tablename__ = "drones"

    id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), primary_key=True)

    registro_anatel = db.Column(db.String(50), nullable=False, index=True)
    registro_anac = db.Column(db.String(50), nullable=False, unique=True, index=True)

    # pmd (peso máximo de decolagem)
    pmd_kg = db.Column(db.Float, nullable=False)

    baterias = db.relationship(
        "Baterias",
        back_populates="drone_vinculado",
        lazy="select",
        foreign_keys="[Baterias.drone_id]"
    )

    __mapper_args__ = {"polymorphic_identity": "drones"}


class Baterias(Equipamentos):
    __tablename__ = "baterias"

    id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), primary_key=True)

    ciclo = db.Column(db.Integer, default=0)

    # a qual Drone essa bateria pertence
    drone_id = db.Column(db.Integer, db.ForeignKey("drones.id"), nullable=True, index=True)
    drone_vinculado = db.relationship(
        "Drones",
        back_populates="baterias",
        foreign_keys=[drone_id]
    )

    __mapper_args__ = {"polymorphic_identity": "baterias"}


class Veiculos(Equipamentos):
    __tablename__ = "veiculos"

    id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), primary_key=True)

    # FROTA: PROPRIA | ALUGADA
    frota = db.Column(db.String(20), nullable=False, index=True)

    # OPERAÇÃO: PMSP | AGRO (ou outras no futuro)
    operacao = db.Column(db.String(30), nullable=False, index=True)

    placa = db.Column(db.String(10), nullable=False, unique=True, index=True)

    responsavel = db.Column(db.String(120), index=True)

    km_atual = db.Column(db.Float, default=0, nullable=False)
    km_prox_revisao = db.Column(db.Float, nullable=True)

    revisao_marcada_em = db.Column(db.DateTime, nullable=True, index=True)
    revisao_obs = db.Column(db.String(255))

    __mapper_args__ = {"polymorphic_identity": "veiculos"}

    @property
    def km_restante_revisao(self):
        if self.km_prox_revisao is None:
            return None
        try:
            return float(self.km_prox_revisao) - float(self.km_atual or 0)
        except Exception:
            return None


# -------------------------------------------------------------
# LOGS DE VEÍCULO
# -------------------------------------------------------------
class LogVeiculo(db.Model):
    __tablename__ = "logs_veiculo"

    id = db.Column(db.Integer, primary_key=True)

    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculos.id"), nullable=False, index=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)

    data_registro = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    km_inicial = db.Column(db.Float, nullable=False)
    km_final = db.Column(db.Float, nullable=False)

    abasteceu = db.Column(db.Boolean, default=False)
    litros = db.Column(db.Float, nullable=True)
    valor_total = db.Column(db.Float, nullable=True)
    km_no_abastecimento = db.Column(db.Float, nullable=True)

    observacao = db.Column(db.Text)

    veiculo = db.relationship(
        "Veiculos",
        backref=db.backref("logs", lazy="select", cascade="all, delete-orphan")
    )
    piloto = db.relationship("Pilotos", backref=db.backref("logs_veiculo", lazy="select"))