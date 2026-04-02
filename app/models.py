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

    # + incluir "equipe_uvis" e "regional"
    # tipos esperados: "admin", "uvis", "operario", "visualizador", "regional", "piloto", "equipe_uvis"
    tipo_usuario = db.Column(db.String(20), default="uvis", index=True)

    # ----------------------------
    # Piloto (já existe)
    # ----------------------------
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    piloto = db.relationship("Pilotos", lazy="joined")

    # ----------------------------
    # Equipe UVIS (NOVO)
    # Essa "conta" representa uma equipe específica de uma UVIS dona.
    # ----------------------------
    equipe_uvis_uvis_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True
    )
    equipe_uvis_nome = db.Column(db.String(100), nullable=True, index=True)

    # relação para pegar a UVIS "dona" da equipe
    equipe_uvis_dona = db.relationship(
        "Usuario",
        foreign_keys=[equipe_uvis_uvis_usuario_id],
        lazy="joined"
    )

    __table_args__ = (
        # evita duas contas de login para a mesma equipe da mesma uvis
        db.UniqueConstraint(
            "equipe_uvis_uvis_usuario_id",
            "equipe_uvis_nome",
            name="uq_usuario_conta_equipe_uvis"
        ),
        db.Index("ix_usuario_equipe_uvis", "equipe_uvis_uvis_usuario_id", "equipe_uvis_nome"),
    )

    # Solicitações criadas por este usuário
    solicitacoes = db.relationship("Solicitacao", back_populates="usuario", lazy="select")

    vinculos_pilotos = db.relationship(
        "PilotoUvis",
        back_populates="uvis_usuario",
        lazy="select",
        cascade="all, delete-orphan"
    )

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
# -------------------------------------------------------------
# AUDITORIA DE USUARIOS
# -------------------------------------------------------------
class AuditoriaUsuario(db.Model):
    __tablename__ = "auditoria_usuarios"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, nullable=True, index=True)
    usuario_nome = db.Column(db.String(100), nullable=False, index=True)
    usuario_login = db.Column(db.String(50), nullable=True, index=True)
    tipo_usuario = db.Column(db.String(20), nullable=True, index=True)

    metodo = db.Column(db.String(10), nullable=False, index=True)
    tipo_evento = db.Column(db.String(20), nullable=False, index=True)
    endpoint = db.Column(db.String(120), nullable=True, index=True)
    path = db.Column(db.String(255), nullable=False, index=True)
    query_string = db.Column(db.Text)

    status_code = db.Column(db.Integer, nullable=False, index=True)
    ip = db.Column(db.String(64), nullable=True, index=True)
    user_agent = db.Column(db.Text)
    referrer = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)


# -------------------------------------------------------------
# EQUIPE UVIS (atÃ© 5 pessoas por UVIS)
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
    tipo_operacao = db.Column(db.String(50), index=True) #monitoramento ou tratamento
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

    origem_retorno_id = db.Column(
        db.Integer,
        db.ForeignKey("solicitacoes.id"),
        nullable=True,
        index=True
    )
    gerada_automaticamente = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )
    origem_retorno = db.relationship(
        "Solicitacao",
        remote_side=[id],
        backref=db.backref("retornos_automaticos", lazy="select")
    )

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
    calculo_dosagem_planejado = db.Column(db.Text)
    calculo_dosagem_planejado_em = db.Column(db.DateTime, index=True)

    tipo_aplicacao = db.Column(db.String(100), index=True)
    quantidade_produto_administrada_ml = db.Column(db.Float)

    pulverizacao_area_l_ha = db.Column(db.Float)

    prefixo_aeronave_pulverizacao = db.Column(db.String(100), index=True)
    prefixo_aeronave_monitoramento = db.Column(db.String(100), index=True)

    quantidade_videos_registradas = db.Column(db.Integer)
    quantidade_imagens_registradas = db.Column(db.Integer)

    imagem_principal = db.Column(db.String(255))
    outras_imagens = db.Column(db.Text)  # JSON array de paths
    video = db.Column(db.String(255))

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
    drone = db.relationship(
        "Drones", 
        foreign_keys=[drone_id], # <--- ISSO RESOLVE O ERRO
        lazy="joined"
    )

    # Relacionamento 2: Drone de Monitoramento
    drone_monitoramento_id = db.Column(db.Integer, db.ForeignKey("drones.id"), nullable=True, index=True)
    drone_monitoramento = db.relationship(
        "Drones", 
        foreign_keys=[drone_monitoramento_id], # <--- ISSO RESOLVE O ERRO
        lazy="joined"
    )

    # Snapshots do primeiro drone
    drone_denominacao = db.Column(db.String(100)) # 'renomacao'
    drone_modelo = db.Column(db.String(100))
    drone_numero_serie = db.Column(db.String(100))
    drone_registro_anatel = db.Column(db.String(50))
    drone_registro_anac = db.Column(db.String(50))


    # Snapshots do drone de monitoramento
    drone_monitoramento_denominacao = db.Column(db.String(100)) #  'renomacao'
    drone_monitoramento_modelo = db.Column(db.String(100))
    drone_monitoramento_numero_serie = db.Column(db.String(100))
    drone_monitoramento_registro_anatel = db.Column(db.String(50))
    drone_monitoramento_registro_anac = db.Column(db.String(50))

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
# LOGS DE VEÍCULO (UNIFICADO: ABS + CCD)
# -------------------------------------------------------------
class LogVeiculo(db.Model):
    __tablename__ = "logs_veiculo"

    id = db.Column(db.Integer, primary_key=True)

    # Identificação e Relacionamentos
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculos.id"), nullable=False, index=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    data_registro = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    # Quilometragem (Essencial para ambos os formulários)
    km_inicial = db.Column(db.Float, nullable=False)
    km_final = db.Column(db.Float, nullable=True)

    # Seção de Checklist Diário (CCD)
    check_diario = db.Column(db.Boolean, default=False) # Define se este registro é o checklist do dia 
    qtd_fazendas_enderecos = db.Column(db.Integer) #Quantos endereços fez no dia (final)
    foto_painel_path = db.Column(db.String(255), nullable=True) # Foto comprovando Nível de Combustível/KM [cite: 62]
    
    # Validação e Assinatura
    assinatura_piloto = db.Column(db.Text) # Armazena o Base64 do seu Canvas 
    observacao = db.Column(db.Text)

    # Relacionamento com os diversos abastecimentos que podem ocorrer
    abastecimentos_detalhados = db.relationship(
        "Abastecimento", 
        back_populates="log_pai", 
        cascade="all, delete-orphan"
    )
    
    # Relacionamentos
    veiculo = db.relationship(
        "Veiculos",
        backref=db.backref("logs", lazy="select", cascade="all, delete-orphan")
    )
    piloto = db.relationship("Pilotos", backref=db.backref("logs_veiculo", lazy="select"))

    @property
    def abastecimentos_ordenados(self):
        return sorted(
            self.abastecimentos_detalhados or [],
            key=lambda item: item.data_hora or self.data_registro or datetime.min
        )

    @property
    def teve_abastecimento(self):
        return bool(self.abastecimentos_detalhados)

    @property
    def qtd_abastecimentos(self):
        return len(self.abastecimentos_detalhados or [])

    @property
    def tipos_abastecimento(self):
        tipos = []
        for item in self.abastecimentos_ordenados:
            tipo = (item.tipo_abastecimento or "").strip()
            if tipo and tipo not in tipos:
                tipos.append(tipo)
        return tipos

    @property
    def tipos_abastecimento_resumo(self):
        return ", ".join(self.tipos_abastecimento)

    @property
    def total_litros_abastecidos(self):
        return sum((item.litros or 0) for item in (self.abastecimentos_detalhados or []))

    @property
    def total_valor_abastecido(self):
        return sum((item.valor_total or 0) for item in (self.abastecimentos_detalhados or []))

    @property
    def ultima_movimentacao_em(self):
        datas = [self.data_registro] if self.data_registro else []
        datas.extend(
            item.data_hora
            for item in (self.abastecimentos_detalhados or [])
            if item.data_hora is not None
        )
        return max(datas) if datas else None

    @property
    def ultimo_km_registrado(self):
        kms = [self.km_inicial or 0]
        kms.extend(
            item.km_registro
            for item in (self.abastecimentos_detalhados or [])
            if item.km_registro is not None
        )
        if self.km_final is not None:
            kms.append(self.km_final)
        return max(kms) if kms else 0

# -------------------------------------------------------------
# ABASTECIMENTOS (Pode haver vários em um turno)
# -------------------------------------------------------------
class Abastecimento(db.Model):
    __tablename__ = "abastecimentos"

    id = db.Column(db.Integer, primary_key=True)
    
    # Vincula ao log do veículo (que é o turno atual do piloto)
    log_veiculo_id = db.Column(db.Integer, db.ForeignKey("logs_veiculo.id"), nullable=False, index=True)
    
    data_hora = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    km_registro = db.Column(db.Float, nullable=False)
    tipo_abastecimento = db.Column(db.String(100), nullable=False) # Tipo registrado na nota fiscal
    litros = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=True)
    
    # Caminho da foto da NF capturada NA HORA (capture="environment")
    foto_nf_path = db.Column(db.String(255), nullable=False)
    
    # Relacionamento
    log_pai = db.relationship("LogVeiculo", back_populates="abastecimentos_detalhados")
# -------------------------------------------------------------
# CHECKLIST SEMANAL DE VEÍCULO
# -------------------------------------------------------------
class ChecklistSemanalVeiculo(db.Model):
    __tablename__ = "checklists_semanais_veiculo"

    id = db.Column(db.Integer, primary_key=True)
    
    # Identificação
    veiculo_id = db.Column(db.Integer, db.ForeignKey("veiculos.id"), nullable=False, index=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    data_registro = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    km_leitura = db.Column(db.Float, nullable=False)

    # Luzes direção / iluminação
    farois_funcionando = db.Column(db.Boolean, default=True)
    setas_funcionando = db.Column(db.Boolean, default=True)
    lanternas_funcionando = db.Column(db.Boolean, default=True)
    piscaalerta_funcionando = db.Column(db.Boolean, default=True)
    condicao_luzes_direcao = db.Column(db.Text) 

    # Luzes painel
    luz_painel = db.Column(db.Boolean, default=True)
    condicao_luz_painel = db.Column(db.Text) 

    # Itens de Manutenção Preventiva
    limpador_parabrisa = db.Column(db.Boolean, default=True)
    agua_radiador = db.Column(db.Boolean, default=True)
    fluido_freio = db.Column(db.Boolean, default=True)
    oleo_motor = db.Column(db.Boolean, default=True)
    condicao_itens_manutencao = db.Column(db.Text)  

    # Itens de Segurança motorista
    vidros = db.Column(db.Boolean, default=True)
    retrovisores = db.Column(db.Boolean, default=True)
    condicao_vidros_retrovisores = db.Column(db.Text)

    pneus = db.Column(db.Boolean, default=True)
    estepe = db.Column(db.Boolean, default=True)
    macaco = db.Column(db.Boolean, default=True)
    triangulo = db.Column(db.Boolean, default=True)
    chave_roda = db.Column(db.Boolean, default=True)
    condicao_pneus_estepe = db.Column(db.Text)

    extintor = db.Column(db.Boolean, default=True)
    cinto_seguranca = db.Column(db.Boolean, default=True)
    condicao_itens_seguranca = db.Column(db.Text) 

    # Itens carro interno
    alarme = db.Column(db.Boolean, default=True)
    ar_condicionado = db.Column(db.Boolean, default=True)
    radio = db.Column(db.Boolean, default=True)
    condicao_itens_carro_interno = db.Column(db.Text)

    giroflex = db.Column(db.Boolean, default=True)
    isqueiro = db.Column(db.Boolean, default=True)
    carregador = db.Column(db.Boolean, default=True)
    condicao_giroflex_isqueiro_carregador = db.Column(db.Text)

    # Itens carro externo (Lataria)
    lataria_frontal = db.Column(db.Boolean, default=True) 
    lataria_lateral = db.Column(db.Boolean, default=True) 
    lataria_traseira = db.Column(db.Boolean, default=True) 
    condicao_lataria = db.Column(db.Text)
    lataria_porta_frontal = db.Column(db.Boolean, default=True) 
    lataria_porta_traseira = db.Column(db.Boolean, default=True) 
    lataria_porta_lateral = db.Column(db.Boolean, default=True) 
    condicao_lataria_portas = db.Column(db.Text)

    parachoque_frontal = db.Column(db.Boolean, default=True)
    parachoque_traseiro = db.Column(db.Boolean, default=True)
    condicao_itens_carro_externo = db.Column(db.Text)

    assinatura_piloto = db.Column(db.Text) # Base64
    
    # Relacionamentos
    veiculo = db.relationship("Veiculos", backref=db.backref("checklists_semanais", lazy="select"))
    piloto = db.relationship("Pilotos", backref=db.backref("checklists_veiculo", lazy="select"))


# -------------------------------------------------------------
# CHECKLIST SEMANAL DE EQUIPAMENTO (DRONE)
# -------------------------------------------------------------
class ChecklistSemanalDrone(db.Model):
    __tablename__ = "checklists_semanais_drone"

    id = db.Column(db.Integer, primary_key=True)
    
    # Identificação
    drone_id = db.Column(db.Integer, db.ForeignKey("drones.id"), nullable=False, index=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    data_registro = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    # Itens do Drone
    helices_status = db.Column(db.Boolean, default=True) # CW e CCW funcional/defeituoso
    condicao_helices = db.Column(db.Text) # Observações sobre as hélices (ex: "Hélice 1 com rachadura leve")

    tanque = db.Column(db.Boolean, default=True) # Tanque/Trem de Pouso/Câmeras
    trem_pouso = db.Column(db.Boolean, default=True)
    cameras = db.Column(db.Boolean, default=True)
    condicao_estrutura = db.Column(db.Text)

    carregador_controle = db.Column(db.Boolean, default=True) # Carregador Controle/WB/Baterias
    baterias = db.Column(db.Boolean, default=True) # WB/Baterias
    condicao_carregador_bateria = db.Column(db.Text)

    cabos_carregador = db.Column(db.Boolean, default=True) # Cabo do carregador / Correia
    correia_pescoco = db.Column(db.Boolean, default=True)
    condicao_cabos_correia = db.Column(db.Text)

    # Quantidades
    num_baterias = db.Column(db.Integer, default=0)
    num_baterias_wb = db.Column(db.Integer, default=0)
    
    observacoes_equipamento = db.Column(db.Text)
    assinatura_piloto = db.Column(db.Text) # Base64
    nome_responsavel = db.Column(db.String(150), index=True) # Nome do piloto que fez o checklist (para facilitar consulta)
    assinatura_piloto_responsavel = db.Column(db.Text) # Base64 da assinatura do piloto (para facilitar consulta)

    # Relacionamentos
    drone = db.relationship("Drones", backref=db.backref("checklists_semanais", lazy="select"))
    piloto = db.relationship("Pilotos", backref=db.backref("checklists_drone", lazy="select"))


# -------------------------------------------------------------
# IMPORTACAO DE LOGS DJI (IMPORTAR EXCEL)
# -------------------------------------------------------------
class DjiFlightLogImport(db.Model):
    __tablename__ = "dji_flight_log_imports"

    id = db.Column(db.Integer, primary_key=True)

    uploaded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(255), nullable=False)
    file_sha256 = db.Column(db.String(64), nullable=False, index=True)

    total_rows = db.Column(db.Integer, nullable=False, default=0)
    imported_rows = db.Column(db.Integer, nullable=False, default=0)
    skipped_rows = db.Column(db.Integer, nullable=False, default=0)

    period_start = db.Column(db.DateTime, index=True)
    period_end = db.Column(db.DateTime, index=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    uploaded_by = db.relationship("Usuario", lazy="joined")
    records = db.relationship(
        "DjiFlightRecord",
        back_populates="import_batch",
        lazy="select",
        cascade="all, delete-orphan",
    )

    @property
    def period_display(self):
        if self.period_start and self.period_end:
            return f"{self.period_start.strftime('%d/%m/%Y %H:%M')} ate {self.period_end.strftime('%d/%m/%Y %H:%M')}"
        return "Periodo nao identificado"


class DjiFlightRecord(db.Model):
    __tablename__ = "dji_flight_records"

    id = db.Column(db.Integer, primary_key=True)

    import_id = db.Column(
        db.Integer,
        db.ForeignKey("dji_flight_log_imports.id"),
        nullable=False,
        index=True,
    )

    source_row_number = db.Column(db.Integer, nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False, unique=True, index=True)

    flight_window = db.Column(db.String(80), nullable=False)
    flight_start = db.Column(db.DateTime, nullable=False, index=True)
    flight_end = db.Column(db.DateTime, nullable=False, index=True)

    location = db.Column(db.Text)
    aircraft_name = db.Column(db.String(120), index=True)
    task_type = db.Column(db.String(80), index=True)
    sprayed_area_ha = db.Column(db.Float, default=0)
    total_amount_l_kg = db.Column(db.Float, default=0)
    flight_duration_seconds = db.Column(db.Integer, default=0)
    flight_duration_label = db.Column(db.String(20))

    crop = db.Column(db.String(80), index=True)
    pilot_name = db.Column(db.String(120), index=True)
    team_name = db.Column(db.String(120), index=True)
    field_name = db.Column(db.String(150), index=True)
    serial_number = db.Column(db.String(120), index=True)

    starting_battery_level = db.Column(db.Integer)
    ending_battery_level = db.Column(db.Integer)
    battery_consumed_level = db.Column(db.Integer)
    battery_sn = db.Column(db.String(120), index=True)

    raw_payload = db.Column(db.Text)
    imported_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    import_batch = db.relationship("DjiFlightLogImport", back_populates="records")
    route_kml = db.relationship(
        "DjiFlightKmlRoute",
        back_populates="flight_record",
        uselist=False,
        lazy="select",
    )

    __table_args__ = (
        db.Index("ix_dji_flight_record_aircraft_start", "aircraft_name", "flight_start"),
        db.Index("ix_dji_flight_record_pilot_start", "pilot_name", "flight_start"),
        db.Index("ix_dji_flight_record_team_start", "team_name", "flight_start"),
        db.Index("ix_dji_flight_record_serial_start", "serial_number", "flight_start"),
    )

    @property
    def duration_display(self):
        total_seconds = int(self.flight_duration_seconds or 0)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def location_short(self):
        value = (self.location or "").strip()
        if not value:
            return "Nao informado"
        return value.split(",")[0].strip() or "Nao informado"

    @property
    def battery_consumption_pct(self):
        if self.battery_consumed_level is not None:
            return self.battery_consumed_level
        if self.starting_battery_level is None or self.ending_battery_level is None:
            return None
        return self.starting_battery_level - self.ending_battery_level


class DjiFlightKmlRoute(db.Model):
    __tablename__ = "dji_flight_kml_routes"

    id = db.Column(db.Integer, primary_key=True)

    flight_record_id = db.Column(
        db.Integer,
        db.ForeignKey("dji_flight_records.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    uploaded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )

    route_code = db.Column(db.String(120), nullable=False, unique=True, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(255), nullable=False)
    file_sha256 = db.Column(db.String(64), nullable=False, unique=True, index=True)

    aircraft_name = db.Column(db.String(120), index=True)
    pilot_name = db.Column(db.String(120), index=True)
    flight_controller_id = db.Column(db.String(120), index=True)
    route_timestamp = db.Column(db.DateTime, index=True)
    mode_selection = db.Column(db.String(40))
    flight_time_raw = db.Column(db.String(40))
    task_area = db.Column(db.Float)
    spray_amount = db.Column(db.Float)

    route_color = db.Column(db.String(20))
    route_width = db.Column(db.Float)
    point_count = db.Column(db.Integer, nullable=False, default=0)
    points_json = db.Column(db.Text, nullable=False)

    imported_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    flight_record = db.relationship("DjiFlightRecord", back_populates="route_kml")
    uploaded_by = db.relationship("Usuario", lazy="joined")

    @property
    def has_points(self):
        return bool(self.point_count)
