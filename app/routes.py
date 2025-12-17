from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Usuario, Solicitacao, Notificacao
from flask import jsonify
from datetime import datetime, date
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date
from flask import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO
from flask import send_file
from datetime import datetime, date 
import tempfile
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app, send_from_directory
from sqlalchemy.orm import joinedload

print("--- ROTAS CARREGADAS COM SUCESSO ---")

bp = Blueprint('main', __name__)
@bp.context_processor
def inject_current_user():
    class CurrentUser:
        def __init__(self):
            # autenticação
            self.id = session.get("user_id")
            self.is_authenticated = bool(self.id)

            # nomes esperados no base.html
            self.nome_uvis = session.get("user_nome_uvis")
            self.name = session.get("user_name")

            # tipo de usuário
            self.tipo_usuario = session.get("user_tipo")

    return dict(current_user=CurrentUser())

@bp.app_template_filter('datetimeformat')
def datetimeformat(value, format='%d-%m-%y'):
    try:
        # tenta converter string do tipo "2025-12-09"
        return datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except:
        return value  # se falhar, retorna como está

def get_upload_folder():
    # pasta dentro do projeto: /seu_projeto/upload-files
    folder = os.path.join(current_app.root_path, '..', 'upload-files')
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    return folder

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.context_processor
def inject_user():
    class MockUser:
        is_authenticated = 'user_id' in session
        name = session.get('user_nome')
        id = session.get('user_id')
        tipo_usuario = session.get('user_tipo')
    return dict(current_user=MockUser())

# --- Context Processor: Simula o 'current_user' para o HTML ---
@bp.context_processor
def inject_user():
    class MockUser:
        is_authenticated = 'user_id' in session
        name = session.get('user_nome')
        id = session.get('user_id')
        tipo_usuario = session.get('user_tipo')
    return dict(current_user=MockUser())

# --- DASHBOARD UVIS ---

@bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # AJUSTE CHAVE: Se for admin, operario OU visualizar, redireciona para o painel de gestão
    if session.get('user_tipo') in ['admin', 'operario', 'visualizar']:
        return redirect(url_for('main.admin_dashboard'))

    try:
        user_id = int(session.get('user_id'))
    except (ValueError, TypeError):
        session.clear()
        flash('Sessão Inválida. Por favor, faça login novamente.', 'warning')
        return redirect(url_for('main.login'))

    # 1. Query Base: Pega os pedidos SÓ deste usuário
    query = Solicitacao.query.filter_by(usuario_id=user_id)

    # 2. Lógica do Filtro: Verifica se veio algo na URL (ex: ?status=PENDENTE)
    filtro_status = request.args.get('status')

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    # 3. Lógica da Paginação:
    page = request.args.get("page", 1, type=int)

    paginacao = query.order_by(
        Solicitacao.data_criacao.desc()
    ).paginate(page=page, per_page=6, error_out=False)

    return render_template(
        'dashboard.html',
        nome=session.get('user_nome'),
        solicitacoes=paginacao.items,
        paginacao=paginacao
    )

# --- PAINEL DE GESTÃO (Visualização para todos) ---
@bp.route('/admin')
def admin_dashboard():
    # AJUSTE CHAVE: Permite 'admin', 'operario' E 'visualizar'
    if 'user_id' not in session or session.get('user_tipo') not in ['admin', 'operario', 'visualizar']:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.login'))
    
    # Flag para controlar a renderização dos botões de edição no template
    is_editable = session.get('user_tipo') in ['admin', 'operario']
    
    # --- Captura filtros enviados pelo GET ---
    filtro_status = request.args.get("status")
    filtro_unidade = request.args.get("unidade")
    filtro_regiao = request.args.get("regiao")

    # --- Query base: Necessário dar JOIN com Usuario para filtrar por nome/região ---
    query = Solicitacao.query.join(Usuario)
    
    # 🔑 APLICAÇÃO DOS FILTROS 🔑
    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))
    # 🔑 FIM APLICAÇÃO DOS FILTROS 🔑

    page = request.args.get("page", 1, type=int)

    paginacao = query.order_by(
        Solicitacao.data_criacao.desc()
    ).paginate(page=page, per_page=6)

    # Injeta a data/hora atual (para evitar o erro 'now is undefined' se fosse usado)
    data_atual = datetime.now() 
    
    return render_template(
        'admin.html',
        pedidos=paginacao.items,
        paginacao=paginacao,
        is_editable=is_editable,
        now=data_atual
    )

@bp.route('/admin/exportar_excel')
def exportar_excel():
    # Permite APENAS admin e operario
    if 'user_id' not in session or session.get('user_tipo') not in ['admin', 'operario']:
        flash('Permissão negada para exportar.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    # --- Captura filtros ---
    filtro_status = request.args.get("status")
    filtro_unidade = request.args.get("unidade")
    filtro_regiao = request.args.get("regiao")

    # Query base
    query = Solicitacao.query.join(Usuario)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    pedidos = query.order_by(Solicitacao.data_criacao.desc()).all()

    # --- CRIA EXCEL ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório de Solicitações"

    # Cabeçalho atualizado com ENDEREÇO ÚNICO
    headers = [
        "ID", "Unidade", "Região",
        "Data Agendada", "Hora",
        "Endereço Completo",       # <-- CAMPO ÚNICO
        "Latitude", "Longitude",
        "Foco", "Tipo Visita", "Altura",
        "Apoio CET?",
        "Observação",
        "Status", "Protocolo", "Justificativa"
    ]

    # Estilos
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Cabeçalho
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Conteúdo
    row_num = 2
    for p in pedidos:

        # --- ENDEREÇO COMPLETO ---
        endereco_completo = (
            f"{p.logradouro or ''}, {getattr(p, 'numero', '')} - "
            f"{p.bairro or ''} - "
            f"{(p.cidade or '')}/{(p.uf or '')} - "
            f"{p.cep or ''}"
        )

        if getattr(p, 'complemento', None):
            endereco_completo += f" - {p.complemento}"

        # Booleans
        cet_txt = "SIM" if getattr(p, 'apoio_cet', None) else "NÃO"

        # Data formatada
        if p.data_agendamento:
            try:
                if isinstance(p.data_agendamento, (date, datetime)):
                    data_formatada = p.data_agendamento.strftime("%d-%m-%y")
                else:
                    data_formatada = datetime.strptime(str(p.data_agendamento), "%Y-%m-%d").strftime("%d-%m-%y")
            except ValueError:
                data_formatada = str(p.data_agendamento)
        else:
            data_formatada = ""

        # Linha completa
        row = [
            p.id,
            p.autor.nome_uvis,
            p.autor.regiao,
            data_formatada,
            p.hora_agendamento,

            endereco_completo,     # <-- CAMPO ÚNICO AQUI

            getattr(p, 'latitude', ''),
            getattr(p, 'longitude', ''),

            p.foco,
            getattr(p, 'tipo_visita', ''),
            getattr(p, 'altura_voo', ''),
            cet_txt,
            getattr(p, 'observacao', ''),
            p.status,
            p.protocolo,
            p.justificativa
        ]

        # Escreve na planilha
        for col_num, value in enumerate(row, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        row_num += 1

    # Congela o cabeçalho
    ws.freeze_panes = "A2"

    # Ajuste automático de largura
    for col in ws.columns:
        max_length = 0
        column_letter = col[0].column_letter

        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        ws.column_dimensions[column_letter].width = max_length + 2

    # Salvar em memória
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Enviar arquivo
    return send_file(
        output,
        download_name="relatorio_solicitacoes.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@bp.route('/admin/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    if session.get('user_tipo') not in ['admin', 'operario']:
        flash('Permissão negada para esta ação.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    pedido = Solicitacao.query.get_or_404(id)

    # Campos atuais (como já está)
    pedido.protocolo = request.form.get('protocolo')
    pedido.status = request.form.get('status')
    pedido.justificativa = request.form.get('justificativa')
    pedido.latitude = request.form.get('latitude')
    pedido.longitude = request.form.get('longitude')

    # ✅ NOVO: arquivo
    file = request.files.get("anexo")
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("Tipo de arquivo não permitido.", "warning")
            return redirect(url_for('main.admin_dashboard'))

        original = secure_filename(file.filename)
        ext = original.rsplit(".", 1)[1].lower()
        unique_name = f"sol_{pedido.id}_{uuid.uuid4().hex}.{ext}"

        upload_folder = get_upload_folder()
        save_path = os.path.join(upload_folder, unique_name)
        file.save(save_path)

        # grava no banco (caminho relativo)
        pedido.anexo_path = f"upload-files/{unique_name}"
        pedido.anexo_nome = original

    db.session.commit()
    flash('Pedido atualizado com sucesso!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@bp.route("/admin/solicitacao/<int:id>/anexo", endpoint="baixar_anexo_admin")
def baixar_anexo_admin(id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_tipo = session.get("user_tipo")
    user_id = int(session.get("user_id"))

    pedido = Solicitacao.query.get_or_404(id)

    # ✅ Admin/Operário/Visualizar: pode baixar qualquer
    if user_tipo in ["admin", "operario", "visualizar"]:
        pass
    # ✅ UVIS: só pode baixar se for o dono
    elif user_tipo == "uvis":
        if pedido.usuario_id != user_id:
            flash("Permissão negada.", "danger")
            return redirect(url_for("main.dashboard"))
    else:
        flash("Permissão negada.", "danger")
        return redirect(url_for("main.login"))

    if not pedido.anexo_path:
        flash("Essa solicitação não tem anexo.", "warning")
        return redirect(url_for("main.admin_dashboard"))

    upload_folder = get_upload_folder()
    filename = pedido.anexo_path.replace("upload-files/", "", 1)
    return send_from_directory(upload_folder, filename, as_attachment=True)



# --- NOVO PEDIDO ---
@bp.route('/novo_cadastro', methods=['GET', 'POST'], endpoint='novo')
def novo():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    hoje = date.today().isoformat()

    if request.method == 'POST':
        try:
            user_id_int = int(session['user_id'])

            data_str = request.form.get('data')
            hora_str = request.form.get('hora')

            if data_str:
                data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            else:
                data_obj = None

            if hora_str:
                hora_obj = datetime.strptime(hora_str, '%H:%M').time()
            else:
                hora_obj = None

            apoio_cet_bool = request.form.get('apoio_cet') == 'sim'


            nova_solicitacao = Solicitacao(
                data_agendamento=data_obj,
                hora_agendamento=hora_obj,

                cep=request.form.get('cep'),
                logradouro=request.form.get('logradouro'),
                bairro=request.form.get('bairro'),
                cidade=request.form.get('cidade'),
                numero=request.form.get('numero'),
                uf=request.form.get('uf'),
                complemento=request.form.get('complemento'), 

                foco=request.form.get('foco'),

                tipo_visita=request.form.get('tipo_visita'),
                altura_voo=request.form.get('altura_voo'),
                apoio_cet=apoio_cet_bool,
                observacao=request.form.get('observacao'),

                latitude=request.form.get('latitude'),
                longitude=request.form.get('longitude'),

                usuario_id=user_id_int,
                status='PENDENTE'
            )

            db.session.add(nova_solicitacao)
            db.session.commit()

            flash('Pedido enviado!', 'success')
            return redirect(url_for('main.dashboard'))

        except ValueError as ve:
            db.session.rollback()
            flash(f"Erro no formato de data/hora: {ve}", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {e}", "danger")

    return render_template('cadastro.html', hoje=hoje)

# --- LOGIN ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        # AJUSTE CHAVE: Redireciona para admin_dashboard se for admin, operario OU visualizar
        if session.get('user_tipo') in ['admin', 'operario', 'visualizar']:
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        user = Usuario.query.filter_by(login=request.form.get('login')).first()

        if user and user.check_senha(request.form.get('senha')):
            session['user_id'] = int(user.id)
            session['user_nome'] = user.nome_uvis
            session['user_tipo'] = user.tipo_usuario

            flash(f'Bem-vindo, {user.nome_uvis}! Login realizado com sucesso.', 'success')

            # AJUSTE CHAVE: Redireciona para admin_dashboard se for admin, operario OU visualizar
            if user.tipo_usuario in ['admin', 'operario', 'visualizar']:
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login ou senha incorretos. Tente novamente.', 'danger')

    return render_template('login.html')

# --- LOGOUT ---
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@bp.route("/forcar_erro")
def forcar_erro():
    1 / 0  # erro proposital
    return "nunca vai chegar aqui"

# ReportLab (PDF)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

# Openpyxl (Excel)
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# O objeto 'bp' precisa ser definido (Exemplo: bp = Blueprint('main', __name__))
# E 'Usuario' e 'Solicitacao' precisam ser seus modelos SQLAlchemy

# =======================================================================
# Função Auxiliar de Filtros (Reutilizada em todas as rotas)
# =======================================================================

def aplicar_filtros_base(query, filtro_data, uvis_id):
    """Aplica o filtro de mês/ano e opcionalmente o filtro de UVIS (usuario_id)."""
    
    # Filtro de Mês/Ano (obrigatório)
    query = query.filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    
    # Filtro de UVIS (opcional)
    if uvis_id:
        query = query.filter(Solicitacao.usuario_id == uvis_id)
        
    return query


# =======================================================================
# ROTA 1: Visualização do Relatório (HTML)
# =======================================================================
@bp.route('/relatorios', methods=['GET'])
def relatorios():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # 1. Parâmetros de Filtro
    mes_atual = request.args.get('mes', datetime.now().month, type=int)
    ano_atual = request.args.get('ano', datetime.now().year, type=int)
    uvis_id = request.args.get('uvis_id', type=int)
    filtro_data = f"{ano_atual}-{mes_atual:02d}"

    # 2. UVIS disponíveis para o dropdown
    uvis_disponiveis = db.session.query(Usuario.id, Usuario.nome_uvis) \
        .filter(Usuario.tipo_usuario == 'uvis') \
        .order_by(Usuario.nome_uvis) \
        .all()

    # 3. Histórico Mensal (usado para gerar anos disponíveis - não filtra por uvis_id)
    dados_mensais_raw = (
        db.session.query(
            db.func.strftime('%Y-%m', Solicitacao.data_criacao).label('mes'),
            db.func.count(Solicitacao.id)
        )
        .group_by('mes')
        .order_by('mes')
        .all()
    )
    dados_mensais = [tuple(row) for row in dados_mensais_raw]

    anos_disponiveis = sorted(list(set([d[0].split('-')[0] for d in dados_mensais])), reverse=True)
    if not anos_disponiveis:
        anos_disponiveis = [ano_atual]

    # 4. Totalizações (usando a função de filtro)
    base_query = db.session.query(Solicitacao)

    total_solicitacoes = aplicar_filtros_base(base_query, filtro_data, uvis_id).count()
    
    total_aprovadas = aplicar_filtros_base(base_query, filtro_data, uvis_id) \
        .filter(Solicitacao.status == "APROVADO").count()

    total_aprovadas_com_recomendacoes = aplicar_filtros_base(base_query, filtro_data, uvis_id) \
        .filter(Solicitacao.status == "APROVADO COM RECOMENDAÇÕES").count()

    total_recusadas = aplicar_filtros_base(base_query, filtro_data, uvis_id) \
        .filter(Solicitacao.status == "NEGADO").count()

    total_analise = aplicar_filtros_base(base_query, filtro_data, uvis_id) \
        .filter(Solicitacao.status == "EM ANÁLISE").count()

    total_pendentes = aplicar_filtros_base(base_query, filtro_data, uvis_id) \
        .filter(Solicitacao.status == "PENDENTE").count()

    # 5. Consultas Agrupadas (usando a função de filtro)

    # Região (requer JOIN)
    query_regiao = db.session.query(Usuario.regiao, db.func.count(Solicitacao.id)) \
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    dados_regiao_raw = aplicar_filtros_base(query_regiao, filtro_data, uvis_id) \
        .group_by(Usuario.regiao) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_regiao = [tuple(row) for row in dados_regiao_raw]

    # Status
    query_status = db.session.query(Solicitacao.status, db.func.count(Solicitacao.id))
    dados_status_raw = aplicar_filtros_base(query_status, filtro_data, uvis_id) \
        .group_by(Solicitacao.status) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_status = [tuple(row) for row in dados_status_raw]

    # Foco
    query_foco = db.session.query(Solicitacao.foco, db.func.count(Solicitacao.id))
    dados_foco_raw = aplicar_filtros_base(query_foco, filtro_data, uvis_id) \
        .group_by(Solicitacao.foco) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_foco = [tuple(row) for row in dados_foco_raw]
    
    # Tipo Visita
    query_tipo_visita = db.session.query(Solicitacao.tipo_visita, db.func.count(Solicitacao.id))
    dados_tipo_visita_raw = aplicar_filtros_base(query_tipo_visita, filtro_data, uvis_id) \
        .group_by(Solicitacao.tipo_visita) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_tipo_visita = [tuple(row) for row in dados_tipo_visita_raw]
    
    # Altura de Voo
    query_altura_voo = db.session.query(Solicitacao.altura_voo, db.func.count(Solicitacao.id))
    dados_altura_voo_raw = aplicar_filtros_base(query_altura_voo, filtro_data, uvis_id) \
        .group_by(Solicitacao.altura_voo) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_altura_voo = [tuple(row) for row in dados_altura_voo_raw]

    # Unidade (UVIS) - Requer JOIN e filtro adicional de tipo_usuario
    query_unidade = db.session.query(Usuario.nome_uvis, db.func.count(Solicitacao.id)) \
        .join(Usuario, Usuario.id == Solicitacao.usuario_id) \
        .filter(Usuario.tipo_usuario == 'uvis')
    dados_unidade_raw = aplicar_filtros_base(query_unidade, filtro_data, uvis_id) \
        .group_by(Usuario.nome_uvis) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_unidade = [tuple(row) for row in dados_unidade_raw]

    # 6. Retorno
    return render_template(
        'relatorios.html',
        total_solicitacoes=total_solicitacoes,
        total_aprovadas=total_aprovadas,
        total_aprovadas_com_recomendacoes=total_aprovadas_com_recomendacoes,
        total_recusadas=total_recusadas,
        total_analise=total_analise,
        total_pendentes=total_pendentes,
        dados_regiao=dados_regiao,
        dados_status=dados_status,
        dados_foco=dados_foco,
        dados_tipo_visita=dados_tipo_visita,
        dados_altura_voo=dados_altura_voo,
        dados_unidade=dados_unidade,
        dados_mensais=dados_mensais,
        mes_selecionado=mes_atual,
        ano_selecionado=ano_atual,
        anos_disponiveis=anos_disponiveis,
        uvis_id_selecionado=uvis_id, # Passa o ID selecionado
        uvis_disponiveis=uvis_disponiveis # Passa a lista completa para o dropdown
    )


# =======================================================================
# ROTA 2: Exportar PDF (Com Filtro UVIS)
# =======================================================================
import os
import tempfile
from io import BytesIO
from datetime import datetime
from math import ceil

from flask import send_file, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage, Flowable, KeepTogether
)

# matplotlib é opcional — tentamos importar e marcamos se disponível
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

@bp.route('/admin/exportar_relatorio_pdf')
def exportar_relatorio_pdf():
    # -------------------------
    # 1. Parâmetros e filtros
    # -------------------------
    mes = int(request.args.get('mes', datetime.now().month))
    ano = int(request.args.get('ano', datetime.now().year))
    uvis_id = request.args.get('uvis_id', type=int)
    orient = request.args.get('orient', default='portrait')  # 'portrait' ou 'landscape'
    filtro_data = f"{ano}-{mes:02d}"

    # 2. Busca Principal para Totais e Detalhes
    query_base = db.session.query(Solicitacao, Usuario).join(Usuario, Usuario.id == Solicitacao.usuario_id)
    query_base = aplicar_filtros_base(query_base, filtro_data, uvis_id)
    query_results = query_base.order_by(Solicitacao.data_criacao.desc()).all()

    # 3. Totais
    total_solicitacoes = len(query_results)
    total_aprovadas = sum(1 for s, u in query_results if s.status == "APROVADO")
    total_aprovadas_com_recomendacoes = sum(1 for s, u in query_results if s.status == "APROVADO COM RECOMENDAÇÕES")
    total_recusadas = sum(1 for s, u in query_results if s.status == "NEGADO")
    total_analise = sum(1 for s, u in query_results if s.status == "EM ANÁLISE")
    total_pendentes = sum(1 for s, u in query_results if s.status == "PENDENTE")

    # 4. Buscas agrupadas
    def aplicar_filtros_agrupados(query):
        query = query.filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        if uvis_id:
            query = query.filter(Solicitacao.usuario_id == uvis_id)
        return query

    dados_regiao_raw = aplicar_filtros_agrupados(
        db.session.query(Usuario.regiao, db.func.count(Solicitacao.id)).join(Usuario, Usuario.id == Solicitacao.usuario_id)
    ).group_by(Usuario.regiao).all()
    dados_regiao = [(r or "Não informado", c) for r, c in dados_regiao_raw]

    dados_status_raw = aplicar_filtros_agrupados(
        db.session.query(Solicitacao.status, db.func.count(Solicitacao.id))
    ).group_by(Solicitacao.status).all()
    dados_status = [(s or "Não informado", c) for s, c in dados_status_raw]

    dados_foco_raw = aplicar_filtros_agrupados(
        db.session.query(Solicitacao.foco, db.func.count(Solicitacao.id))
    ).group_by(Solicitacao.foco).all()
    dados_foco = [(f or "Não informado", c) for f, c in dados_foco_raw]

    dados_tipo_visita_raw = aplicar_filtros_agrupados(
        db.session.query(Solicitacao.tipo_visita, db.func.count(Solicitacao.id))
    ).group_by(Solicitacao.tipo_visita).all()
    dados_tipo_visita = [(t or "Não informado", c) for t, c in dados_tipo_visita_raw]

    dados_altura_raw = aplicar_filtros_agrupados(
        db.session.query(Solicitacao.altura_voo, db.func.count(Solicitacao.id))
    ).group_by(Solicitacao.altura_voo).all()
    dados_altura_voo = [(a or "Não informado", c) for a, c in dados_altura_raw]

    dados_unidade_query = db.session.query(Usuario.nome_uvis, db.func.count(Solicitacao.id)) \
        .join(Usuario, Usuario.id == Solicitacao.usuario_id) \
        .filter(Usuario.tipo_usuario == 'uvis')
    dados_unidade_raw = aplicar_filtros_agrupados(dados_unidade_query) \
        .group_by(Usuario.nome_uvis) \
        .order_by(db.func.count(Solicitacao.id).desc()) \
        .all()
    dados_unidade = [(u or "Não informado", c) for u, c in dados_unidade_raw]

    dados_mensais_raw = (
        db.session.query(
            db.func.strftime('%Y-%m', Solicitacao.data_criacao).label('mes'),
            db.func.count(Solicitacao.id)
        )
        .group_by('mes')
        .order_by('mes')
        .all()
    )
    dados_mensais = [(m, c) for m, c in dados_mensais_raw]

    # -------------------------
    # 5. Preparar documento PDF
    # -------------------------
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    caminho_pdf = tmp_pdf.name
    tmp_pdf.close()

    # Auto-landscape se muitos campos (evita esmagar a tabela detalhada)
    if orient not in ('portrait', 'landscape'):
        orient = 'portrait'
    pagesize = A4
    if orient == 'landscape' or True:  # deixei sempre landscape pq a tabela detalhada tem muitas colunas
        pagesize = landscape(A4)

    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=pagesize,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=14*mm, bottomMargin=18*mm
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'title', parent=styles['Title'],
        fontSize=20, leading=24, alignment=1,
        spaceAfter=6, textColor=colors.HexColor('#0d6efd')
    )
    subtitle_style = ParagraphStyle(
        'subtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#666'),
        alignment=1, spaceAfter=6
    )
    section_h = ParagraphStyle(
        'sec', parent=styles['Heading2'],
        fontSize=12, spaceAfter=6,
        textColor=colors.HexColor('#0d6efd')
    )
    normal = styles['Normal']
    small = ParagraphStyle('small', parent=styles['BodyText'], fontSize=9, textColor=colors.HexColor('#555'))

    # Estilo de célula p/ tabela grande (principal correção do “sobrepondo”)
    cell_style = ParagraphStyle(
        'cell',
        parent=styles['BodyText'],
        fontSize=7.4,
        leading=9,                 # evita sobreposição vertical
        textColor=colors.HexColor('#222'),
        wordWrap='CJK',            # quebra bem até em textos “sem espaço”
        splitLongWords=True,
        spaceAfter=0,
        spaceBefore=0,
    )

    story = []

    # -------------------------
    # Funções utilitárias
    # -------------------------
    def P(txt):
        txt = '' if txt is None else str(txt)
        txt = txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return Paragraph(txt, cell_style)

    def cut(s, n=220):
        s = '' if s is None else str(s)
        return (s[:n] + '…') if len(s) > n else s

    def safe_img_from_plt(fig, width_mm=155):
        bio = BytesIO()
        fig.tight_layout()
        fig.savefig(bio, format='png', dpi=180, bbox_inches='tight')
        plt.close(fig)
        bio.seek(0)
        return RLImage(bio, width=width_mm*mm)

    def render_small_table(rows, colWidths):
        tbl = Table(rows, colWidths=colWidths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fbfdff')]),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        return tbl

    # -------------------------
    # Cabeçalho / Capa
    # -------------------------
    logo_path = os.path.join(os.getcwd(), 'static', 'logo.png')
    logo = None
    if os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, width=32*mm, height=32*mm)
        except Exception:
            logo = None

    story.append(Spacer(1, 6))
    if logo:
        h = [[logo, Paragraph(f"<b>Relatório Mensal — {mes:02d}/{ano}</b>", title_style)]]
        cap_tbl = Table(h, colWidths=[36*mm, (doc.width - 36*mm)])
        cap_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        story.append(cap_tbl)
    else:
        story.append(Paragraph(f"Relatório Mensal — {mes:02d}/{ano}", title_style))

    titulo_uvis = ""
    if uvis_id:
        uvis_obj = db.session.query(Usuario.nome_uvis).filter(Usuario.id == uvis_id).first()
        if uvis_obj:
            titulo_uvis = f" — {uvis_obj.nome_uvis}"

    story.append(Paragraph(f"Sistema de Gestão de Solicitações{titulo_uvis}", subtitle_style))
    story.append(Spacer(1, 8))

    resumo_box = [
        ['Métrica', 'Quantidade'],
        ['Total de Solicitações', str(total_solicitacoes)],
        ['Aprovadas', str(total_aprovadas)],
        ['Aprovadas com Recomendações', str(total_aprovadas_com_recomendacoes)],
        ['Recusadas', str(total_recusadas)],
        ['Em Análise', str(total_analise)],
        ['Pendentes', str(total_pendentes)]
    ]
    story.append(render_small_table(resumo_box, [90*mm, 45*mm]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", small))
    story.append(Spacer(1, 14))

    # Sumário
    story.append(Paragraph("Sumário", section_h))
    sumario_itens = [
        "Resumo Geral",
        "Solicitações por Região",
        "Status Detalhado",
        "Solicitações por Foco / Tipo / Altura",
        "Solicitações por Unidade (UVIS)",
        "Histórico Mensal",
        "Gráficos (Visão Geral)",
        "Registros Detalhados"
    ]
    for i, it in enumerate(sumario_itens, 1):
        story.append(Paragraph(f"{i}. {it}", normal))
    story.append(PageBreak())

    # Seções
    story.append(Paragraph("Resumo Geral", section_h))
    story.append(render_small_table(resumo_box, [110*mm, 60*mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Solicitações por Região", section_h))
    rows = [['Região', 'Total']] + [[r, str(c)] for r, c in dados_regiao]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Status Detalhado", section_h))
    rows = [['Status', 'Total']] + [[s, str(c)] for s, c in dados_status]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Solicitações por Foco", section_h))
    rows = [['Foco', 'Total']] + [[f, str(c)] for f, c in dados_foco]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Solicitações por Tipo de Visita", section_h))
    rows = [['Tipo', 'Total']] + [[t, str(c)] for t, c in dados_tipo_visita]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Solicitações por Altura de Voo", section_h))
    rows = [['Altura (m)', 'Total']] + [[str(a), str(c)] for a, c in dados_altura_voo]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Solicitações por Unidade (UVIS) — Top", section_h))
    rows = [['Unidade', 'Total']] + [[u, str(c)] for u, c in dados_unidade]
    story.append(render_small_table(rows, [110*mm, 60*mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Histórico Mensal (Total por Mês)", section_h))
    rows = [['Mês', 'Total']] + [[m, str(c)] for m, c in dados_mensais]
    story.append(render_small_table(rows, [70*mm, 45*mm]))
    story.append(Spacer(1, 10))

    # -------------------------
    # Gráficos (compactos e mais bonitos)
    # -------------------------
    story.append(PageBreak())
    story.append(Paragraph("Gráficos (Visão Geral)", section_h))

    if MATPLOTLIB_AVAILABLE:
        try:
            # Donut: status
            labels = [s for s, _ in dados_status]
            values = [c for _, c in dados_status]
            total = sum(values) or 1

            def autopct(p):
                return f'{p:.0f}%' if p >= 6 else ''

            fig1, ax1 = plt.subplots(figsize=(5.2, 2.2))
            wedges, *_ = ax1.pie(
                values or [1],
                labels=None,
                autopct=autopct,
                startangle=90,
                pctdistance=0.75,
                textprops={'fontsize': 8}
            )
            centre_circle = plt.Circle((0,0), 0.55, fc='white')
            ax1.add_artist(centre_circle)
            ax1.legend(wedges, labels, loc='center left', bbox_to_anchor=(1.02, 0.5),
                       fontsize=8, frameon=False)
            ax1.set_title('Distribuição por Status', fontsize=9)
            ax1.axis('equal')
            story.append(safe_img_from_plt(fig1, width_mm=145))
            story.append(Spacer(1, 6))

            # Barh: Top UVIS
            u_names = [u for u, _ in dados_unidade[:8]]
            u_vals = [c for _, c in dados_unidade[:8]]

            fig2, ax2 = plt.subplots(figsize=(6.2, 2.2))
            ax2.barh(u_names[::-1] or ['Nenhum'], u_vals[::-1] or [0])
            ax2.set_xlabel('Total', fontsize=8)
            ax2.set_title('Top UVIS', fontsize=9)
            ax2.tick_params(axis='y', labelsize=8)
            ax2.tick_params(axis='x', labelsize=8)
            ax2.grid(axis='x', linestyle=':', linewidth=0.5)
            story.append(safe_img_from_plt(fig2, width_mm=155))
            story.append(Spacer(1, 6))

            # Linha: histórico mensal
            months = [m for m, _ in dados_mensais]
            counts = [c for _, c in dados_mensais]

            fig3, ax3 = plt.subplots(figsize=(6.4, 2.2))
            if months:
                ax3.plot(range(len(months)), counts, marker='o', linewidth=1)
                ax3.set_xticks(range(len(months)))
                ax3.set_xticklabels(months, rotation=45, ha='right', fontsize=8)
            ax3.set_title('Histórico Mensal', fontsize=9)
            ax3.tick_params(axis='y', labelsize=8)
            ax3.grid(axis='y', linestyle=':', linewidth=0.5)
            story.append(safe_img_from_plt(fig3, width_mm=160))
            story.append(Spacer(1, 6))

        except Exception:
            story.append(Paragraph("Gráficos indisponíveis (erro ao gerar).", normal))
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("Matplotlib não disponível — gráficos foram omitidos.", normal))
        story.append(Spacer(1, 8))

    # -------------------------
    # Registros detalhados (sem sobreposição)
    # -------------------------
    story.append(PageBreak())
    story.append(Paragraph("Registros Detalhados", section_h))
    story.append(Spacer(1, 6))

    registros_header = ['Data', 'Hora', 'Unidade', 'Protocolo', 'Status', 'Região', 'Foco', 'Tipo Visita', 'Observação']
    registros_rows = [[P(h) for h in registros_header]]

    for s, u in query_results:
        # data/hora safe formatting
        try:
            if getattr(s, 'data_agendamento', None):
                data_str = s.data_agendamento.strftime("%d/%m/%Y") if hasattr(s.data_agendamento, 'strftime') else str(s.data_agendamento)
            else:
                data_str = s.data_criacao.strftime("%d/%m/%Y") if hasattr(s.data_criacao, 'strftime') else str(s.data_criacao)
        except Exception:
            data_str = str(getattr(s, 'data_agendamento', '') or getattr(s, 'data_criacao', ''))

        hora = getattr(s, 'hora_agendamento', '')
        hora_str = hora.strftime("%H:%M") if hasattr(hora, 'strftime') else str(hora or '')

        unidade = getattr(u, 'nome_uvis', '') or "Não informado"
        protocolo = getattr(s, 'protocolo', '') or ''
        status = getattr(s, 'status', '') or ''
        regiao = getattr(u, 'regiao', '') or ''
        foco = getattr(s, 'foco', '') or ''
        tipo_visita = getattr(s, 'tipo_visita', '') or ''
        obs = cut(getattr(s, 'observacao', '') or '', 260)

        registros_rows.append([
            P(data_str),
            P(hora_str),
            P(unidade),
            P(protocolo),
            P(status),
            P(regiao),
            P(foco),
            P(tipo_visita),
            P(obs),
        ])

    # Chunk para não estourar memória/paginação
    chunk_size = 32
    for i in range(0, len(registros_rows), chunk_size):
        chunk = registros_rows[i:i+chunk_size]

        # colWidths ajustadas p/ landscape A4 (melhor distribuição)
        colWidths = [18*mm, 14*mm, 34*mm, 25*mm, 22*mm, 26*mm, 26*mm, 28*mm, 85*mm]

        tbl = Table(chunk, repeatRows=1, colWidths=colWidths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),

            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fbfdff')]),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),

            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),

            ('WORDWRAP', (0,0), (-1,-1), 'CJK'),
        ]))

        story.append(tbl)
        story.append(Spacer(1, 6))
        if i + chunk_size < len(registros_rows):
            story.append(PageBreak())

    # -------------------------
    # Header/Footer
    # -------------------------
    def _header_footer(canvas, doc_):
        canvas.saveState()
        w, h = pagesize

        # header line
        canvas.setFillColor(colors.HexColor('#0d6efd'))
        canvas.rect(doc_.leftMargin, h - (12*mm), doc_.width, 4, fill=1, stroke=0)

        footer_text = "Sistema de Gestão de Solicitações — IJASystem"
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor('#777'))
        canvas.drawString(doc_.leftMargin, 10*mm, footer_text)

        page_num_text = f"Página {canvas.getPageNumber()}"
        canvas.drawRightString(doc_.leftMargin + doc_.width, 10*mm, page_num_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

    nome_arquivo = f"relatorio_IJASystem_{ano}_{mes:02d}"
    if uvis_id:
        nome_arquivo += f"_UVIS_{uvis_id}"

    return send_file(
        caminho_pdf,
        as_attachment=True,
        download_name=f"{nome_arquivo}.pdf",
        mimetype="application/pdf"
    )


# =======================================================================
# ROTA 3: Exportar Excel (Com Filtro UVIS)
# =======================================================================
@bp.route('/admin/exportar_relatorio_excel')
def exportar_relatorio_excel():
    # 1. Parâmetros de Filtro
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    mes = request.args.get('mes', datetime.now().month, type=int)
    ano = request.args.get('ano', datetime.now().year, type=int)
    uvis_id = request.args.get('uvis_id', type=int) # NOVO FILTRO
    filtro_data = f"{ano}-{mes:02d}"

    # 2. Busca de Dados
    query_dados = db.session.query(
        Solicitacao.id,
        Solicitacao.status,
        Solicitacao.foco,
        Solicitacao.tipo_visita,
        Solicitacao.altura_voo,
        Solicitacao.data_agendamento,
        Solicitacao.hora_agendamento,
        Solicitacao.cep,
        Solicitacao.logradouro,
        Solicitacao.numero,
        Solicitacao.bairro,
        Solicitacao.cidade,
        Solicitacao.uf,
        Solicitacao.latitude,
        Solicitacao.longitude,
        Usuario.nome_uvis,
        Usuario.regiao
    ) \
        .join(Usuario, Usuario.id == Solicitacao.usuario_id) \
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)

    # APLICAÇÃO DO NOVO FILTRO
    if uvis_id:
        query_dados = query_dados.filter(Solicitacao.usuario_id == uvis_id)

    dados = query_dados.all()

    # 3. Criar arquivo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"

    # Cabeçalho
    colunas = [
        "ID", "Status", "Foco", "Tipo Visita", "Altura Voo",
        "Data Agendamento", "Hora Agendamento",
        "CEP", "Logradouro", "Número", "Bairro", "Cidade", "UF",
        "Latitude", "Longitude", "UVIS", "Região"
    ]

    # ... (Estilos e escrita do cabeçalho) ...
    header_fill = PatternFill(start_color="1E90FF", end_color="1E90FF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style='thin', color="000000")
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    zebra1 = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")
    zebra2 = PatternFill(start_color="FFF7FBFF", end_color="FFF7FBFF", fill_type="solid")

    for col_num, col_name in enumerate(colunas, 1):
        cell = ws.cell(row=1, column=col_num, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border

    # 4. Preenchimento das linhas
    for row_num, row in enumerate(dados, 2):

        # ---- FORMATAR DATAS ----
        data_agendamento_fmt = ""
        if row.data_agendamento:
            try:
                data_agendamento_fmt = row.data_agendamento.strftime("%d/%m/%Y")
            except:
                data_agendamento_fmt = str(row.data_agendamento)

        # ---- FORMATAR HORA ----
        hora_agendamento_fmt = ""
        if row.hora_agendamento:
            try:
                hora_agendamento_fmt = row.hora_agendamento.strftime("%H:%M")
            except:
                hora_agendamento_fmt = str(row.hora_agendamento)

        # ---- PREENCHER LINHAS ----
        values = [
            row.id,
            row.status,
            row.foco,
            row.tipo_visita,
            row.altura_voo,
            data_agendamento_fmt,
            hora_agendamento_fmt,
            row.cep,
            row.logradouro,
            row.numero,
            row.bairro,
            row.cidade,
            row.uf,
            row.latitude,
            row.longitude,
            row.nome_uvis,
            row.regiao
        ]

        for col_index, value in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_index, value=value)
            cell.border = thin_border
            if col_index in (1, 3, 6, 8, 15, 16):
                cell.alignment = center
            else:
                cell.alignment = Alignment(vertical="top", horizontal="left")

            fill = zebra1 if (row_num % 2 == 0) else zebra2
            cell.fill = fill

    # 5. Ajustar e Finalizar
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value is not None:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[column].width = max(10, min(max_length + 2, 60))

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}1"

    # Gerar arquivo em memória
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Nome do arquivo
    nome_arquivo = f"relatorio_IJASystem_{ano}_{mes:02d}"
    if uvis_id:
        nome_arquivo += f"_UVIS_{uvis_id}"

    return send_file(
        output,
        download_name=f"{nome_arquivo}.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
@bp.route('/admin/editar_completo/<int:id>', methods=['GET', 'POST'], endpoint='admin_editar_completo')
def admin_editar_completo(id):
    if session.get('user_tipo') != 'admin':
        flash('Permissão negada. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    pedido = Solicitacao.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # estado anterior (pra saber se mudou)
            antes_data = pedido.data_agendamento
            antes_hora = pedido.hora_agendamento

            data_str = request.form.get('data_agendamento')
            hora_str = request.form.get('hora_agendamento')

            pedido.data_agendamento = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
            pedido.hora_agendamento = datetime.strptime(hora_str, '%H:%M').time() if hora_str else None

            pedido.foco = request.form.get('foco')
            pedido.tipo_visita = request.form.get('tipo_visita')
            pedido.altura_voo = request.form.get('altura_voo')
            pedido.apoio_cet = request.form.get('apoio_cet') == 'sim'
            pedido.observacao = request.form.get('observacao')

            pedido.cep = request.form.get('cep')
            pedido.logradouro = request.form.get('logradouro')
            pedido.numero = request.form.get('numero')
            pedido.bairro = request.form.get('bairro')
            pedido.cidade = request.form.get('cidade')
            pedido.uf = request.form.get('uf')
            pedido.complemento = request.form.get('complemento')

            pedido.protocolo = request.form.get('protocolo')
            pedido.status = request.form.get('status')
            pedido.justificativa = request.form.get('justificativa')
            pedido.latitude = request.form.get('latitude')
            pedido.longitude = request.form.get('longitude')

            db.session.commit()

            # 🔔 cria notificação se agendou/mudou data/hora
            mudou_agendamento = (antes_data != pedido.data_agendamento) or (antes_hora != pedido.hora_agendamento)

            if pedido.data_agendamento and mudou_agendamento:
                data_fmt = pedido.data_agendamento.strftime("%d/%m/%Y")
                hora_fmt = pedido.hora_agendamento.strftime("%H:%M") if pedido.hora_agendamento else "00:00"

                criar_notificacao(
                    usuario_id=pedido.usuario_id,
                    titulo="Agendamento atualizado",
                    mensagem=f"Sua solicitação foi agendada para {data_fmt} às {hora_fmt}.",
                    link=url_for("main.agenda")
                )

            flash('Solicitação atualizada com sucesso!', 'success')
            return redirect(url_for('main.admin_dashboard'))

        except ValueError as ve:
            db.session.rollback()
            flash(f"Erro no formato de data/hora: {ve}", 'warning')
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {e}", 'danger')

    return render_template('admin_editar_completo.html', pedido=pedido)


from sqlalchemy.orm import joinedload
from flask import session, flash, redirect, url_for

@bp.route('/admin/deletar/<int:id>', methods=['POST'], endpoint='deletar_registro')
def deletar(id):

    if session.get('user_tipo') != 'admin':
        flash('Permissão negada. Apenas administradores podem deletar registros.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    # Carrega o autor junto (evita lazy load pós-delete)
    pedido = (
        Solicitacao.query
        .options(joinedload(Solicitacao.autor))
        .get_or_404(id)
    )

    pedido_id = pedido.id
    autor_nome = pedido.autor.nome_uvis if pedido.autor else "UVIS"

    try:
        db.session.delete(pedido)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Não mostra erro ao usuário
        pass

    flash(f"Pedido #{pedido_id} da {autor_nome} deletado permanentemente.", "success")
    return redirect(url_for('main.admin_dashboard'))
@bp.route("/agenda")
def agenda():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_tipo = session.get("user_tipo")
    user_id = session.get("user_id")

    # ----------------------------
    # Filtros (GET)
    # ----------------------------
    filtro_status = request.args.get("status") or None
    filtro_uvis_id = request.args.get("uvis_id", type=int)

    mes = request.args.get("mes", datetime.now().month, type=int)
    ano = request.args.get("ano", datetime.now().year, type=int)

    # link vindo da notificação (você já usa ?d=YYYY-MM-DD lá)
    d = request.args.get("d")  # opcional
    initial_date = d or f"{ano}-{mes:02d}-01"

    # ----------------------------
    # Query base + permissões
    # ----------------------------
    query = Solicitacao.query.options(joinedload(Solicitacao.autor))

    # UVIS só vê os próprios (e não pode filtrar outra UVIS)
    if user_tipo not in ["admin", "operario", "visualizar"]:
        query = query.filter(Solicitacao.usuario_id == user_id)
        filtro_uvis_id = None
    else:
        # Admin/Operário/Visualizar podem filtrar por UVIS
        if filtro_uvis_id:
            query = query.filter(Solicitacao.usuario_id == filtro_uvis_id)

    # Filtro por status
    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    # Filtro por mês/ano (pela data do agendamento)
    filtro_mesano = f"{ano}-{mes:02d}"
    query = query.filter(db.func.strftime("%Y-%m", Solicitacao.data_agendamento) == filtro_mesano)

    eventos = query.all()

    # ----------------------------
    # UVIS disponíveis (dropdown)
    # ----------------------------
    uvis_disponiveis = []
    if user_tipo in ["admin", "operario", "visualizar"]:
        uvis_disponiveis = (
            db.session.query(Usuario.id, Usuario.nome_uvis)
            .filter(Usuario.tipo_usuario == "uvis")
            .order_by(Usuario.nome_uvis)
            .all()
        )

    # Anos disponíveis (pra select)
    anos_raw = (
        db.session.query(db.func.strftime("%Y", Solicitacao.data_agendamento))
        .filter(Solicitacao.data_agendamento.isnot(None))
        .distinct()
        .order_by(db.func.strftime("%Y", Solicitacao.data_agendamento).desc())
        .all()
    )
    anos_disponiveis = [int(a[0]) for a in anos_raw if a and a[0]]
    if not anos_disponiveis:
        anos_disponiveis = [datetime.now().year]

    # ----------------------------
    # Monta eventos p/ FullCalendar
    # ----------------------------
    agenda_eventos = []

    for e in eventos:
        if not e.data_agendamento:
            continue

        data = e.data_agendamento.strftime("%Y-%m-%d")
        hora = e.hora_agendamento.strftime("%H:%M") if e.hora_agendamento else "00:00"

        ev = {
            "id": str(e.id),  # (opcional, mas útil)
            "title": f"{e.foco} - {e.autor.nome_uvis}",
            "start": f"{data}T{hora}",
            "color": (
                "#198754" if e.status == "APROVADO" else
                "#ffa023" if e.status == "APROVADO COM RECOMENDAÇÕES" else
                "#dc3545" if e.status == "NEGADO" else
                "#e9fa05" if e.status == "EM ANÁLISE" else
                "#0d6efd"
            ),
            "extendedProps": {
                "is_admin": (user_tipo == "admin"),
                "foco": e.foco,
                "uvis": e.autor.nome_uvis,
                "hora": hora,
                "status": e.status
            }
        }

        if user_tipo == "admin":
            ev["url"] = url_for("main.admin_editar_completo", id=e.id)

        agenda_eventos.append(ev)

    status_opcoes = [
        "PENDENTE",
        "EM ANÁLISE",
        "APROVADO",
        "APROVADO COM RECOMENDAÇÕES",
        "NEGADO",
    ]

    return render_template(
        "agenda.html",
        eventos_json=json.dumps(agenda_eventos),
        uvis_disponiveis=uvis_disponiveis,
        status_opcoes=status_opcoes,
        filtros={
            "uvis_id": filtro_uvis_id,
            "status": filtro_status,
            "mes": mes,
            "ano": ano,
        },
        anos_disponiveis=anos_disponiveis,
        initial_date=initial_date,
        pode_filtrar_uvis=(user_tipo in ["admin", "operario", "visualizar"]),
    )

@bp.route("/agenda/exportar_excel")
def agenda_exportar_excel():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_tipo = session.get("user_tipo")
    user_id = session.get("user_id")

    export_all = request.args.get("all") == "1"

    # filtros (se all=1, ignora)
    filtro_status = None if export_all else (request.args.get("status") or None)
    filtro_uvis_id = None if export_all else request.args.get("uvis_id", type=int)
    mes = None if export_all else request.args.get("mes", type=int)
    ano = None if export_all else request.args.get("ano", type=int)

    query = Solicitacao.query.options(joinedload(Solicitacao.autor))

    # permissões
    if user_tipo not in ["admin", "operario", "visualizar"]:
        query = query.filter(Solicitacao.usuario_id == user_id)
        filtro_uvis_id = None  # UVIS não filtra outras UVIS
    else:
        if filtro_uvis_id:
            query = query.filter(Solicitacao.usuario_id == filtro_uvis_id)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if mes and ano:
        filtro_mesano = f"{ano}-{mes:02d}"
        query = query.filter(
            db.func.strftime("%Y-%m", Solicitacao.data_agendamento) == filtro_mesano
        )

    query = query.order_by(
        Solicitacao.data_agendamento.desc(),
        Solicitacao.hora_agendamento.desc()
    )
    eventos = query.all()

    # -----------------------------
    # Monta XLSX
    # -----------------------------
    wb = Workbook()
    ws = wb.active
    ws.title = "Agenda"

    headers = [
        "DATA",
        "HORÁRIO",
        "REGIÃO",
        "UVIS",
        "CET",
        "ENDEREÇO DA AÇÃO",
        "CEP",
        "FOCO DA AÇÃO",
        "COORDENADA GEOGRÁFICA",
        "Altura dos Voos",
        "Protocolo DECA",
        "Status",
    ]
    ws.append(headers)

    for p in eventos:
        # Endereço completo
        endereco_completo = (
            f"{p.logradouro or ''}, {getattr(p, 'numero', '')} - "
            f"{p.bairro or ''} - "
            f"{(p.cidade or '')}/{(p.uf or '')} - "
            f"{p.cep or ''}"
        )
        if getattr(p, "complemento", None):
            endereco_completo += f" - {p.complemento}"

        cet_txt = "SIM" if getattr(p, "apoio_cet", None) else "NÃO"

        data_str = p.data_agendamento.strftime("%d/%m/%Y") if p.data_agendamento else ""
        hora_str = p.hora_agendamento.strftime("%H:%M") if p.hora_agendamento else ""

        uvis_nome = p.autor.nome_uvis if getattr(p, "autor", None) else ""
        regiao = p.autor.regiao if getattr(p, "autor", None) else ""
       

        lat = getattr(p, "latitude", "") or ""
        lon = getattr(p, "longitude", "") or ""
        coordenada = f"{lat},{lon}" if (lat or lon) else ""

        protocolo_deca = getattr(p, "protocolo_deca", None)
        if not protocolo_deca:
            protocolo_deca = getattr(p, "protocolo", "") or ""

        ws.append([
            data_str,
            hora_str,
            regiao,
            uvis_nome,
            cet_txt,
            endereco_completo,
            getattr(p, "cep", "") or "",
            getattr(p, "foco", "") or "",
            coordenada,
            getattr(p, "altura_voo", "") or "",
            protocolo_deca,
            getattr(p, "status", "") or "",
        ])

    # -----------------------------
    # Estilo (aplica uma vez)
    # -----------------------------
    header_fill = PatternFill("solid", fgColor="0D6EFD")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    wrap = Alignment(vertical="top", wrap_text=True)

    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.fill = header_fill
        c.font = header_font
        c.alignment = center

    thin = Side(style="thin", color="D0D7DE")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.border = border
            cell.alignment = wrap if cell.row > 1 else center

    # largura automática simples
    for col in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col)
        for cell in ws[col_letter]:
            v = str(cell.value) if cell.value is not None else ""
            max_len = max(max_len, len(v))
        ws.column_dimensions[col_letter].width = min(max(12, max_len + 2), 60)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    nome = "agenda_tudo.xlsx" if export_all else "agenda_exportada.xlsx"
    return send_file(
        bio,
        as_attachment=True,
        download_name=nome,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# -------------------------------------------------
# CONTADOR (badge) NO BASE.HTML
# -------------------------------------------------
@bp.context_processor
def inject_notificacoes():
    if 'user_id' not in session:
        return dict(notif_count=0)

    user_id = session.get("user_id")
    user_tipo = session.get("user_tipo")

    if user_tipo in ["admin", "operario", "visualizar"]:
        notif_count = Notificacao.query.filter_by(lida_em=None).count()
    else:
        notif_count = Notificacao.query.filter_by(usuario_id=user_id, lida_em=None).count()

    return dict(notif_count=notif_count)


# -------------------------------------------------
# CRIAR NOTIFICAÇÃO
# -------------------------------------------------
def criar_notificacao(usuario_id, titulo, mensagem="", link=None):
    n = Notificacao(
        usuario_id=usuario_id,
        titulo=titulo,
        mensagem=mensagem or "",
        link=link
    )
    db.session.add(n)
    db.session.commit()
    return n


# -------------------------------------------------
# GARANTIR NOTIFICAÇÕES DO DIA (sem duplicar)
# - Admin/Operário/Visualizar: cria notificações "globais" (usuario_id = admin logado)
# - UVIS: cria apenas para ela mesma (usuario_id = uvis logada)
# -------------------------------------------------
def garantir_notificacoes_do_dia(usuario_id):
    hoje = date.today()

    ags = (
        Solicitacao.query
        .options(joinedload(Solicitacao.autor))
        .filter_by(usuario_id=usuario_id)
        .filter(Solicitacao.data_agendamento == hoje)
        .all()
    )

    for s in ags:
        hora_fmt = s.hora_agendamento.strftime("%H:%M") if s.hora_agendamento else "00:00"

        # 🔒 chave estável (NÃO mude mais esse formato)
        link = url_for("main.agenda", sid=s.id, d=hoje.isoformat())

        ja_existe = (
            Notificacao.query
            .filter_by(usuario_id=usuario_id, link=link)
            .first()
        )
        if ja_existe:
            continue

        criar_notificacao(
            usuario_id=usuario_id,
            titulo="Agendamento para hoje",
            mensagem=f"Você tem um agendamento hoje às {hora_fmt} (Foco: {s.foco}).",
            link=link
        )



# -------------------------------------------------
# LER NOTIFICAÇÃO
# -------------------------------------------------
@bp.route("/notificacoes/<int:notif_id>/ler")
def ler_notificacao(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session["user_id"]
    user_tipo = session.get("user_tipo")

    if user_tipo in ["admin", "operario", "visualizar"]:
        n = Notificacao.query.get_or_404(notif_id)
    else:
        n = Notificacao.query.filter_by(id=notif_id, usuario_id=user_id).first_or_404()

    if n.lida_em is None:
        n.lida_em = datetime.utcnow()
        db.session.commit()

    return redirect(n.link or url_for("main.notificacoes"))


@bp.route("/notificacoes")
def notificacoes():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session["user_id"]
    user_tipo = session.get("user_tipo")

    # ✅ só UVIS gera lembrete do dia (pro próprio usuário)
    if user_tipo not in ["admin", "operario", "visualizar"]:
        garantir_notificacoes_do_dia(user_id)

    # ✅ admin vê tudo, uvis só as dela
    if user_tipo in ["admin", "operario", "visualizar"]:
        itens = Notificacao.query.order_by(Notificacao.criada_em.desc()).all()
    else:
        itens = (Notificacao.query
                 .filter_by(usuario_id=user_id)
                 .order_by(Notificacao.criada_em.desc())
                 .all())

    return render_template("notificacoes.html", itens=itens)

# -------------------------------------------------
# EXCLUIR UMA NOTIFICAÇÃO
# -------------------------------------------------
@bp.route("/notificacoes/<int:notif_id>/excluir", methods=["POST"])
def excluir_notificacao(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session["user_id"]
    user_tipo = session.get("user_tipo")

    if user_tipo in ["admin", "operario", "visualizar"]:
        n = Notificacao.query.get_or_404(notif_id)
    else:
        n = Notificacao.query.filter_by(id=notif_id, usuario_id=user_id).first_or_404()

    db.session.delete(n)
    db.session.commit()

    return redirect(url_for("main.notificacoes"))

# -------------------------------------------------
# LIMPAR TODAS AS NOTIFICAÇÕES
# -------------------------------------------------
@bp.route("/notificacoes/limpar", methods=["POST"])
def limpar_notificacoes():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session["user_id"]
    user_tipo = session.get("user_tipo")

    if user_tipo in ["admin", "operario", "visualizar"]:
        Notificacao.query.delete()
    else:
        Notificacao.query.filter_by(usuario_id=user_id).delete()

    db.session.commit()
    return redirect(url_for("main.notificacoes"))

# ==========================
# CHATBOT UVIS (FAQ inteligente)
# ==========================
import re
import unicodedata
from flask import jsonify, request, session

def _norm(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text

UVIS_FAQ = [
    {
        "title": "Status da solicitação",
        "keywords": ["status", "pendente", "em analise", "aprovado", "negado", "protocolo"],
        "answer": (
            "📌 **Significado dos status**:\n"
            "- **Pendente**: solicitação registrada e aguardando início do processo.\n"
            "- **Em Análise**: pedido em validação pela equipe responsável.\n"
            "- **Aprovado**: pedido autorizado (pode aparecer o número de protocolo).\n"
            "- **Aprovado com Recomendações**: pedido aprovado com sugestões de melhoria.\n"
            "- **Negado**: pedido não aprovado (o motivo aparece nos detalhes).\n\n"
            "💡 Dica: clique em **Detalhes** para ver justificativa/protocolo."
        ),
    },
    {
        "title": "O que tem na tela 'Minhas Solicitações' (Dashboard)",
        "keywords": ["dashboard", "minhas solicitacoes", "tela inicial", "filtro", "detalhes", "nova solicitacao"],
        "answer": (
            "Na tela **Minhas Solicitações** você encontra:\n"
            "- Botão **Nova Solicitação** (abre o formulário)\n"
            "- **Filtro por status** (Pendente, Em Análise, Aprovado, Aprovado com Recomendações, Negado)\n"
            "- **Tabela** com data/hora, localização e foco\n"
            "- Botão **Detalhes** (abre um modal com informações completas)\n"
        ),
    },
    {
        "title": "Campos obrigatórios ao criar uma solicitação",
        "keywords": ["novo", "nova solicitacao", "cadastro", "campos", "obrigatorio", "cep", "numero", "tipo de visita", "altura", "foco"],
        "answer": (
            "✅ No cadastro de uma nova solicitação, atenção aos campos:\n"
            "- **Data** e **Hora** (obrigatórios)\n"
            "- **CEP** (8 dígitos) para preencher endereço automático\n"
            "- **Logradouro** (confirmar) e **Número** (preencher manualmente)\n"
            "- **Tipo de visita** (Monitoramento / Aedes / Culex)\n"
            "- **Altura do voo** (10m, 20m, 30m, 40m)\n"
            "- **Foco da ação** (ex.: Imóvel Abandonado, Piscina/Caixa d’água, Terreno Baldio, Ponto Estratégico)\n"
        ),
    },
    {
        "title": "CEP / endereço não encontrado e boas práticas",
        "keywords": ["cep", "endereco", "logradouro", "bairro", "cidade", "uf", "nao encontrado", "boas praticas"],
        "answer": (
            "Se o **CEP não for encontrado**, preencha o endereço manualmente e revise.\n"
            "Boas práticas:\n"
            "- confira se o **CEP** corresponde ao local\n"
            "- verifique logradouro/bairro/cidade/UF\n"
            "- preencha o **número** (sem ele pode dificultar a localização)\n"
        ),
    },
    {
        "title": "Latitude/Longitude e mapa",
        "keywords": ["latitude", "longitude", "coordenadas", "gps", "mapa"],
        "answer": (
            "📍 **Latitude/Longitude** é opcional (recomendado) e melhora a precisão.\n"
            "Se houver coordenadas, o sistema pode oferecer acesso rápido ao mapa."
        ),
    },
    {
        "title": "Notificações e Agenda",
        "keywords": ["notificacao", "notificacoes", "agenda", "calendario", "lembrete"],
        "answer": (
            "🔔 Em **Notificações**, você vê alertas da unidade (lembretes do dia/atualizações).\n"
            "Ao clicar, pode ser direcionado para a **Agenda**, que mostra os agendamentos por mês/semana/lista."
        ),
    },
    {
        "title": "Checklist antes de enviar",
        "keywords": ["checklist", "antes de enviar", "enviar pedido", "validar"],
        "answer": (
            "🧾 **Checklist rápido antes de enviar**:\n"
            "☐ Data e hora corretas\n"
            "☐ CEP válido e endereço conferido\n"
            "☐ Número preenchido\n"
            "☐ Tipo de visita e altura do voo selecionados\n"
            "☐ Foco da ação selecionado\n"
            "☐ Observações (se necessário) com informações objetivas\n"
        ),
    },
    {
        "title": "Suporte",
        "keywords": ["suporte", "erro", "acesso", "login", "senha"],
        "answer": (
            "Se a dúvida for de **erro de acesso**, inconsistência de **CEP/endereço**, ou algo fora do fluxo: "
            "entre em contato com o time de desenvolvimento/suporte da IJA."
        ),
    },
]

@bp.route("/api/uvis/chatbot", methods=["POST"])
def uvis_chatbot():
    # protege: só usuário logado
    if "user_id" not in session:
        return jsonify({"answer": "Sessão expirada. Faça login novamente."}), 401

    payload = request.get_json(silent=True) or {}
    msg = (payload.get("message") or "").strip()

    if not msg:
        return jsonify({"answer": "Escreva sua dúvida (ex.: “o que significa Em Análise?”)."}), 400

    nmsg = _norm(msg)

    best = None
    best_score = 0

    for item in UVIS_FAQ:
        score = 0
        for kw in item["keywords"]:
            if kw in nmsg:
                score += 1
        if score > best_score:
            best_score = score
            best = item

    if not best or best_score == 0:
        sugestoes = [
            "• “O que significa Pendente/Em Análise/Aprovado/Aprovado com Recomendações/Negado?”",
            "• “Quais campos são obrigatórios na Nova Solicitação?”",
            "• “O que fazer se o CEP não encontrar?”",
            "• “Qual o checklist antes de enviar?”",
            "• “Como funciona Notificações e Agenda?”",
        ]
        return jsonify({
            "answer": (
                "Não encontrei essa dúvida diretamente no manual.\n\n"
                "Tenta uma dessas perguntas:\n" + "\n".join(sugestoes)
            ),
            "matched": None,
            "confidence": 0,
        }), 200

    return jsonify({
        "answer": best["answer"],
        "matched": best["title"],
        "confidence": best_score,
    }), 200
@bp.route("/solicitacao/<int:id>/anexo", endpoint="baixar_anexo")
@bp.route("/admin/solicitacao/<int:id>/anexo", endpoint="baixar_anexo")
def baixar_anexo(id):
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_tipo = session.get("user_tipo")
    user_id = int(session.get("user_id"))

    pedido = Solicitacao.query.get_or_404(id)

    # ✅ Permissões:
    # Admin/Operário/Visualizar: pode baixar qualquer um
    # UVIS: só pode baixar se for dono da solicitação
    if user_tipo not in ["admin", "operario", "visualizar", "uvis"]:
        flash("Permissão negada.", "danger")
        return redirect(url_for("main.dashboard"))

    if user_tipo == "uvis" and pedido.usuario_id != user_id:
        flash("Permissão negada.", "danger")
        return redirect(url_for("main.dashboard"))

    if not pedido.anexo_path:
        flash("Essa solicitação não tem anexo.", "warning")
        return redirect(url_for("main.dashboard"))

    upload_folder = os.path.abspath(os.path.join(bp.root_path, "..", "..", "upload-files"))
    filename = pedido.anexo_path.replace("upload-files/", "", 1)

    file_path = os.path.join(upload_folder, filename)
    if not os.path.exists(file_path):
        flash("Arquivo não encontrado no servidor.", "warning")
        return redirect(url_for("main.dashboard"))

    return send_from_directory(upload_folder, filename, as_attachment=True)
