from flask import Blueprint
from app.core.errors import register_error_handlers
from app.core.routes import register_core_routes
from app.core.templating import register_template_helpers
from app.modules.admin_checklists import register_routes as register_admin_checklists_routes
from app.modules.admin_dashboard import register_routes as register_admin_dashboard_routes
from app.modules.admin_uvis import register_routes as register_admin_uvis_routes
from app.modules.agro import register_routes as register_agro_routes
from app.modules.auditoria import register_routes as register_auditoria_routes
from app.modules.agenda_notificacoes import register_routes as register_agenda_notificacoes_routes
from app.modules.anexos import register_routes as register_anexos_routes
from app.modules.backup import register_routes as register_backup_routes
from app.modules.canceladas import register_routes as register_canceladas_routes
from app.modules.cep import register_routes as register_cep_routes
from app.modules.chatbot import register_routes as register_chatbot_routes
from app.modules.clientes import register_routes as register_clientes_routes
from app.modules.dashboard import register_routes as register_dashboard_routes
from app.modules.dji_flight_logs import register_routes as register_dji_flight_logs_routes
from app.modules.drones_import import register_routes as register_drones_import_routes
from app.modules.equipamentos import register_routes as register_equipamentos_routes
from app.modules.equipe_uvis_dashboard import register_routes as register_equipe_uvis_dashboard_routes
from app.modules.equipes import register_routes as register_equipes_routes
from app.modules.mapas import register_routes as register_mapas_routes
from app.modules.piloto_checklists import register_routes as register_piloto_checklists_routes
from app.modules.piloto_os import register_routes as register_piloto_os_routes
from app.modules.pilotos import register_routes as register_pilotos_routes
from app.modules.relatorios import register_routes as register_relatorios_routes
from app.modules.solicitacoes import register_routes as register_solicitacoes_routes
from app.modules.uvis_equipes import register_routes as register_uvis_equipes_routes
from app.modules.usuarios import register_routes as register_usuarios_routes
from app.modules.veiculos import register_routes as register_veiculos_routes


print("--- ROTAS CARREGADAS COM SUCESSO ---")

bp = Blueprint("main", __name__)
register_core_routes(bp)
register_error_handlers(bp)
register_template_helpers(bp)
register_admin_checklists_routes(bp)
register_admin_dashboard_routes(bp)
register_admin_uvis_routes(bp)
register_agro_routes(bp)
register_auditoria_routes(bp)
register_agenda_notificacoes_routes(bp)
register_anexos_routes(bp)
register_backup_routes(bp)
register_canceladas_routes(bp)
register_cep_routes(bp)
register_chatbot_routes(bp)
register_clientes_routes(bp)
register_dashboard_routes(bp)
register_dji_flight_logs_routes(bp)
register_drones_import_routes(bp)
register_equipamentos_routes(bp)
register_equipe_uvis_dashboard_routes(bp)
register_equipes_routes(bp)
register_mapas_routes(bp)
register_piloto_checklists_routes(bp)
register_piloto_os_routes(bp)
register_pilotos_routes(bp)
register_relatorios_routes(bp)
register_solicitacoes_routes(bp)
register_uvis_equipes_routes(bp)
register_usuarios_routes(bp)
register_veiculos_routes(bp)
