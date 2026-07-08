from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask_login import UserMixin


class Prefeitura(db.Model):
    __tablename__ = "prefeituras"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criada_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    usuarios = db.relationship("Usuario", back_populates="prefeitura", lazy="select")
    solicitacoes = db.relationship("Solicitacao", back_populates="prefeitura", lazy="select")
    clientes = db.relationship("Clientes", back_populates="prefeitura", lazy="select")
    clientes_agro = db.relationship("ClienteAgro", back_populates="prefeitura", lazy="select")
    fornecedores_agro = db.relationship("FornecedorAgro", back_populates="prefeitura", lazy="select")
    orcamentos_agro = db.relationship("OrcamentoAgro", back_populates="prefeitura", lazy="select")
    rds_mapeamento_agro = db.relationship("RdMapeamentoAgro", back_populates="prefeitura", lazy="select")
    contratos_agro = db.relationship("ContratoAgro", back_populates="prefeitura", lazy="select")
    ordens_servico_agro = db.relationship("OrdemServicoAgro", back_populates="prefeitura", lazy="select")
    financeiros_agro = db.relationship("FinanceiroAgro", back_populates="prefeitura", lazy="select")
    financeiros_agro_entradas = db.relationship("FinanceiroAgroEntrada", back_populates="prefeitura", lazy="select")
    financeiros_agro_saidas = db.relationship("FinanceiroAgroSaida", back_populates="prefeitura", lazy="select")
    financeiros_agro_categorias = db.relationship("FinanceiroAgroCategoria", back_populates="prefeitura", lazy="select")
    financeiros_agro_caixa_diarios = db.relationship("FinanceiroAgroCaixaDiario", back_populates="prefeitura", lazy="select")
    pilotos = db.relationship("Pilotos", back_populates="prefeitura", lazy="select")
    pilotos_agro = db.relationship("PilotoAgro", back_populates="prefeitura", lazy="select")
    curriculos_agro = db.relationship("CurriculoAgro", back_populates="prefeitura", lazy="select")
    equipes = db.relationship("Equipe", lazy="select")
    equipes_agro = db.relationship("EquipeAgro", back_populates="prefeitura", lazy="select")
    equipamentos = db.relationship("Equipamentos", back_populates="prefeitura", lazy="select")
    equipamentos_agro = db.relationship("EquipamentoAgro", back_populates="prefeitura", lazy="select")

# -------------------------------------------------------------
# USUÁRIO (login do sistema)
# - UVIS também é um Usuario (tipo_usuario="uvis")
# - Piloto também é um Usuario (tipo_usuario="piloto") e aponta para Pilotos via piloto_id
# -------------------------------------------------------------
class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    nome_uvis = db.Column(db.String(100), nullable=False, index=True)
    regiao = db.Column(db.String(50), index=True)
    codigo_setor = db.Column(db.String(10))

    login = db.Column(db.String(50), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(200), nullable=False)

    # + incluir "equipe_uvis" e "regional"
    # tipos esperados: "dev", "admin", "uvis", "operario", "visualizador", "regional", "piloto", "equipe_uvis", "equipe_oceano"
    tipo_usuario = db.Column(db.String(20), default="uvis", index=True)
    suporte_operacional = db.Column(db.Boolean, nullable=False, default=False, index=True)
    suporte_tecnico = db.Column(db.Boolean, nullable=False, default=False, index=True)

    # ----------------------------
    # Piloto (já existe)
    # ----------------------------
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    piloto = db.relationship("Pilotos", lazy="joined")
    piloto_agro_id = db.Column(db.Integer, db.ForeignKey("pilotos_agro.id"), nullable=True, index=True)
    piloto_agro = db.relationship("PilotoAgro", back_populates="usuario", lazy="joined", foreign_keys=[piloto_agro_id])

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
    prefeitura = db.relationship("Prefeitura", back_populates="usuarios", lazy="joined")

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
    presenca = db.relationship(
        "UsuarioPresenca",
        back_populates="usuario",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

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

    feedbacks_criados = db.relationship(
        "FeedbackTopico",
        foreign_keys="FeedbackTopico.criado_por_id",
        back_populates="criado_por",
        lazy="select",
    )

    feedbacks_da_uvis = db.relationship(
        "FeedbackTopico",
        foreign_keys="FeedbackTopico.uvis_usuario_id",
        back_populates="uvis_usuario",
        lazy="select",
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class FeedbackTopico(db.Model):
    __tablename__ = "feedback_topicos"

    id = db.Column(db.Integer, primary_key=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    uvis_usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    uvis_nome = db.Column(db.String(100), nullable=False, index=True)
    regiao = db.Column(db.String(50), nullable=True, index=True)

    criado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    criado_por_nome = db.Column(db.String(100), nullable=False)
    criado_por_tipo = db.Column(db.String(20), nullable=True, index=True)

    titulo = db.Column(db.String(180), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(30), nullable=False, default="sugestao", index=True)
    setor_suporte = db.Column(db.String(30), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="aberto", index=True)
    prioridade = db.Column(db.String(20), nullable=False, default="media", index=True)

    responsavel_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True)
    resolvido_em = db.Column(db.DateTime, nullable=True, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, index=True)

    prefeitura = db.relationship("Prefeitura", lazy="joined")
    uvis_usuario = db.relationship("Usuario", foreign_keys=[uvis_usuario_id], back_populates="feedbacks_da_uvis", lazy="joined")
    criado_por = db.relationship("Usuario", foreign_keys=[criado_por_id], back_populates="feedbacks_criados", lazy="joined")
    responsavel = db.relationship("Usuario", foreign_keys=[responsavel_id], lazy="joined")
    comentarios = db.relationship(
        "FeedbackComentario",
        back_populates="topico",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="FeedbackComentario.criado_em.asc()",
    )

    __table_args__ = (
        db.Index("ix_feedback_topicos_scope", "prefeitura_id", "regiao", "uvis_usuario_id"),
        db.Index("ix_feedback_topicos_status_updated", "status", "atualizado_em"),
    )


class FeedbackComentario(db.Model):
    __tablename__ = "feedback_comentarios"

    id = db.Column(db.Integer, primary_key=True)
    topico_id = db.Column(db.Integer, db.ForeignKey("feedback_topicos.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    usuario_nome = db.Column(db.String(100), nullable=False)
    usuario_tipo = db.Column(db.String(20), nullable=True, index=True)
    mensagem = db.Column(db.Text, nullable=False)
    interno = db.Column(db.Boolean, nullable=False, default=False, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    topico = db.relationship("FeedbackTopico", back_populates="comentarios", lazy="joined")
    usuario = db.relationship("Usuario", lazy="joined")
    anexos = db.relationship(
        "FeedbackComentarioAnexo",
        back_populates="comentario",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="FeedbackComentarioAnexo.id.asc()",
    )


class FeedbackComentarioAnexo(db.Model):
    __tablename__ = "feedback_comentario_anexos"

    id = db.Column(db.Integer, primary_key=True)
    comentario_id = db.Column(db.Integer, db.ForeignKey("feedback_comentarios.id"), nullable=False, index=True)
    arquivo_path = db.Column(db.String(255), nullable=False)
    arquivo_nome = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    tamanho_bytes = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    comentario = db.relationship("FeedbackComentario", back_populates="anexos", lazy="joined")

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
class WatchdogDeployEvent(db.Model):
    __tablename__ = "watchdog_deploy_events"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="redeploy_triggered", index=True)
    source = db.Column(db.String(60), nullable=True, index=True)
    health_url = db.Column(db.String(255), nullable=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True, index=True)
    recovered_at = db.Column(db.DateTime, nullable=True, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)


class UsuarioPresenca(db.Model):
    __tablename__ = "usuario_presencas"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, unique=True, index=True)

    primeiro_acesso_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    ultimo_acesso_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    login_em = db.Column(db.DateTime, nullable=True, index=True)
    logout_em = db.Column(db.DateTime, nullable=True, index=True)

    ultimo_metodo = db.Column(db.String(10), nullable=True)
    ultimo_endpoint = db.Column(db.String(120), nullable=True, index=True)
    ultimo_path = db.Column(db.String(255), nullable=False, default="/", index=True)
    ultimo_query_string = db.Column(db.Text, nullable=True)

    ip = db.Column(db.String(64), nullable=True, index=True)
    user_agent = db.Column(db.Text, nullable=True)
    referrer = db.Column(db.String(255), nullable=True)

    usuario = db.relationship("Usuario", back_populates="presenca", lazy="joined")


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
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    nome_piloto = db.Column(db.String(100), nullable=False, index=True)
    regiao = db.Column(db.String(20))
    regiao_alternativa = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    prefeitura = db.relationship("Prefeitura", back_populates="pilotos", lazy="joined")

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
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    # Dados Básicos e Data
    data_agendamento = db.Column(db.Date, nullable=False, index=True)
    hora_agendamento = db.Column(db.Time, nullable=False)

    foco = db.Column(db.String(50), nullable=False, index=True)

    # Detalhes Operacionais
    tipo_operacao = db.Column(db.String(50), index=True) #monitoramento ou tratamento
    tipo_visita = db.Column(db.String(50), index=True)
    tipo_imovel = db.Column(db.String(30), index=True)
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
    prefeitura = db.relationship("Prefeitura", back_populates="solicitacoes", lazy="joined")

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
    ordem_servico_equipe_uvis = db.relationship(
        "OrdemServicoEquipeUvis",
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

    dji_kml_route_id = db.Column(
        db.Integer,
        db.ForeignKey("dji_flight_kml_routes.id"),
        nullable=True,
        index=True,
    )
    dji_kml_route = db.relationship(
        "DjiFlightKmlRoute",
        foreign_keys=[dji_kml_route_id],
        lazy="joined",
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


class OrdemServicoEquipeUvis(db.Model):
    __tablename__ = "ordens_servico_equipe_uvis"

    id = db.Column(db.Integer, primary_key=True)

    solicitacao_id = db.Column(
        db.Integer,
        db.ForeignKey("solicitacoes.id"),
        nullable=False,
        unique=True,
        index=True
    )

    equipe_uvis_nome = db.Column(db.String(100), nullable=False, index=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id"), nullable=True, index=True)

    identificador_os = db.Column(db.String(100), index=True)
    respondido_por = db.Column(db.String(150), index=True)
    respondido_em = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(30), nullable=False, default="EM_ANDAMENTO", index=True)

    situacao_aplicacao = db.Column(db.String(100), index=True)
    tratamento_adicional_realizado = db.Column(db.String(20))
    quantos_quais = db.Column(db.Text)
    quantidade_produto_administrada_ml = db.Column(db.Float)
    motivo_nao_realizacao = db.Column(db.String(255))
    larva_visualizada = db.Column(db.String(20))
    retornar_proxima_semana_monitorar_larvas = db.Column(db.String(20))
    retorno_monitoramento_em = db.Column(db.DateTime, index=True)
    observacoes = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        index=True
    )

    solicitacao = db.relationship("Solicitacao", back_populates="ordem_servico_equipe_uvis")
    equipe = db.relationship("Equipe", lazy="joined")


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
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    nome_cliente = db.Column(db.String(100), nullable=False, index=True)

    documento = db.Column(db.String(50), unique=True, nullable=False, index=True)

    contato = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100), index=True)
    endereco = db.Column(db.String(255))
    prefeitura = db.relationship("Prefeitura", back_populates="clientes", lazy="joined")


# -------------------------------------------------------------
# CLIENTES AGRO
# -------------------------------------------------------------
class ClienteAgro(db.Model):
    __tablename__ = "clientes_agro"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    documento = db.Column(db.String(50), unique=True, nullable=True, index=True)
    nome = db.Column(db.String(150), nullable=False, index=True)

    cep = db.Column(db.String(9), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100), nullable=True, index=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    uf = db.Column(db.String(2), nullable=True, index=True)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="clientes_agro", lazy="joined")
    orcamentos = db.relationship(
        "OrcamentoAgro",
        back_populates="cliente",
        lazy="select",
        cascade="all, delete-orphan",
    )
    financeiros = db.relationship("FinanceiroAgro", back_populates="cliente", lazy="select")
    financeiros_entradas = db.relationship("FinanceiroAgroEntrada", back_populates="cliente", lazy="select")
    financeiros_saidas = db.relationship("FinanceiroAgroSaida", back_populates="cliente", lazy="select")


# -------------------------------------------------------------
# FORNECEDORES AGRO
# -------------------------------------------------------------
class FornecedorAgro(db.Model):
    __tablename__ = "fornecedores_agro"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    documento = db.Column(db.String(50), unique=True, nullable=True, index=True)
    nome = db.Column(db.String(150), nullable=False, index=True)

    cep = db.Column(db.String(9), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100), nullable=True, index=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    uf = db.Column(db.String(2), nullable=True, index=True)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="fornecedores_agro", lazy="joined")
    financeiros_saidas = db.relationship("FinanceiroAgroSaida", back_populates="fornecedor", lazy="select")


# -------------------------------------------------------------
# ORCAMENTOS AGRO
# -------------------------------------------------------------
class OrcamentoAgro(db.Model):
    __tablename__ = "orcamentos_agro"

    SERVICO_MAPEAMENTO = "Mapeamento"
    SERVICO_MAPEAMENTO_PULVERIZACAO = "Mapeamento e pulverização"
    SERVICO_PULVERIZACAO = "Pulverização"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    cliente_agro_id = db.Column(db.Integer, db.ForeignKey("clientes_agro.id"), nullable=True, index=True)

    cliente_nome = db.Column(db.String(150), nullable=False, index=True)
    cliente_documento = db.Column(db.String(50), nullable=True, index=True)
    nome_fazenda = db.Column(db.String(150), nullable=False, index=True)
    mapeamento = db.Column(db.Boolean, default=False, nullable=False, index=True)
    risco_operacional = db.Column(db.Text)
    cultura = db.Column(db.String(100), index=True)
    cultura_alternativa = db.Column(db.String(100), index=True)
    servico = db.Column(db.String(50), nullable=False, default=SERVICO_MAPEAMENTO, index=True)
    area_ha = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    elaborado_por_nome = db.Column(db.String(150), index=True)
    preco_base = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    preco_mapeamento = db.Column("preco_monitoramento", db.Numeric(12, 2), nullable=False, default=0)
    preco_pulverizacao = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    preco_pulverizacao_adicional = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    drone_agro_id = db.Column(db.Integer, db.ForeignKey("equipamentos_agro.id"), nullable=True, index=True)
    drone_mapeamento_agro_id = db.Column(db.Integer, db.ForeignKey("equipamentos_agro.id"), nullable=True, index=True)
    drone_tipo = db.Column(db.String(50))
    drone_identificacao = db.Column(db.String(100))
    drone_modelo = db.Column(db.String(100))
    drone_funcao_operacional = db.Column(db.String(30))
    drone_registro_anatel = db.Column(db.String(50))
    drone_registro_anac = db.Column(db.String(50))
    drone_capacidade_tanque_l = db.Column(db.Numeric(10, 2))
    drone_mapeamento_identificacao = db.Column(db.String(100))
    drone_mapeamento_modelo = db.Column(db.String(100))
    drone_mapeamento_funcao_operacional = db.Column(db.String(30))
    drone_mapeamento_registro_anatel = db.Column(db.String(50))
    drone_mapeamento_registro_anac = db.Column(db.String(50))
    possui_produto_aplicado = db.Column(db.Boolean, default=False, nullable=False, index=True)
    produto_aplicado_receituario = db.Column(db.Text)
    inicio_aplicacao_prevista = db.Column(db.Date, index=True)
    fim_aplicacao_prevista = db.Column(db.Date, index=True)

    cep = db.Column(db.String(9), nullable=False)
    logradouro = db.Column(db.String(150), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100), nullable=False, index=True)
    cidade = db.Column(db.String(100), nullable=False, index=True)
    uf = db.Column(db.String(2), nullable=False, index=True)

    anexo_path = db.Column(db.String(255))
    anexo_nome = db.Column(db.String(255))
    protocolo = db.Column(db.String(80), index=True)

    data_criacao = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="orcamentos_agro", lazy="joined")
    cliente = db.relationship("ClienteAgro", back_populates="orcamentos", lazy="joined")
    drone_agro = db.relationship("EquipamentoAgro", foreign_keys=[drone_agro_id], lazy="joined")
    drone_mapeamento_agro = db.relationship("EquipamentoAgro", foreign_keys=[drone_mapeamento_agro_id], lazy="joined")
    contrato = db.relationship(
        "ContratoAgro",
        back_populates="orcamento",
        uselist=False,
        lazy="select",
        cascade="all, delete-orphan",
    )
    rd_mapeamento = db.relationship(
        "RdMapeamentoAgro",
        back_populates="orcamento",
        uselist=False,
        lazy="select",
        cascade="all, delete-orphan",
    )
    ordens_servico = db.relationship("OrdemServicoAgro", back_populates="orcamento", lazy="select")
    financeiros = db.relationship("FinanceiroAgro", back_populates="orcamento", lazy="select")

    __table_args__ = (
        db.Index("ix_orcamentos_agro_cliente_data", "cliente_agro_id", "data_criacao"),
        db.Index("ix_orcamentos_agro_protocolo_data", "protocolo", "data_criacao"),
    )

    @staticmethod
    def _decimal_or_zero(value):
        if value in (None, ""):
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")

    @staticmethod
    def _format_decimal_br(value):
        amount = OrcamentoAgro._decimal_or_zero(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{amount:.2f}".replace(".", ",")

    @classmethod
    def calcular_valor_item(cls, area_ha, valor_por_ha):
        area = cls._decimal_or_zero(area_ha)
        valor = cls._decimal_or_zero(valor_por_ha)
        return (area * valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calcular_valor_total(
        cls,
        area_ha,
        preco_pulverizacao,
        preco_mapeamento=0,
        *,
        mapeamento_ativo=False,
        preco_pulverizacao_adicional=0,
        pulverizacao_adicional_ativa=False,
    ):
        total = cls.calcular_valor_item(area_ha, preco_pulverizacao)
        if mapeamento_ativo:
            total += cls.calcular_valor_item(area_ha, preco_mapeamento)
        if pulverizacao_adicional_ativa:
            total += cls.calcular_valor_item(area_ha, preco_pulverizacao_adicional)
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def culturas_formatadas(self):
        culturas = []
        for cultura in (self.cultura, self.cultura_alternativa):
            valor = (cultura or "").strip()
            if valor and valor not in culturas:
                culturas.append(valor)
        return " / ".join(culturas)

    @property
    def inclui_mapeamento(self):
        return bool(
            self.mapeamento
            or self._decimal_or_zero(self.preco_mapeamento) > 0
            or self.servico in (self.SERVICO_MAPEAMENTO, self.SERVICO_MAPEAMENTO_PULVERIZACAO)
        )

    @property
    def inclui_pulverizacao(self):
        return self._decimal_or_zero(self.preco_pulverizacao) > 0 or self.servico in (
            self.SERVICO_MAPEAMENTO_PULVERIZACAO,
            self.SERVICO_PULVERIZACAO,
        )

    @property
    def inclui_pulverizacao_adicional(self):
        return (
            self._decimal_or_zero(self.preco_pulverizacao_adicional) > 0
            or bool((self.cultura_alternativa or "").strip())
        )

    @property
    def area_ha_formatada(self):
        if self.area_ha in (None, ""):
            return ""
        return self._format_decimal_br(self.area_ha)

    @property
    def estimativa_aplicacao_dias(self):
        if not self.inicio_aplicacao_prevista or not self.fim_aplicacao_prevista:
            return None
        if self.fim_aplicacao_prevista < self.inicio_aplicacao_prevista:
            return None
        return (self.fim_aplicacao_prevista - self.inicio_aplicacao_prevista).days + 1

    @property
    def valor_mapeamento_total(self):
        if not self.inclui_mapeamento:
            return Decimal("0.00")
        return self.calcular_valor_item(self.area_ha, self.preco_mapeamento)

    @property
    def valor_pulverizacao_total(self):
        if not self.inclui_pulverizacao:
            return Decimal("0.00")
        return self.calcular_valor_item(self.area_ha, self.preco_pulverizacao)

    @property
    def valor_pulverizacao_adicional_total(self):
        if not self.inclui_pulverizacao_adicional:
            return Decimal("0.00")
        return self.calcular_valor_item(self.area_ha, self.preco_pulverizacao_adicional)

    @property
    def valor_total_calculado(self):
        return self.calcular_valor_total(
            self.area_ha,
            self.preco_pulverizacao,
            self.preco_mapeamento if self.inclui_mapeamento else 0,
            mapeamento_ativo=self.inclui_mapeamento,
            preco_pulverizacao_adicional=(
                self.preco_pulverizacao_adicional if self.inclui_pulverizacao_adicional else 0
            ),
            pulverizacao_adicional_ativa=self.inclui_pulverizacao_adicional,
        )


# -------------------------------------------------------------
# CONTRATOS AGRO
# -------------------------------------------------------------
class ContratoAgro(db.Model):
    __tablename__ = "contratos_agro"

    STATUS_EM_ELABORACAO = "EM ELABORACAO"
    STATUS_APROVADO = "APROVADO"
    STATUS_OPTIONS = (
        STATUS_EM_ELABORACAO,
        STATUS_APROVADO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    orcamento_agro_id = db.Column(db.Integer, db.ForeignKey("orcamentos_agro.id"), nullable=False, unique=True, index=True)
    equipe_agro_id = db.Column(db.Integer, db.ForeignKey("equipes_agro.id"), nullable=True, index=True)

    status = db.Column(db.String(30), nullable=False, default=STATUS_EM_ELABORACAO, index=True)

    contratante_nome = db.Column(db.String(150), nullable=False, index=True)
    contratante_documento = db.Column(db.String(50), nullable=False, index=True)
    contratante_rg = db.Column(db.String(40), index=True)

    contratante_cep = db.Column(db.String(9), nullable=False)
    contratante_logradouro = db.Column(db.String(150), nullable=False)
    contratante_numero = db.Column(db.String(20), nullable=False)
    contratante_complemento = db.Column(db.String(100))
    contratante_bairro = db.Column(db.String(100), nullable=False, index=True)
    contratante_cidade = db.Column(db.String(100), nullable=False, index=True)
    contratante_uf = db.Column(db.String(2), nullable=False, index=True)

    propriedade_nome = db.Column(db.String(150), nullable=False, index=True)
    propriedade_cep = db.Column(db.String(9), nullable=False)
    propriedade_logradouro = db.Column(db.String(150), nullable=False)
    propriedade_numero = db.Column(db.String(20), nullable=False)
    propriedade_complemento = db.Column(db.String(100))
    propriedade_bairro = db.Column(db.String(100), nullable=False, index=True)
    propriedade_cidade = db.Column(db.String(100), nullable=False, index=True)
    propriedade_uf = db.Column(db.String(2), nullable=False, index=True)

    descricao_servico = db.Column(db.Text, nullable=False)
    cultura = db.Column(db.String(100), index=True)
    cultura_alternativa = db.Column(db.String(100), index=True)
    area_contratada = db.Column(db.String(50))

    valor_total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_mapeamento_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_pulverizacao_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_pulverizacao_adicional_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    prazo_inicio_dias = db.Column(db.Integer, nullable=False, default=10)
    prazo_pagamento_dias = db.Column(db.Integer, nullable=False, default=10)
    cidade_assinatura = db.Column(db.String(100), nullable=False, default="São Paulo")
    foro_cidade = db.Column(db.String(100), nullable=False, default="São Paulo")
    data_assinatura = db.Column(db.Date)
    observacoes_adicionais = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="contratos_agro", lazy="joined")
    orcamento = db.relationship("OrcamentoAgro", back_populates="contrato", lazy="joined")
    equipe = db.relationship("EquipeAgro", back_populates="contratos", lazy="joined")
    ordens_servico = db.relationship("OrdemServicoAgro", back_populates="contrato", lazy="select")
    financeiros = db.relationship("FinanceiroAgro", back_populates="contrato", lazy="select")

    @property
    def culturas_formatadas(self):
        culturas = []
        for cultura in (self.cultura, self.cultura_alternativa):
            valor = (cultura or "").strip()
            if valor and valor not in culturas:
                culturas.append(valor)
        return " / ".join(culturas)

    __table_args__ = (
        db.Index("ix_contratos_agro_orcamento_data", "orcamento_agro_id", "atualizado_em"),
        db.Index("ix_contratos_agro_status_equipe", "status", "equipe_agro_id"),
    )


# -------------------------------------------------------------
# RD DE MAPEAMENTO AGRO
# -------------------------------------------------------------
class RdMapeamentoAgro(db.Model):
    __tablename__ = "rds_mapeamento_agro"

    STATUS_AGUARDANDO_PREENCHIMENTO = "AGUARDANDO PREENCHIMENTO"
    STATUS_PREENCHIDO = "PREENCHIDO"
    STATUS_OPTIONS = (
        STATUS_AGUARDANDO_PREENCHIMENTO,
        STATUS_PREENCHIDO,
    )
    RESPOSTA_SIM = "SIM"
    RESPOSTA_NAO = "NAO"
    RESPOSTA_OPTIONS = (
        RESPOSTA_SIM,
        RESPOSTA_NAO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    orcamento_agro_id = db.Column(db.Integer, db.ForeignKey("orcamentos_agro.id"), nullable=False, unique=True, index=True)
    equipe_agro_id = db.Column(db.Integer, db.ForeignKey("equipes_agro.id"), nullable=True, index=True)
    piloto_agro_id = db.Column(db.Integer, db.ForeignKey("pilotos_agro.id"), nullable=True, index=True)

    status = db.Column(db.String(40), nullable=False, default=STATUS_AGUARDANDO_PREENCHIMENTO, index=True)

    cliente_nome = db.Column(db.String(150), nullable=False, index=True)
    numero_os = db.Column(db.String(80), index=True)
    propriedade_nome = db.Column(db.String(150), nullable=False, index=True)
    municipio = db.Column(db.String(100), nullable=False, index=True)
    uf = db.Column(db.String(2), index=True)
    proprietario_ou_preposto = db.Column(db.String(150))

    tipo_servico = db.Column(db.String(120))
    cultura = db.Column(db.String(150))
    equipamento = db.Column(db.String(150))
    altura_voo_m = db.Column(db.Numeric(10, 2))
    area_ha = db.Column(db.Numeric(12, 2))
    sobreposicao_frontal_pct = db.Column(db.Numeric(10, 2))
    sobreposicao_lateral_pct = db.Column(db.Numeric(10, 2))
    gsd = db.Column(db.String(50))
    outros = db.Column(db.Text)
    data_relatorio = db.Column(db.Date, index=True)

    rede_energia_baixa = db.Column(db.String(3))
    rede_energia_alta_media = db.Column(db.String(3))
    poste = db.Column(db.String(3))
    poste_com_tirante = db.Column(db.String(3))
    acesso_area = db.Column(db.String(3))
    arvores_secas = db.Column(db.String(3))
    outros_area = db.Column(db.Text)

    observacoes = db.Column(db.Text)
    responsavel_nome = db.Column(db.String(150))

    enviado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    preenchido_em = db.Column(db.DateTime, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="rds_mapeamento_agro", lazy="joined")
    orcamento = db.relationship("OrcamentoAgro", back_populates="rd_mapeamento", lazy="joined")
    equipe = db.relationship("EquipeAgro", back_populates="rds_mapeamento", lazy="joined")
    piloto = db.relationship("PilotoAgro", back_populates="rds_mapeamento_preenchidos", lazy="joined")

    __table_args__ = (
        db.Index("ix_rd_mapeamento_status_equipe", "status", "equipe_agro_id"),
        db.Index("ix_rd_mapeamento_orcamento_status", "orcamento_agro_id", "status"),
    )


# -------------------------------------------------------------
# ORDENS DE SERVICO AGRO
# -------------------------------------------------------------
class OrdemServicoAgro(db.Model):
    __tablename__ = "ordens_servico_agro"

    STATUS_PLANEJADA = "PLANEJADA"
    STATUS_EM_EXECUCAO = "EM EXECUCAO"
    STATUS_CONCLUIDA = "CONCLUIDA"
    STATUS_CANCELADA = "CANCELADA"
    STATUS_OPTIONS = (
        STATUS_PLANEJADA,
        STATUS_EM_EXECUCAO,
        STATUS_CONCLUIDA,
        STATUS_CANCELADA,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    contrato_agro_id = db.Column(db.Integer, db.ForeignKey("contratos_agro.id"), nullable=False, index=True)
    orcamento_agro_id = db.Column(db.Integer, db.ForeignKey("orcamentos_agro.id"), nullable=False, index=True)
    equipe_agro_id = db.Column(db.Integer, db.ForeignKey("equipes_agro.id"), nullable=False, index=True)
    piloto_agro_id = db.Column(db.Integer, db.ForeignKey("pilotos_agro.id"), nullable=True, index=True)

    drone_pulverizacao_id = db.Column(db.Integer, db.ForeignKey("equipamentos_agro.id"), nullable=True, index=True)
    drone_mapeamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos_agro.id"), nullable=True, index=True)

    identificador_os = db.Column(db.String(50), nullable=False, unique=True, index=True)
    status = db.Column(db.String(30), nullable=False, default=STATUS_PLANEJADA, index=True)
    data_aplicacao = db.Column(db.Date, index=True)
    periodo_aplicacao = db.Column(db.String(120))

    cliente_nome = db.Column(db.String(150), nullable=False, index=True)
    propriedade_nome = db.Column(db.String(150), nullable=False, index=True)
    cultura = db.Column(db.String(100), index=True)
    servico = db.Column(db.String(50), index=True)
    protocolo = db.Column(db.String(80), index=True)
    cidade_operacao = db.Column(db.String(100), index=True)
    uf_operacao = db.Column(db.String(2), index=True)

    drone_pulverizacao_identificacao = db.Column(db.String(100))
    drone_pulverizacao_modelo = db.Column(db.String(100))
    drone_pulverizacao_tipo = db.Column(db.String(50))
    drone_pulverizacao_registro_anatel = db.Column(db.String(50))
    drone_pulverizacao_registro_anac = db.Column(db.String(50))

    drone_mapeamento_identificacao = db.Column(db.String(100))
    drone_mapeamento_modelo = db.Column(db.String(100))
    drone_mapeamento_tipo = db.Column(db.String(50))
    drone_mapeamento_registro_anatel = db.Column(db.String(50))
    drone_mapeamento_registro_anac = db.Column(db.String(50))

    altura_voo_m = db.Column(db.Numeric(10, 2))
    largura_faixa_m = db.Column(db.Numeric(10, 2))
    ponta_pulverizacao = db.Column(db.String(100))
    mapeamento_descricao = db.Column(db.String(120))

    temperatura_min_c = db.Column(db.Numeric(10, 2))
    temperatura_max_c = db.Column(db.Numeric(10, 2))
    umidade_min_pct = db.Column(db.Numeric(10, 2))
    umidade_max_pct = db.Column(db.Numeric(10, 2))
    vento_min_kmh = db.Column(db.Numeric(10, 2))
    vento_max_kmh = db.Column(db.Numeric(10, 2))

    area_total_ha = db.Column(db.Numeric(12, 2))
    total_calda_l = db.Column(db.Numeric(12, 2))
    media_aplicada_l_ha = db.Column(db.Numeric(12, 2))
    taxa_aplicacao_l_ha = db.Column(db.Numeric(12, 2))
    tipo_aplicacao = db.Column(db.String(100))

    produto_aplicado = db.Column(db.String(200))
    formulacao_produto = db.Column(db.String(200))
    dosagem = db.Column(db.String(100))
    classe_toxica = db.Column(db.String(100))

    relatorio_pdf_path = db.Column(db.String(255))
    relatorio_pdf_nome = db.Column(db.String(255))
    mapa_aplicacao_path = db.Column(db.String(255))
    mapa_aplicacao_nome = db.Column(db.String(255))
    observacoes = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)
    finalizado_em = db.Column(db.DateTime, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="ordens_servico_agro", lazy="joined")
    contrato = db.relationship("ContratoAgro", back_populates="ordens_servico", lazy="joined")
    orcamento = db.relationship("OrcamentoAgro", back_populates="ordens_servico", lazy="joined")
    equipe = db.relationship("EquipeAgro", back_populates="ordens_servico", lazy="joined")
    piloto = db.relationship("PilotoAgro", back_populates="ordens_servico", lazy="joined")
    drone_pulverizacao = db.relationship("EquipamentoAgro", foreign_keys=[drone_pulverizacao_id], back_populates="ordens_servico_pulverizacao", lazy="joined")
    drone_mapeamento = db.relationship("EquipamentoAgro", foreign_keys=[drone_mapeamento_id], back_populates="ordens_servico_mapeamento", lazy="joined")
    financeiros = db.relationship("FinanceiroAgro", back_populates="ordem_servico", lazy="select")

    __table_args__ = (
        db.Index("ix_os_agro_status_equipe", "status", "equipe_agro_id"),
        db.Index("ix_os_agro_contrato_data", "contrato_agro_id", "data_aplicacao"),
        db.Index("ix_os_agro_piloto_status", "piloto_agro_id", "status"),
    )


# -------------------------------------------------------------
# FINANCEIRO AGRO
# -------------------------------------------------------------
class FinanceiroAgro(db.Model):
    __tablename__ = "financeiro_agro"

    STATUS_PENDENTE = "PENDENTE"
    STATUS_PARCIAL = "PARCIAL"
    STATUS_RECEBIDO = "RECEBIDO"
    STATUS_VENCIDO = "VENCIDO"
    STATUS_CANCELADO = "CANCELADO"
    STATUS_OPTIONS = (
        STATUS_PENDENTE,
        STATUS_PARCIAL,
        STATUS_RECEBIDO,
        STATUS_VENCIDO,
        STATUS_CANCELADO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    cliente_agro_id = db.Column(db.Integer, db.ForeignKey("clientes_agro.id"), nullable=True, index=True)
    orcamento_agro_id = db.Column(db.Integer, db.ForeignKey("orcamentos_agro.id"), nullable=True, index=True)
    contrato_agro_id = db.Column(db.Integer, db.ForeignKey("contratos_agro.id"), nullable=False, index=True)
    ordem_servico_agro_id = db.Column(db.Integer, db.ForeignKey("ordens_servico_agro.id"), nullable=True, index=True)
    banco_agro_id = db.Column(db.Integer, db.ForeignKey("banco_agro.id"), nullable=True, index=True)

    cliente_nome = db.Column(db.String(150), nullable=False, index=True)
    cultura = db.Column(db.String(100), index=True)
    forma_recebimento = db.Column(db.String(50))
    status = db.Column(db.String(30), nullable=False, default=STATUS_PENDENTE, index=True)
    observacoes = db.Column(db.Text)

    competencia_mes = db.Column(db.Integer, index=True)
    competencia_ano = db.Column(db.Integer, index=True)

    data_elaboracao_contrato = db.Column(db.Date, index=True)
    data_servico_executado = db.Column(db.Date, index=True)
    data_vencimento = db.Column(db.Date, nullable=False, index=True)
    data_recebimento = db.Column(db.Date, index=True)

    area_mapeamento_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_mapeamento_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_mapeamento = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    area_pulverizacao_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    area_pulverizada_real_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_pulverizacao_ha = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_pulverizacao = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    valor_total_contrato = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_recebido = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    comissao_por_ha = db.Column(db.Numeric(12, 2), nullable=False, default=8)
    valor_comissao = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    comissao_cooperativa_por_ha = db.Column(db.Numeric(12, 2), nullable=False, default=10)
    valor_comissao_cooperativa = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="financeiros_agro", lazy="joined")
    cliente = db.relationship("ClienteAgro", back_populates="financeiros", lazy="joined")
    orcamento = db.relationship("OrcamentoAgro", back_populates="financeiros", lazy="joined")
    contrato = db.relationship("ContratoAgro", back_populates="financeiros", lazy="joined")
    ordem_servico = db.relationship("OrdemServicoAgro", back_populates="financeiros", lazy="joined")
    banco_agro = db.relationship("BancoAgro", back_populates="financeiros_agro", lazy="joined")

    __table_args__ = (
        db.Index("ix_financeiro_agro_status_vencimento", "status", "data_vencimento"),
        db.Index("ix_financeiro_agro_competencia", "competencia_ano", "competencia_mes"),
        db.Index("ix_financeiro_agro_contrato_vencimento", "contrato_agro_id", "data_vencimento"),
    )

    @staticmethod
    def _decimal_or_zero(value):
        if value in (None, ""):
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")

    @classmethod
    def calcular_total_item(cls, area_ha, valor_por_ha):
        area = cls._decimal_or_zero(area_ha)
        valor = cls._decimal_or_zero(valor_por_ha)
        return (area * valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calcular_total_comissao(cls, area_ha, valor_por_ha):
        return cls.calcular_total_item(area_ha, valor_por_ha)

    @property
    def total_comissoes(self):
        return (
            self._decimal_or_zero(self.valor_comissao)
            + self._decimal_or_zero(self.valor_comissao_cooperativa)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def valor_liquido_previsto(self):
        return (
            self._decimal_or_zero(self.valor_total_contrato) - self.total_comissoes
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def valor_recebido_decimal(self):
        return self._decimal_or_zero(self.valor_recebido).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def saldo_receber(self):
        saldo = self._decimal_or_zero(self.valor_total_contrato) - self.valor_recebido_decimal
        if saldo < Decimal("0"):
            saldo = Decimal("0")
        return saldo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BancoAgro(db.Model):
    __tablename__ = "banco_agro"

    TIPO_CORRENTE = "CORRENTE"
    TIPO_POUPANCA = "POUPANCA"
    TIPO_CAIXA = "CAIXA"
    TIPO_OPTIONS = (
        TIPO_CORRENTE,
        TIPO_POUPANCA,
        TIPO_CAIXA,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    nome = db.Column(db.String(120), nullable=False, index=True)
    banco_nome = db.Column(db.String(120), nullable=False, index=True)
    agencia = db.Column(db.String(20))
    conta = db.Column(db.String(40))
    tipo_conta = db.Column(db.String(20), nullable=False, default=TIPO_CORRENTE, index=True)
    saldo_inicial = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    saldo_previsto = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    saldo_atual = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    observacoes = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", lazy="joined")
    financeiros_agro = db.relationship("FinanceiroAgro", back_populates="banco_agro", lazy="select")
    financeiros_agro_entradas = db.relationship("FinanceiroAgroEntrada", back_populates="banco_agro", lazy="select")
    financeiros_agro_saidas = db.relationship("FinanceiroAgroSaida", back_populates="banco_agro", lazy="select")

    __table_args__ = (
        db.Index("ix_banco_agro_nome_ativo", "nome", "ativo"),
    )

    @property
    def saldo_inicial_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_inicial)

    @property
    def saldo_previsto_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_previsto)

    @property
    def saldo_atual_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_atual)


class FinanceiroAgroCategoria(db.Model):
    __tablename__ = "financeiro_agro_categorias"

    TIPO_ENTRADA = "ENTRADA"
    TIPO_SAIDA = "SAIDA"
    TIPO_OPTIONS = (
        TIPO_ENTRADA,
        TIPO_SAIDA,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    tipo_movimento = db.Column(db.String(20), nullable=False, index=True)
    nome = db.Column(db.String(120), nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="financeiros_agro_categorias", lazy="joined")
    subcategorias = db.relationship(
        "FinanceiroAgroSubcategoria",
        back_populates="categoria",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="FinanceiroAgroSubcategoria.nome",
    )

    __table_args__ = (
        db.UniqueConstraint("prefeitura_id", "tipo_movimento", "nome", name="uq_financeiro_agro_categoria_pref_tipo_nome"),
        db.Index("ix_financeiro_agro_categoria_pref_tipo_ativo", "prefeitura_id", "tipo_movimento", "ativo"),
    )


class FinanceiroAgroSubcategoria(db.Model):
    __tablename__ = "financeiro_agro_subcategorias"

    id = db.Column(db.Integer, primary_key=True, index=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("financeiro_agro_categorias.id"), nullable=False, index=True)
    nome = db.Column(db.String(120), nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    categoria = db.relationship("FinanceiroAgroCategoria", back_populates="subcategorias", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("categoria_id", "nome", name="uq_financeiro_agro_subcategoria_categoria_nome"),
        db.Index("ix_financeiro_agro_subcategoria_categoria_ativo", "categoria_id", "ativo"),
    )


class FinanceiroAgroSaida(db.Model):
    __tablename__ = "financeiro_agro_saidas"

    TIPO_DESPESA = "DESPESA"
    TIPO_IMPOSTO = "IMPOSTO"
    TIPO_RETENCAO = "RETENCAO"
    TIPO_OUTRA_SAIDA = "OUTRA_SAIDA"
    TIPO_OPTIONS = (
        TIPO_DESPESA,
        TIPO_IMPOSTO,
        TIPO_RETENCAO,
        TIPO_OUTRA_SAIDA,
    )

    STATUS_PENDENTE = "PENDENTE"
    STATUS_PAGO = "PAGO"
    STATUS_VENCIDO = "VENCIDO"
    STATUS_CANCELADO = "CANCELADO"
    STATUS_OPTIONS = (
        STATUS_PENDENTE,
        STATUS_PAGO,
        STATUS_VENCIDO,
        STATUS_CANCELADO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    cliente_agro_id = db.Column(db.Integer, db.ForeignKey("clientes_agro.id"), nullable=True, index=True)
    fornecedor_agro_id = db.Column(db.Integer, db.ForeignKey("fornecedores_agro.id"), nullable=True, index=True)
    banco_agro_id = db.Column(db.Integer, db.ForeignKey("banco_agro.id"), nullable=True, index=True)

    tipo_saida = db.Column(db.String(30), nullable=False, default=TIPO_DESPESA, index=True)
    categoria = db.Column(db.String(120), nullable=False, index=True)
    subcategoria = db.Column(db.String(120), index=True)
    descricao = db.Column(db.String(180), nullable=False)
    documento_referencia = db.Column(db.String(80), index=True)
    detalhamento_imposto = db.Column(db.String(180))
    favorecido = db.Column(db.String(150), index=True)
    cep = db.Column(db.String(9), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100), nullable=True, index=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    uf = db.Column(db.String(2), nullable=True, index=True)
    forma_pagamento = db.Column(db.String(50))
    status = db.Column(db.String(30), nullable=False, default=STATUS_PENDENTE, index=True)
    observacoes = db.Column(db.Text)

    competencia_mes = db.Column(db.Integer, index=True)
    competencia_ano = db.Column(db.Integer, index=True)

    data_lancamento = db.Column(db.Date, index=True)
    data_emissao = db.Column(db.Date, index=True)
    data_vencimento = db.Column(db.Date, nullable=False, index=True)
    data_pagamento = db.Column(db.Date, index=True)
    grupo_lancamento = db.Column(db.String(36), index=True)
    parcela_numero = db.Column(db.Integer, nullable=False, default=1)
    parcela_total = db.Column(db.Integer, nullable=False, default=1)

    valor = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="financeiros_agro_saidas", lazy="joined")
    cliente = db.relationship("ClienteAgro", back_populates="financeiros_saidas", lazy="joined")
    fornecedor = db.relationship("FornecedorAgro", back_populates="financeiros_saidas", lazy="joined")
    banco_agro = db.relationship("BancoAgro", back_populates="financeiros_agro_saidas", lazy="joined")

    __table_args__ = (
        db.Index("ix_financeiro_agro_saidas_competencia", "competencia_ano", "competencia_mes"),
        db.Index("ix_financeiro_agro_saidas_status_vencimento", "status", "data_vencimento"),
        db.Index("ix_financeiro_agro_saidas_tipo_status", "tipo_saida", "status"),
    )

    @property
    def valor_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.valor)


class FinanceiroAgroEntrada(db.Model):
    __tablename__ = "financeiro_agro_entradas"

    CATEGORIA_CONTRATO_SOFTWARE = "Contrato de software"
    CATEGORIA_OUTRA_ENTRADA = "Outra entrada"
    CATEGORIA_OPTIONS = (
        CATEGORIA_CONTRATO_SOFTWARE,
        CATEGORIA_OUTRA_ENTRADA,
    )

    STATUS_PENDENTE = "PENDENTE"
    STATUS_RECEBIDO = "RECEBIDO"
    STATUS_VENCIDO = "VENCIDO"
    STATUS_CANCELADO = "CANCELADO"
    STATUS_OPTIONS = (
        STATUS_PENDENTE,
        STATUS_RECEBIDO,
        STATUS_VENCIDO,
        STATUS_CANCELADO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    cliente_agro_id = db.Column(db.Integer, db.ForeignKey("clientes_agro.id"), nullable=True, index=True)
    banco_agro_id = db.Column(db.Integer, db.ForeignKey("banco_agro.id"), nullable=True, index=True)

    categoria = db.Column(db.String(120), nullable=False, index=True)
    subcategoria = db.Column(db.String(120), index=True)
    descricao = db.Column(db.String(180), nullable=False)
    documento_referencia = db.Column(db.String(80), index=True)
    cliente_nome = db.Column(db.String(150), nullable=False, index=True)
    cep = db.Column(db.String(9), nullable=True)
    logradouro = db.Column(db.String(150), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100), nullable=True, index=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    uf = db.Column(db.String(2), nullable=True, index=True)
    forma_recebimento = db.Column(db.String(50))
    status = db.Column(db.String(30), nullable=False, default=STATUS_PENDENTE, index=True)
    observacoes = db.Column(db.Text)

    competencia_mes = db.Column(db.Integer, index=True)
    competencia_ano = db.Column(db.Integer, index=True)

    data_lancamento = db.Column(db.Date, index=True)
    data_emissao = db.Column(db.Date, index=True)
    data_vencimento = db.Column(db.Date, nullable=False, index=True)
    data_recebimento = db.Column(db.Date, index=True)
    grupo_lancamento = db.Column(db.String(36), index=True)
    parcela_numero = db.Column(db.Integer, nullable=False, default=1)
    parcela_total = db.Column(db.Integer, nullable=False, default=1)

    valor = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="financeiros_agro_entradas", lazy="joined")
    cliente = db.relationship("ClienteAgro", back_populates="financeiros_entradas", lazy="joined")
    banco_agro = db.relationship("BancoAgro", back_populates="financeiros_agro_entradas", lazy="joined")

    __table_args__ = (
        db.Index("ix_financeiro_agro_entradas_competencia", "competencia_ano", "competencia_mes"),
        db.Index("ix_financeiro_agro_entradas_status_vencimento", "status", "data_vencimento"),
        db.Index("ix_financeiro_agro_entradas_categoria_status", "categoria", "status"),
    )

    @property
    def valor_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.valor)


class FinanceiroAgroCaixaDiario(db.Model):
    __tablename__ = "financeiro_agro_caixa_diario"

    STATUS_ABERTO = "ABERTO"
    STATUS_FECHADO = "FECHADO"
    STATUS_OPTIONS = (
        STATUS_ABERTO,
        STATUS_FECHADO,
    )

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    data_caixa = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ABERTO, index=True)

    saldo_anterior = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    saldo_abertura = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_entradas = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_saidas = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    saldo_fechamento = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    aberto_por_nome = db.Column(db.String(120))
    fechado_por_nome = db.Column(db.String(120))
    observacoes_abertura = db.Column(db.Text)
    observacoes_fechamento = db.Column(db.Text)

    aberto_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    fechado_em = db.Column(db.DateTime, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="financeiros_agro_caixa_diarios", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("prefeitura_id", "data_caixa", name="uq_financeiro_agro_caixa_diario_prefeitura_data"),
        db.Index("ix_financeiro_agro_caixa_diario_status_data", "status", "data_caixa"),
    )

    @property
    def saldo_anterior_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_anterior)

    @property
    def saldo_abertura_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_abertura)

    @property
    def total_entradas_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.total_entradas)

    @property
    def total_saidas_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.total_saidas)

    @property
    def saldo_fechamento_decimal(self):
        return FinanceiroAgro._decimal_or_zero(self.saldo_fechamento)


class FinanceiroAgroCompetenciaControle(db.Model):
    __tablename__ = "financeiro_agro_competencia_controle"

    id = db.Column(db.Integer, primary_key=True, index=True)
    competencia_ano = db.Column(db.Integer, nullable=False, index=True)
    competencia_mes = db.Column(db.Integer, nullable=False, index=True)
    liberado = db.Column(db.Boolean, nullable=False, default=False, index=True)
    atualizado_por_nome = db.Column(db.String(120))
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("competencia_ano", "competencia_mes", name="uq_financeiro_agro_competencia_controle"),
        db.Index("ix_financeiro_agro_competencia_controle_ano_mes", "competencia_ano", "competencia_mes"),
    )


# -------------------------------------------------------------
# EQUIPES AGRO
# -------------------------------------------------------------
class EquipeAgro(db.Model):
    __tablename__ = "equipes_agro"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

    nome = db.Column(db.String(120), nullable=False, index=True)
    descricao = db.Column(db.Text)
    ativa = db.Column(db.Boolean, default=True, nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="equipes_agro", lazy="joined")
    contratos = db.relationship("ContratoAgro", back_populates="equipe", lazy="select")
    rds_mapeamento = db.relationship("RdMapeamentoAgro", back_populates="equipe", lazy="select")
    ordens_servico = db.relationship("OrdemServicoAgro", back_populates="equipe", lazy="select")
    pilotos = db.relationship("PilotoAgro", back_populates="equipe", lazy="select")
    equipamentos = db.relationship("EquipamentoAgro", back_populates="equipe", lazy="select")


# -------------------------------------------------------------
# PILOTOS AGRO
# -------------------------------------------------------------
class PilotoAgro(db.Model):
    __tablename__ = "pilotos_agro"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    equipe_agro_id = db.Column(db.Integer, db.ForeignKey("equipes_agro.id"), nullable=True, index=True)

    nome = db.Column(db.String(120), nullable=False, index=True)
    telefone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="pilotos_agro", lazy="joined")
    equipe = db.relationship("EquipeAgro", back_populates="pilotos", lazy="joined")
    rds_mapeamento_preenchidos = db.relationship("RdMapeamentoAgro", back_populates="piloto", lazy="select")
    ordens_servico = db.relationship("OrdemServicoAgro", back_populates="piloto", lazy="select")
    usuario = db.relationship("Usuario", back_populates="piloto_agro", uselist=False, foreign_keys="Usuario.piloto_agro_id")


# -------------------------------------------------------------
# BANCO DE TALENTOS AGRO
# -------------------------------------------------------------
class CurriculoAgro(db.Model):
    __tablename__ = "curriculos_agro"

    STATUS_NOVO = "NOVO"
    STATUS_EM_ANALISE = "EM_ANALISE"
    STATUS_ENTREVISTA = "ENTREVISTA"
    STATUS_APROVADO = "APROVADO"
    STATUS_ARQUIVADO = "ARQUIVADO"
    STATUS_OPTIONS = (
        STATUS_NOVO,
        STATUS_EM_ANALISE,
        STATUS_ENTREVISTA,
        STATUS_APROVADO,
        STATUS_ARQUIVADO,
    )

    ANALISE_PROCESSANDO = "PROCESSANDO"
    ANALISE_CONCLUIDA = "CONCLUIDA"
    ANALISE_ERRO = "ERRO"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    criado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(180), nullable=False, index=True)
    email = db.Column(db.String(180), index=True)
    telefone = db.Column(db.String(40), index=True)
    cidade = db.Column(db.String(120), index=True)
    uf = db.Column(db.String(2), index=True)
    linkedin = db.Column(db.String(255))

    titulo_profissional = db.Column(db.String(180), index=True)
    area_principal = db.Column(db.String(180), index=True)
    resumo_perfil = db.Column(db.Text)
    objetivo_profissional = db.Column(db.Text)
    habilidades_tecnicas = db.Column(db.JSON, nullable=False, default=list)
    habilidades_comportamentais = db.Column(db.JSON, nullable=False, default=list)
    areas_atuacao = db.Column(db.JSON, nullable=False, default=list)
    areas_desenvolvimento = db.Column(db.JSON, nullable=False, default=list)
    experiencias = db.Column(db.JSON, nullable=False, default=list)
    formacoes = db.Column(db.JSON, nullable=False, default=list)
    certificacoes = db.Column(db.JSON, nullable=False, default=list)
    idiomas = db.Column(db.JSON, nullable=False, default=list)

    status = db.Column(db.String(30), nullable=False, default=STATUS_NOVO, index=True)
    observacoes = db.Column(db.Text)
    analise_status = db.Column(db.String(30), nullable=False, default=ANALISE_PROCESSANDO, index=True)
    analise_erro = db.Column(db.Text)
    gemini_modelo = db.Column(db.String(100))
    analisado_em = db.Column(db.DateTime, index=True)

    arquivo_nome_original = db.Column(db.String(255), nullable=False)
    arquivo_mime_type = db.Column(db.String(100), nullable=False, default="application/pdf")
    arquivo_tamanho = db.Column(db.Integer, nullable=False)
    arquivo_sha256 = db.Column(db.String(64), nullable=False, index=True)
    dropbox_path = db.Column(db.String(500), nullable=False, unique=True)
    dropbox_rev = db.Column(db.String(100))

    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True, onupdate=datetime.now)

    prefeitura = db.relationship("Prefeitura", back_populates="curriculos_agro", lazy="joined")
    criado_por = db.relationship("Usuario", foreign_keys=[criado_por_usuario_id], lazy="joined")

    __table_args__ = (
        db.UniqueConstraint(
            "prefeitura_id",
            "arquivo_sha256",
            name="uq_curriculos_agro_prefeitura_arquivo_sha256",
        ),
        db.Index("ix_curriculos_agro_status_analise", "status", "analise_status"),
        db.Index("ix_curriculos_agro_area_criado_em", "area_principal", "criado_em"),
    )


# -------------------------------------------------------------
# EQUIPAMENTOS AGRO
# -------------------------------------------------------------
class EquipamentoAgro(db.Model):
    __tablename__ = "equipamentos_agro"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    equipe_agro_id = db.Column(db.Integer, db.ForeignKey("equipes_agro.id"), nullable=True, index=True)

    tipo = db.Column(db.String(50), nullable=False, index=True)
    modelo = db.Column(db.String(100), nullable=False, index=True)
    identificacao = db.Column(db.String(100), nullable=False, index=True)
    numero_serie = db.Column(db.String(100), unique=True, index=True)
    status = db.Column(db.String(30), default="Ativo", nullable=False, index=True)
    funcao_operacional = db.Column(db.String(30), index=True)
    registro_anatel = db.Column(db.String(50), index=True)
    registro_anac = db.Column(db.String(50), index=True)
    capacidade_tanque_l = db.Column(db.Numeric(10, 2))
    largura_faixa_m = db.Column(db.Numeric(10, 2))
    altura_voo_padrao_m = db.Column(db.Numeric(10, 2))
    ponta_pulverizacao = db.Column(db.String(100))
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    prefeitura = db.relationship("Prefeitura", back_populates="equipamentos_agro", lazy="joined")
    equipe = db.relationship("EquipeAgro", back_populates="equipamentos", lazy="joined")
    ordens_servico_pulverizacao = db.relationship("OrdemServicoAgro", foreign_keys="[OrdemServicoAgro.drone_pulverizacao_id]", back_populates="drone_pulverizacao", lazy="select")
    ordens_servico_mapeamento = db.relationship("OrdemServicoAgro", foreign_keys="[OrdemServicoAgro.drone_mapeamento_id]", back_populates="drone_mapeamento", lazy="select")


# -------------------------------------------------------------
# EQUIPES
# -------------------------------------------------------------
class Equipe(db.Model):
    __tablename__ = "equipes"

    id = db.Column(db.Integer, primary_key=True, index=True)
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)

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

    logs_veiculo = db.relationship(
        "LogVeiculo",
        back_populates="equipe",
        lazy="select"
    )

    checklists_veiculo = db.relationship(
        "ChecklistSemanalVeiculo",
        back_populates="equipe",
        lazy="select"
    )

    checklists_drone = db.relationship(
        "ChecklistSemanalDrone",
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
    prefeitura_id = db.Column(db.Integer, db.ForeignKey("prefeituras.id"), nullable=True, index=True)
    prefeitura = db.relationship("Prefeitura", back_populates="equipamentos", lazy="joined")

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
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id"), nullable=True, index=True)
    data_registro = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    # Quilometragem (Essencial para ambos os formulários)
    km_inicial = db.Column(db.Float, nullable=False)
    km_final = db.Column(db.Float, nullable=True)

    # Seção de Checklist Diário (CCD)
    check_diario = db.Column(db.Boolean, default=False) # Define se este registro é o checklist do dia 
    qtd_fazendas_enderecos = db.Column(db.Integer) #Quantos endereços fez no dia (final)
    foto_painel_path = db.Column(db.String(255), nullable=True) # Foto comprovando Nível de Combustível/KM [cite: 62]
    foto_painel_final_path = db.Column(db.String(255), nullable=True)
    
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
    equipe = db.relationship("Equipe", back_populates="logs_veiculo", lazy="joined")

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
    foto_painel_path = db.Column(db.String(255), nullable=True)
    
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
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id"), nullable=True, index=True)
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
    equipe = db.relationship("Equipe", back_populates="checklists_veiculo", lazy="joined")


# -------------------------------------------------------------
# CHECKLIST SEMANAL DE EQUIPAMENTO (DRONE)
# -------------------------------------------------------------
class ChecklistSemanalDrone(db.Model):
    __tablename__ = "checklists_semanais_drone"

    id = db.Column(db.Integer, primary_key=True)
    
    # Identificação
    drone_id = db.Column(db.Integer, db.ForeignKey("drones.id"), nullable=False, index=True)
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=True, index=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id"), nullable=True, index=True)
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
    equipe = db.relationship("Equipe", back_populates="checklists_drone", lazy="joined")


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
