# ==========================
# IMPORTS PADRÃO PYTHON
# ==========================
import os
import re
import tempfile
import unicodedata
import math
from datetime import date, datetime
from io import BytesIO
import json
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
from pyparsing import col
from werkzeug.utils import secure_filename
import uuid
import os
import threading
from flask import render_template, url_for
from flask_login import login_required, current_user

# ==========================
# FLASK
# ==========================
from flask import (Blueprint, after_this_request, current_app, flash, jsonify,
                redirect, render_template, request, send_file,
                send_from_directory, url_for)


from flask_login import current_user , login_required

# ==========================
# EXCEL / PDF
# ==========================
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import landscape
# ==========================
# SQLALCHEMY / BANCO
# ==========================
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

# ==========================
# APP
# ==========================
from app import db
from app.models import (
    Abastecimento,
    Clientes,
    Equipe,
    EquipePiloto,
    EquipeUvis,
    LogVeiculo,
    Notificacao,
    OrdemServico,
    Pilotos,
    Solicitacao,
    Usuario,
    Veiculos,
)
TZ = ZoneInfo("America/Sao_Paulo")
print("--- ROTAS CARREGADAS COM SUCESSO ---")

bp = Blueprint('main', __name__)

@bp.context_processor
def inject_globals():
    """
    Otimizado e blindado contra erros de transação. 
    Se o banco falhar, retorna 0 notificações mas não derruba o sistema.
    """
    if current_user.is_authenticated:
        try:
            # Consulta de contagem direta no banco
            q = db.session.query(db.func.count(Notificacao.id)).filter(
                Notificacao.lida_em.is_(None),
                Notificacao.apagada_em.is_(None)
            )
            
            if current_user.tipo_usuario not in ["admin", "operario", "visualizar"]:
                q = q.filter(Notificacao.usuario_id == current_user.id)
                
            return dict(notif_count=q.scalar() or 0)
        except Exception as e:
            # Se houver erro de transação (Transaction Aborted), limpamos aqui
            db.session.rollback()
            # Opcional: print(f"Erro no inject_globals (notificações): {e}")
            return dict(notif_count=0) 
            
    return dict(notif_count=0)

def inject_google_key():
    return {"google_maps_key": current_app.config.get("KEY_API_GOOGLE_MAPS") or os.getenv("KEY_API_GOOGLE_MAPS")}


# --- 2: FILTRO DE DATA PARA JINJA2 ---
@bp.app_template_filter('datetimeformat')
def datetimeformat(value, format='%d-%m-%y'):
    """
    Filtro para formatar datas no Jinja2.
    Otimizado para lidar com strings, objetos datetime e valores nulos.
    """
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            # Se for string (ex: '2025-12-31'), converte para objeto date antes de formatar
            return datetime.strptime(value, "%Y-%m-%d").strftime(format)
        return value.strftime(format)
    except Exception:
        return value # Retorna o valor original em caso de erro para não quebrar a página
    
# --- 3: CÁLCULO DE DISTÂNCIA ENTRE COORDENADAS ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    # Raio da Terra em metros
    R = 6371000 
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(dlambda / 2)**2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


AREAS_GEOFENCING = [
    {"nome": "Aeroporto de Congonhas (CGH)", "lat": -23.6273, "lng": -46.6565, "raio": 5400},
    {"nome": "Aeroporto Campo de Marte (RTE)", "lat": -23.5092, "lng": -46.6377, "raio": 5400},
    {"nome": "Aeroporto de Guarulhos (GRU)", "lat": -23.4356, "lng": -46.4731, "raio": 9000},
    {"nome": "Aeroporto de Viracopos (VCP)", "lat": -23.0069, "lng": -47.1344, "raio": 9000},
    {"nome": "Zona de Helipontos (Av. Paulista)", "lat": -23.5615, "lng": -46.6559, "raio": 2000},
    {"nome": "Base Aérea de Santos", "lat": -23.9275, "lng": -46.2975, "raio": 5400},
]


def detectar_area_restrita(latitude, longitude):
    if latitude is None or longitude is None:
        return False

    for area in AREAS_GEOFENCING:
        distancia = calcular_distancia(latitude, longitude, area["lat"], area["lng"])
        if distancia < area["raio"]:
            return True

    return False

def get_upload_folder():
    """
    Localiza a pasta de uploads de forma absoluta.
    Garante que a pasta exista sem processamento repetitivo desnecessário.
    """
    # Pasta 'upload-files' no mesmo nível da pasta 'app'
    folder = os.path.join(current_app.root_path, '..', 'upload-files')
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    return os.path.abspath(folder)

import unicodedata

def normalize_string(value):
    if value:
        return ''.join(
            c for c in unicodedata.normalize('NFD', value)
            if unicodedata.category(c) != 'Mn'
        ).lower()
    return value


def allowed_file(filename: str) -> bool:
    """Verifica se a extensão do arquivo é permitida."""
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

from sqlalchemy import extract, cast, Integer, func

def aplicar_filtros_base(query, filtro_data, uvis_id):
    if filtro_data:
        try:
            # filtro_data = "2026-01"
            ano, mes = map(int, filtro_data.split('-'))
            
            # Forçamos a comparação de INTEIRO com INTEIRO
            query = query.filter(
                cast(extract('year', Solicitacao.data_agendamento), Integer) == ano,
                cast(extract('month', Solicitacao.data_agendamento), Integer) == mes
            )
            print(f"DEBUG SQL: Filtrando por Ano={ano} e Mes={mes}")
        except Exception as e:
            print(f"Erro no filtro de data: {e}")

    if uvis_id:
        query = query.filter(Solicitacao.usuario_id == int(uvis_id))
            
    return query

from functools import wraps
from flask import abort
from flask_login import current_user

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.tipo_usuario not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

import os
from datetime import datetime
from flask import request, redirect, url_for, render_template
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func

# ajuste imports conforme seu projeto:
# from app import db
# from app.models import Solicitacao, Equipe, EquipeUvis, EquipeUvis...