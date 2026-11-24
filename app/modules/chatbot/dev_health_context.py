"""Bounded route classification and technical evidence for health triage."""
import hashlib
import re

from flask import current_app
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

from app.modules.chatbot import dev_audit, dev_code
from app.modules.gestao_ti.permissions import can_access_endpoint

CHECK_ACTIONS = {
    'Banco de dados': 'Execute o teste Banco na aba Infra e confira a exceção e a conectividade do banco nos logs do servidor.',
    'Chave da sessão': 'Configure uma chave de sessão persistente no ambiente; valide login e continuidade de sessão após reiniciar o processo.',
    'Google Maps': 'Confira a configuração da chave e suas restrições de domínio; valide o carregamento do mapa na tela afetada.',
    'Dropbox / backup': 'Confira as credenciais configuradas; execute o teste de backup e valide uma restauração em ambiente isolado.',
    'Modo debug': 'Confirme se este ambiente é de produção; nesse caso, desative o debug na configuração de execução e reinicie o serviço.',
    'Diretório de uploads': 'Confira se o diretório configurado existe e se o usuário do processo pode gravar nele; teste um upload pequeno e sua leitura posterior.',
    'Diretório da instância': 'Confira a existência e as permissões do diretório de instância para o usuário que executa a aplicação.',
}


def route_context(endpoint, path, method):
    adapter = current_app.url_map.bind('localhost')
    matched, accepted = None, []
    try:
        matched, _ = adapter.match(path or '/', method=method or 'GET', return_rule=True)
    except MethodNotAllowed as exc:
        accepted = sorted(exc.valid_methods or [])
        for candidate in accepted:
            try:
                matched, _ = adapter.match(path or '/', method=candidate, return_rule=True)
                break
            except (NotFound, MethodNotAllowed, RequestRedirect):
                continue
    except (NotFound, RequestRedirect):
        pass
    registered = endpoint if endpoint in current_app.view_functions else matched.endpoint if matched else None
    rules = list(current_app.url_map.iter_rules(registered)) if registered else []
    if matched:
        target = matched.rule
    elif rules:
        target = rules[0].rule
    else:
        # Keep only route vocabulary defined by the app; hide IDs, arbitrary slugs and filenames.
        vocabulary = {segment for rule in current_app.url_map.iter_rules() for segment in rule.rule.split('/')
                      if segment and '<' not in segment}
        segments = (path or '/').split('?')[0].split('/')
        target = '/'.join(segment if segment in vocabulary or not segment else ':trecho' for segment in segments)[:180]
    probe = re.search(r'(?:^|/)(\.env|\.git|wp-admin|wp-login\.php|xmlrpc\.php)(?:/|$|\.)', path or '', re.I)
    if probe:
        kind, target = 'sondagem_comum', '/' + probe[1].lower()
        explanation = 'Caminho compatível com sondagens comuns. O padrão isolado não confirma ataque nem falha de uma função do sistema.'
    elif accepted:
        kind = 'metodo_incompativel'
        explanation = 'O caminho corresponde a uma rota atual, mas o método registrado não é aceito por ela.'
    elif registered == 'static' or (path or '').startswith('/static/'):
        kind = 'arquivo_estatico'
        explanation = 'Solicitação de arquivo estático. Confira referência, versão do frontend e presença do arquivo no build publicado.'
    elif registered:
        kind = 'funcao_registrada'
        explanation = 'O caminho está associado a uma função registrada na versão atual do aplicativo.'
    else:
        kind = 'endereco_sem_rota'
        explanation = 'O endereço não corresponde a uma rota na versão atual. Confira chamadas antigas, links e origem na auditoria; não há handler a corrigir identificado.'
    return {'categoria': kind, 'destino': target or '/',
            'grupo_caminho': hashlib.sha256((path or '').encode()).hexdigest()[:10],
            'endpoint': registered, 'metodos_aceitos': accepted or sorted({m for rule in rules for m in rule.methods}),
            'explicacao': explanation,
            'limite': 'O roteamento é da versão atual; não comprova quais rotas existiam na data do erro. Trechos privados do caminho foram omitidos.'}


def investigation(item, user):
    status = item['status']
    route = item['rota']
    if route['categoria'] == 'metodo_incompativel':
        action = f"Compare o método {item['metodo']} da chamada com os métodos aceitos: {', '.join(route['metodos_aceitos'])}. Ajuste a chamada que usa esse caminho."
        validation = 'Teste o método esperado e confirme que métodos não permitidos continuam sendo rejeitados.'
    elif route['categoria'] == 'sondagem_comum':
        action = 'Confira a origem e a frequência na auditoria antes de tratar como defeito do produto. Verifique a exposição desse caminho no servidor.'
        validation = 'Confirme que o caminho continua sem expor conteúdo e acompanhe a recorrência separadamente dos fluxos de usuários.'
    elif status >= 500:
        action = 'Correlacione a exceção capturada com o handler e suas dependências; reproduza a mesma operação antes de alterar o código.'
        validation = 'Teste a operação com sucesso e com falha da dependência; acompanhe este mesmo grupo nas 24h seguintes.'
    elif status == 403:
        action = 'Compare o guard da rota e a permissão efetiva do perfil afetado na Central de TI. Confirme se o bloqueio foi correto antes de mudar a regra.'
        validation = 'Teste um perfil autorizado e outro sem permissão, preservando o bloqueio esperado.'
    elif status == 404 and route['categoria'] == 'funcao_registrada':
        action = 'Confira qual recurso o handler procura antes de devolver 404. Em uploads, verifique existência, expiração e retomada da sessão.'
        validation = 'Teste recurso existente e ausente; para uploads, teste retomada após interrupção e expiração.'
    elif status == 409:
        action = 'Confira o motivo capturado (expired, busy ou stale), a reserva de edição e a versão do registro. Não conclua que o conflito é um defeito sem esse contexto.'
        validation = 'Teste expiração durante o upload e duas abas concorrentes, sem sobrescrever arquivos ou alterações de outro editor.'
    elif status in (400, 413, 415, 422):
        action = 'Confira os campos e metadados exigidos pelo handler e a resposta de validação; em fragmentos de vídeo, confira sessão, ordem e tamanho da parte enviada.'
        validation = 'Teste uma requisição válida e o caso rejeitado; confirme orientação clara no cliente e retomada do upload quando aplicável.'
    else:
        action = route['explicacao'] + ' Abra o registro na auditoria para conferir o contexto da chamada.'
        validation = 'Reproduza o endereço e o fluxo de origem, confirme o comportamento esperado e acompanhe novas ocorrências equivalentes.'
    result = {'registro': item['registro_exemplo'], 'acao': action, 'validacao': validation}
    if not can_access_endpoint(user, 'main.admin_logs_usuarios', 'GET', legacy=True):
        result['cobertura'] = 'Consulta à auditoria não autorizada para este acesso.'
        return result
    audit = dev_audit.context(item['registro_exemplo'])
    selected = audit.get('registro_selecionado', {})
    diagnostic = selected.get('diagnostico', {})
    result['excecao'] = diagnostic.get('excecao')
    result['logs'] = diagnostic.get('logs', [])[:3]
    result['cobertura'] = audit['cobertura']
    if status >= 500 and not result['excecao'] and not result['logs']:
        result['acao'] = 'Este registro não capturou a exceção. Reproduza a operação e colete os logs do servidor no horário e na função indicados; identifique a dependência ou condição que falhou antes de alterar o código.'
    code = dev_code.context(current_app.view_functions.get(route['endpoint']), audit)
    # Bound source evidence across the overview; the individual analysis can go deeper.
    snippets = sorted(code.get('trechos', []), key=lambda part: part.get('origem') != 'stack_trace')[:2]
    result['codigo'] = [{**part, 'codigo': '\n'.join(part['codigo'].splitlines()[:18]),
                         'fim': part['inicio'] + len(part['codigo'].splitlines()[:18]) - 1, 'truncado': True}
                        for part in snippets]
    return result
