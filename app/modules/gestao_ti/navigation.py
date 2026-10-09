"""Choose an authorized landing page without replacing the existing sidebars."""
from flask import current_app
from app.modules.gestao_ti.permissions import can_access_endpoint, has_permission, profile_code

# API, file and background-job endpoints are deliberately not navigation entries.
SCREENS = {
 'prefeitura.solicitacoes': [('admin_dashboard','Solicitações'),('novo','Nova solicitação'),('admin_canceladas','Canceladas')],
 'prefeitura.os': [('admin_historico_os','Histórico de OS')],
 'prefeitura.clientes': [('clientes_menu','Visão geral'),('listar_clientes','Clientes'),('admin_uvis_listar','UVIS'),('cadastrar_clientes','Cadastrar cliente'),('admin_uvis_novo','Cadastrar UVIS')],
 'prefeitura.equipes': [('listar_equipes','Equipes OA'),('listar_pilotos','Pilotos'),('admin_listar_equipes_uvis','Equipes UVIS'),('cadastrar_equipes','Cadastrar equipe'),('cadastrar_pilotos','Cadastrar piloto')],
 'prefeitura.equipamentos': [('listar_equipamentos','Visão geral'),('listar_drones','Drones'),('listar_baterias','Baterias'),('equipamentos_manutencao','Em manutenção'),('equipamentos_manutencoes_historico','Histórico de manutenção'),('cadastrar_drone','Cadastrar drone'),('cadastrar_bateria','Cadastrar bateria'),('importar_planilha_drones','Importar drones')],
 'prefeitura.veiculos': [('veiculos_menu','Visão geral'),('listar_veiculos','Frota'),('veiculos_rastreamento','Rastreamento'),('veiculos_limpezas','Limpezas'),('veiculos_alertas_limpeza','Alertas de limpeza'),('cadastrar_veiculo','Cadastrar veículo')],
 'prefeitura.logs_veiculos': [('veiculos_logs','Histórico de veículos')],
 'prefeitura.checklists': [('admin_checklists_semanais','Checklists semanais')],
 'prefeitura.relatorios': [('relatorios','Relatórios')],
 'prefeitura.mapas': [('mapa_relatorio','Mapas'),('agenda','Agenda'),('consultar_endereco_geolocalizacao','Geolocalização')],
 'prefeitura.denuncias': [('denuncias_listar','Denúncias')],
 'prefeitura.prefeituras': [('admin_prefeituras','Prefeituras'),('admin_prefeitura_nova','Cadastrar prefeitura')],
 'prefeitura.voos': [('relatorios_dji_logs','Logs de voo DJI')],
 'prefeitura.vigilancia': [('vigilancia_validacao','Vigilância')],
 'agro.clientes': [('agro_clientes_menu','Visão geral'),('agro_clientes_listar','Clientes'),('agro_fornecedores_listar','Fornecedores'),('agro_cliente_novo','Cadastrar cliente'),('agro_fornecedor_novo','Cadastrar fornecedor')],
 'agro.comercial': [('agro_orcamentos_listar','Orçamentos'),('agro_orcamento_novo','Novo orçamento')],
 'agro.contratos': [('agro_contratos_listar','Contratos'),('agro_contratos_template','Template de contrato')],
 'agro.mapeamentos': [('agro_orcamentos_template_mapeamento','Mapeamentos')],
 'agro.os': [('agro_os_listar','Ordens de serviço')],
 'agro.equipes': [('agro_equipes_listar','Equipes'),('agro_pilotos_listar','Pilotos'),('agro_equipe_nova','Cadastrar equipe'),('agro_piloto_novo','Cadastrar piloto')],
 'agro.equipamentos': [('agro_equipamentos_listar','Equipamentos'),('agro_equipamento_novo','Cadastrar equipamento'),('agro_importar_planilha_drones','Importar equipamentos')],
 'agro.voos': [('agro_logs_voo','Logs de voo')],
 'agro.talentos': [('agro_talentos_listar','Banco de talentos'),('agro_talento_novo','Cadastrar candidato')],
 'financeiro.contas': [('agro_financeiro_contas','Visão geral'),('agro_contas_receber_listar','Contas a receber'),('agro_contas_pagar_listar','Contas a pagar'),('agro_financeiro_entrada_novo','Nova entrada'),('agro_financeiro_saida_novo','Nova saída')],
 'financeiro.caixa': [('agro_caixa_diario','Caixa diário')],
 'financeiro.bancos': [('agro_bancos_listar','Bancos'),('agro_bancos_conciliacao','Conciliação'),('agro_banco_novo','Cadastrar banco')],
 'financeiro.comprovantes': [('agro_contratos_comprovantes','Comprovantes')],
 'financeiro.relacionamentos': [('financeiro_empresa_fornecedores','Fornecedores')],
 'financeiro.comercial': [('financeiro_empresa_clientes','Clientes'),('financeiro_empresa_comercial','Comercial')],
 'financeiro.relatorios': [('agro_financeiro_dashboard','Painel financeiro'),('agro_relatorio_contas_geral','Relatório geral')],
 'financeiro.configuracoes': [('financeiro_empresa_configuracoes','Configurações'),('agro_financeiro_categorias_listar','Categorias')],
 'sistema.usuarios': [('admin_usuarios_listar','Usuários'),('admin_usuario_novo','Cadastrar usuário')],
 'sistema.perfis': [('central_ti','Central de TI')],
 'sistema.suporte': [('feedback_listar','Suporte'),('feedback_novo','Novo chamado')],
 'sistema.bugs': [('bugs_listar','Bugs'),('bug_report_novo','Reportar problema')],
 'sistema.estoque': [('estoque_listar','Estoque'),('estoque_novo','Cadastrar item')],
 'sistema.operacional': [('painel_operacional','Painel operacional')],
 'sistema.auditoria': [('admin_logs_usuarios','Auditoria e presença'),('veiculos_logs_excluidos','Logs excluídos')],
 'sistema.tecnico': [('dev_dashboard','Ferramentas técnicas')],
 'sistema.backups': [('backups_list_page','Backups')],
}


def _screens_for(user, key):
    role = profile_code(user)
    overrides = {
        'piloto': {
            'prefeitura.os': [('piloto_os', 'Ordens de serviço'), ('piloto_os_historico', 'Histórico de OS')],
            'prefeitura.veiculos': [('piloto_veiculos', 'Veículos'), ('piloto_caixa_entrada', 'Alertas'), ('listar_veiculos', 'Frota')],
            'prefeitura.checklists': [('piloto_checklist_semanal', 'Checklists semanais')],
        },
        'uvis': {
            'prefeitura.solicitacoes': [('dashboard', 'Solicitações'), ('novo', 'Nova solicitação'), ('solicitacoes_canceladas', 'Canceladas')],
            'prefeitura.os': [('uvis_historico_os', 'Histórico de OS')],
        },
        'equipe_uvis': {
            'prefeitura.os': [('dashboard_equipe_uvis', 'Ordens de serviço'), ('equipe_uvis_os_historico', 'Histórico de OS')],
        },
        'piloto_agro': {
            'agro.os': [('agro_piloto_os_listar', 'Ordens de serviço')],
            'agro.mapeamentos': [('agro_piloto_mapeamentos_listar', 'Mapeamentos')],
        },
    }
    return overrides.get('piloto' if role == 'equipe_oceano' else role, {}).get(key, SCREENS.get(key, ()))


def first_allowed_screen_endpoint(user, area=None):
    if area == 'financeiro' and has_permission(user, 'area:financeiro'):
        return 'main.financeiro_central'
    for key in SCREENS:
        if area and not key.startswith(area + '.'):
            continue
        # Company screens are entered through the company selector.
        if key.startswith('financeiro.') and has_permission(user, 'area:financeiro'):
            return 'main.financeiro_central'
        for screen, _ in _screens_for(user, key):
            endpoint = 'main.' + screen
            if endpoint == 'main.vigilancia_validacao' and not current_app.config.get('VIGILANCIA_PREVIEW_ENABLED'):
                continue
            if can_access_endpoint(user, endpoint) and any(
                not rule.arguments for rule in current_app.url_map.iter_rules(endpoint)
            ):
                return endpoint
    return None


def area_home_endpoint(user, area):
    if not has_permission(user, 'area:' + area):
        return None
    role = profile_code(user)
    if area == 'financeiro':
        return 'main.financeiro_central'
    if area == 'agro':
        return 'main.agro_piloto_dashboard' if role == 'piloto_agro' else 'main.admin_agro'
    if area == 'prefeitura':
        endpoint = {
            'piloto': 'main.piloto_os', 'equipe_oceano': 'main.piloto_os',
            'equipe_uvis': 'main.dashboard_equipe_uvis', 'uvis': 'main.dashboard',
        }.get(role, 'main.admin_dashboard')
        if can_access_endpoint(user, endpoint):
            return endpoint
    return first_allowed_screen_endpoint(user, area)
