import re
import unicodedata


ADMIN_CHATBOT_TYPES = {"dev", "admin", "operario", "visualizar", "regional"}
AGRO_ADMIN_CHATBOT_TYPES = {
    "dev",
    "admin",
    "operario",
    "visualizar",
    "regional",
    "prefeitura_admin",
    "financeiro_admin",
    "financeiro",
}
AGRO_PILOTO_CHATBOT_TYPES = {"piloto_agro"}


UVIS_FAQ = [
    {
        "title": "Status da solicitacao",
        "keywords": ["status", "pendente", "em analise", "aprovado", "negado", "protocolo"],
        "answer": (
            "**Significado dos status**:\n"
            "- **Pendente**: solicitacao registrada e aguardando inicio do processo.\n"
            "- **Em Analise**: pedido em validacao pela equipe responsavel.\n"
            "- **Aprovado**: pedido autorizado (pode aparecer o numero de protocolo).\n"
            "- **Aprovado com Recomendacoes**: pedido aprovado com sugestoes de melhoria.\n"
            "- **Negado**: pedido nao aprovado (o motivo aparece nos detalhes).\n\n"
            "Dica: clique em **Detalhes** para ver justificativa/protocolo."
        ),
    },
    {
        "title": "O que tem na tela Minhas Solicitacoes",
        "keywords": [
            "dashboard",
            "minhas solicitacoes",
            "tela inicial",
            "filtro",
            "detalhes",
            "nova solicitacao",
            "editar",
            "equipes",
            "informacoes",
            "modal",
            "equipe",
        ],
        "answer": (
            "Na tela **Minhas Solicitacoes** voce encontra:\n"
            "- Botao **Nova Solicitacao** (abre o formulario)\n"
            "- **Filtro por status** (Pendente, Em Analise, Aprovado, Aprovado com Recomendacoes, Negado)\n"
            "- **Filtros por tipo de operacao e tipo de visita**\n"
            "- **Tabela** com data/hora, localizacao e foco\n"
            "- Botao **Detalhes** (abre um modal com informacoes completas)\n"
            "- Botao **Adicionar/Editar Equipes** (abre um modal para inserir a equipe responsavel)\n"
            "- Botao **Editar solicitacao** (abre para editar a solicitacao apenas quando esta pendente ou negada.)\n"
        ),
    },
    {
        "title": "Campos obrigatorios ao criar uma solicitacao",
        "keywords": [
            "novo",
            "nova solicitacao",
            "cadastro",
            "campos",
            "obrigatorio",
            "cep",
            "numero",
            "tipo de operacao",
            "tipo de visita",
            "altura",
            "foco",
        ],
        "answer": (
            "No cadastro de uma nova solicitacao, atencao aos campos:\n"
            "- **Data** e **Hora** (obrigatorios)\n"
            "- **CEP** (8 digitos) para preencher endereco automatico\n"
            "- **Logradouro** (confirmar) e **Numero** (preencher manualmente)\n"
            "- **Tipo de operacao** (Monitoramento / Tratamento)\n"
            "- **Tipo de visita** (Aedes / Culex / Outro)\n"
            "- **Altura do voo** (10m, 20m, 30m, 40m)\n"
            "- **Foco da acao** (ex.: Imovel Abandonado, Piscina/Caixa d'agua, Terreno Baldio, Ponto Estrategico)\n"
        ),
    },
    {
        "title": "CEP e endereco",
        "keywords": ["cep", "endereco", "logradouro", "bairro", "cidade", "uf", "nao encontrado", "boas praticas"],
        "answer": (
            "Se o **CEP nao for encontrado**, preencha o endereco manualmente e revise.\n"
            "Boas praticas:\n"
            "- confira se o **CEP** corresponde ao local\n"
            "- verifique logradouro/bairro/cidade/UF\n"
            "- preencha o **numero** corretamente\n"
        ),
    },
    {
        "title": "Latitude e Longitude",
        "keywords": ["latitude", "longitude", "coordenadas", "gps", "mapa", "consulta", "localizacao"],
        "answer": (
            "**Latitude/Longitude** e preenchido automaticamente apos inserir o endereco.\n"
            "Tendo coordenadas, o sistema oferece acesso rapido ao mapa.\n"
            "Voce consegue consultar latitude e longitude na opcao Geolocalizacao.\n"
        ),
    },
    {
        "title": "Notificacoes e Agenda",
        "keywords": ["notificacao", "notificacoes", "agenda", "calendario", "lembrete"],
        "answer": (
            "Em **Notificacoes**, voce ve alertas da unidade (lembretes do dia/atualizacoes).\n"
            "Ao clicar, pode ser direcionado para a **Agenda**, que mostra os agendamentos por mes/lista.\n"
            "Ao clicar em uma solicitacao, abre um modal com as informacoes completas da solicitacao com opcao de tracar a rota.\n"
        ),
    },
    {
        "title": "Checklist antes de enviar",
        "keywords": ["checklist", "antes de enviar", "enviar pedido", "validar"],
        "answer": (
            "**Checklist rapido antes de enviar**:\n"
            "[] Data e hora corretas\n"
            "[] CEP valido e endereco conferido\n"
            "[] Numero preenchido\n"
            "[] Tipo de operacao, tipo de visita e altura do voo selecionados\n"
            "[] Foco da acao selecionado\n"
            "[] Endereco valido?\n"
            "[] Observacoes (se necessario) com informacoes objetivas\n"
        ),
    },
    {
        "title": "Suporte",
        "keywords": ["suporte", "erro", "acesso", "login", "senha", "ajuda"],
        "answer": "Entre em contato com o time de suporte da Oceano Azul: **suporte@ijadrones.com.br**.",
    },
]


ADMIN_FAQ = [
    {
        "title": "Perfis e permissoes",
        "keywords": ["acesso", "perfil", "permissao", "permissoes", "admin", "operario", "visualizar", "regional", "quem pode"],
        "answer": (
            "<b>Perfis do painel:</b><br>"
            "- <b>Administrador</b>: acesso total (<b>editar</b>, <b>excluir</b>, <b>gerenciar UVIS</b>, <b>relatorios</b> e <b>agenda</b>).<br>"
            "- <b>Operario</b>: consegue <b>salvar decisoes</b> (<b>status</b>, <b>protocolo</b> e <b>justificativa</b>).<br>"
            "- <b>Visualizar</b>: <b>apenas leitura</b>.<br>"
            "- <b>Regional</b>: <b>apenas leitura</b>, com acesso limitado a <b>sua regiao</b>.<br>"
        ),
    },
    {
        "title": "Filtros no painel",
        "keywords": ["filtro", "filtrar", "status", "unidade", "uvis", "regiao", "buscar", "pesquisar"],
        "answer": (
            "<b>No painel voce pode filtrar por:</b><br>"
            "- <b>Status</b><br>"
            "- <b>Unidade (UVIS)</b><br>"
            "- <b>Regiao</b><br>"
            "Use os <b>filtros</b> para encontrar <b>solicitacoes especificas</b> rapidamente."
        ),
    },
    {
        "title": "Ola! Como posso ajudar?",
        "keywords": ["ola", "oi", "hello", "hi", "bom dia", "boa tarde", "boa noite", "ajuda", "suporte"],
        "answer": (
            "Ola! Sou o <b>assistente virtual</b> do <b>painel administrativo</b>.<br>"
            "<b>Posso ajudar</b> com duvidas sobre:<br>"
            "- <b>Perfis e permissoes</b><br>"
            "- <b>Filtros no painel</b><br>"
            "- <b>Salvar decisao</b><br>"
            "- <b>Editar completo</b><br>"
            "- <b>Excluir solicitacao</b><br>"
            "- <b>Anexos</b><br>"
            "- <b>GPS e mapa</b><br>"
            "- <b>Exportar Excel</b><br>"
            "- <b>Agenda</b><br>"
            "- <b>Relatorios</b><br>"
            "- <b>Gestao de UVIS</b><br>"
            "- <b>Google Maps</b><br>"
            "<b>Como posso ajudar voce hoje?</b>"
        ),
    },
    {
        "title": "Salvar decisao",
        "keywords": ["salvar", "decisao", "status", "protocolo", "justificativa", "aprovado", "negado", "analise", "recomendacoes"],
        "answer": (
            "Em cada <b>solicitacao</b> voce pode definir:<br>"
            "- <b>Status</b><br>"
            "- <b>Protocolo</b><br>"
            "- <b>Justificativa</b> (obrigatoria ao <b>negar</b> ou <b>orientar</b>)<br>"
            "Se o perfil for <b>Visualizar</b> ou <b>Regional</b>, fica em <b>somente leitura</b>."
        ),
    },
    {
        "title": "Editar completo",
        "keywords": ["editar", "editar completo", "corrigir", "alterar", "data", "hora", "endereco", "agendamento"],
        "answer": (
            "<b>Editar completo</b> serve para <b>corrigir todos os dados</b> do pedido:<br>"
            "<b>Data/Hora</b>, <b>Endereco</b>, <b>Foco</b>, <b>Tipo de operacao</b>, <b>Tipo de visita</b>, <b>Altura</b> e <b>Observacoes</b>.<br>"
            "Em alguns casos o sistema pode gerar <b>notificacao para a unidade</b>."
        ),
    },
    {
        "title": "Excluir solicitacao",
        "keywords": ["excluir", "deletar", "apagar", "remover"],
        "answer": (
            "<b>Excluir</b> remove a solicitacao <b>definitivamente</b>.<br>"
            "Normalmente e restrito ao perfil <b>Administrador</b> e pede <b>confirmacao</b>."
        ),
    },
    {
        "title": "Anexos",
        "keywords": ["anexo", "arquivo", "upload", "baixar", "download", "pdf", "png", "jpg", "doc", "xlsx"],
        "answer": (
            "Voce pode <b>anexar arquivos</b> na solicitacao e depois <b>baixar</b>.<br>"
            "Se o anexo nao aparecer, verifique se foi <b>salvo corretamente</b> e se o <b>formato e permitido</b>."
        ),
    },
    {
        "title": "GPS e mapa",
        "keywords": ["gps", "latitude", "longitude", "coordenadas", "mapa", "google maps", "consulta", "localizacao", "geolocalizacao", "mapas"],
        "answer": (
            "<b>Latitude e Longitude</b> e utilizado para <b>localizar o endereco com precisao</b>.<br>"
            "Quando preenchidas corretamente, o botao de <b>mapa</b> abre o local no <b>Google Maps</b>.<br>"
            "O sistema possui mapas de calor para melhorar a visualizacao das areas com mais solicitacoes.<br>"
            "O campo de Geolocalizacao permite consultar coordenadas a partir do endereco e tracar rotas."
        ),
    },
    {
        "title": "Exportar Excel do painel",
        "keywords": ["exportar", "excel", "xlsx", "planilha", "baixar excel"],
        "answer": (
            "Existe <b>exportacao para Excel</b> a partir do painel.<br>"
            "Os <b>filtros aplicados</b> (<b>status</b>, <b>unidade</b>, <b>regiao</b>) refletem no <b>arquivo exportado</b>."
        ),
    },
    {
        "title": "Agenda",
        "keywords": ["agenda", "calendario", "eventos", "mes", "ano", "exportar agenda"],
        "answer": (
            "A <b>Agenda</b> mostra <b>agendamentos</b> por periodo.<br>"
            "Voce pode <b>filtrar</b> e <b>exportar</b> quando disponivel."
            "Voce pode <b>tracar as rotas</b> quando houver mais de 2 solicitacoes aprovadas naquele dia."
        ),
    },
    {
        "title": "Relatorios",
        "keywords": ["relatorio", "relatorios", "pdf", "grafico", "totais", "mes", "ano"],
        "answer": (
            "<b>Relatorios</b> permitem filtrar por <b>mes</b>, <b>ano</b> e <b>unidade</b>.<br>"
            "Podem ser exportados em <b>PDF</b> e <b>Excel</b>."
        ),
    },
    {
        "title": "Pilotos",
        "keywords": ["piloto", "pilotos", "copiloto", "auxiliar de piloto", "auxiliar"],
        "answer": (
            "<b>Pilotos</b> sao os responsaveis pela <b>execucao das solicitacoes</b>.<br>"
            "O <b>Cadastro de pilotos</b> permite:<br>"
            "- <b>Cadastrar</b><br>"
            "- <b>Editar</b><br>"
            "- <b>Excluir</b><br>"
            "- <b>Listar</b><br>"
            "Cada solicitacao pode ter um <b>piloto associado</b>.<br>"
            "As <b>UVIS</b> veem os pilotos da <b>sua regiao</b>."
        ),
    },
    {
        "title": "Gestao de UVIS",
        "keywords": ["uvis", "cadastrar uvis", "lista uvis", "gerenciar uvis", "unidade", "login", "senha", "codigo setor", "regiao"],
        "answer": (
            "<b>Gestao de UVIS</b> inclui:<br>"
            "- <b>Listar UVIS</b><br>"
            "- <b>Cadastrar UVIS</b><br>"
            "- <b>Editar UVIS</b> (inclusive <b>redefinir senha</b>)<br>"
            "<b>Atencao:</b> o <b>login nao pode se repetir</b>."
        ),
    },
]


AGRO_ADMIN_FAQ = [
    {
        "title": "Fluxo completo do Agro",
        "keywords": [
            "fluxo completo",
            "fluxo completo do agro",
            "passo a passo",
            "processo",
            "inicio",
            "fim",
            "etapas",
        ],
        "answer": (
            "**Fluxo principal do Agro**:\n"
            "1. Cadastrar o cliente.\n"
            "2. Criar o orcamento.\n"
            "3. Preencher a RD de mapeamento quando o servico exigir.\n"
            "4. Montar o contrato pelo sistema.\n"
            "5. Liberar para o piloto ou para a operacao.\n"
            "6. Acompanhar o preenchimento da OS.\n"
            "7. Gerar ou consultar o relatorio final.\n"
            "8. Seguir com recebimentos, contas e caixa quando houver financeiro."
        ),
    },
    {
        "title": "Cadastrar cliente",
        "keywords": ["cliente", "cadastrar cliente", "novo cliente", "cadastro cliente"],
        "answer": (
            "Para **cadastrar um cliente**:\n"
            "- Abra **Clientes** no painel Agro.\n"
            "- Clique em **Novo Cliente**.\n"
            "- Preencha os dados principais, endereco e documento.\n"
            "- Salve o cadastro.\n\n"
            "Depois disso, o cliente ja pode ser usado no orcamento."
        ),
    },
    {
        "title": "Criar orcamento",
        "keywords": ["orcamento", "criar orcamento", "novo orcamento", "proposta", "valor"],
        "answer": (
            "Para **criar um orcamento**:\n"
            "- Acesse **Orcamentos**.\n"
            "- Clique em **Novo Orcamento**.\n"
            "- Vincule o cliente.\n"
            "- Informe propriedade, servico, cultura, area e valores.\n"
            "- Salve e gere o PDF se precisar enviar ao cliente.\n\n"
            "O proximo passo normalmente e seguir para RD de mapeamento ou contrato."
        ),
    },
    {
        "title": "Quando usar RD de mapeamento",
        "keywords": ["rd", "rd de mapeamento", "mapeamento", "quando preencher rd", "template mapeamento"],
        "answer": (
            "A **RD de mapeamento** entra quando o fluxo precisa de validacao operacional antes da execucao.\n"
            "Ela ajuda a registrar informacoes tecnicas da area, cultura, acesso e detalhes do servico.\n\n"
            "No painel, voce encontra isso em **Listar Mapeamentos**."
        ),
    },
    {
        "title": "Montar contrato",
        "keywords": ["contrato", "montar contrato", "gerar contrato", "contrato via sistema"],
        "answer": (
            "Para **montar o contrato**:\n"
            "- Abra o orcamento desejado.\n"
            "- Siga para a etapa de **Contrato**.\n"
            "- Revise dados comerciais, propriedade, culturas e elaboracao.\n"
            "- Salve o contrato.\n"
            "- Gere o PDF quando precisar formalizar.\n\n"
            "Contrato aprovado e a base para seguir para a operacao."
        ),
    },
    {
        "title": "Enviar para o piloto",
        "keywords": ["piloto", "enviar para o piloto", "liberar para operacao", "operacao", "mandar para piloto"],
        "answer": (
            "Depois que o contrato estiver pronto, a operacao passa a acompanhar o item em **Contratos** e **Operacional**.\n"
            "Quando ainda nao existe OS, o contrato fica aguardando criacao pela equipe ou piloto.\n\n"
            "A ideia e: contrato pronto -> criar OS -> piloto preencher e executar."
        ),
    },
    {
        "title": "Acompanhar OS",
        "keywords": ["os", "ordem de servico", "acompanhar os", "preencher os", "status os"],
        "answer": (
            "Em **Ordens de Servico**, voce acompanha as OS cadastradas e o andamento operacional.\n"
            "Ali voce consegue ver se a OS ja existe, se ainda esta em preenchimento e se ja foi concluida.\n\n"
            "Se o contrato estiver aprovado e sem OS, o proximo passo e gerar a OS."
        ),
    },
    {
        "title": "Relatorio final",
        "keywords": ["relatorio final", "pdf final", "relatorio", "resultado final", "os relatorio"],
        "answer": (
            "O **relatorio final** fica vinculado a OS.\n"
            "Quando a execucao estiver completa, voce pode consultar ou gerar o PDF do relatorio final da ordem.\n\n"
            "Na pratica, o relatorio fecha o ciclo operacional e ajuda no financeiro e no historico do atendimento."
        ),
    },
    {
        "title": "Financeiro do Agro",
        "keywords": [
            "financeiro",
            "financeiro do agro",
            "como funciona o financeiro",
            "como funciona o financeiro do agro",
            "contas",
            "receber",
            "pagar",
            "caixa",
            "bancos",
            "recebimentos",
        ],
        "answer": (
            "No **Financeiro Agro** voce encontra:\n"
            "- **Contas** para visao central.\n"
            "- **Recebimentos** ligados aos contratos e OS.\n"
            "- **Entradas** e **Saidas** manuais.\n"
            "- **Bancos** e conciliacao.\n"
            "- **Caixa Diario** para abertura e fechamento.\n\n"
            "Use essa etapa depois que o fluxo comercial e operacional estiver encaminhado."
        ),
    },
    {
        "title": "Equipes, pilotos e equipamentos",
        "keywords": ["equipe", "equipes", "pilotos", "equipamentos", "cadastros operacionais", "estrutura operacional"],
        "answer": (
            "O bloco operacional do Agro e dividido assim:\n"
            "- **Equipes**: agrupam a operacao.\n"
            "- **Pilotos**: executam ou acompanham as demandas em campo.\n"
            "- **Equipamentos**: drones e recursos vinculados a equipe.\n\n"
            "Esses cadastros ajudam na criacao correta da OS e no direcionamento da operacao."
        ),
    },
]


AGRO_PILOTO_FAQ = [
    {
        "title": "Fluxo do piloto",
        "keywords": ["fluxo", "passo a passo", "como funciona", "piloto", "inicio"],
        "answer": (
            "**Fluxo do piloto Agro**:\n"
            "1. Ver RDs de mapeamento pendentes.\n"
            "2. Preencher a RD quando houver demanda.\n"
            "3. Ver contratos aprovados aguardando OS.\n"
            "4. Criar ou continuar a OS.\n"
            "5. Preencher os dados da execucao.\n"
            "6. Finalizar corretamente para liberar o relatorio final."
        ),
    },
    {
        "title": "Minhas OS",
        "keywords": ["minhas os", "os", "ordem de servico", "ver os", "continuar os"],
        "answer": (
            "Em **Minhas OS**, voce encontra as ordens de servico da sua operacao.\n"
            "Use essa tela para:\n"
            "- continuar uma OS ja aberta\n"
            "- revisar dados antes da execucao\n"
            "- concluir o preenchimento quando o servico terminar"
        ),
    },
    {
        "title": "RD de mapeamento",
        "keywords": ["rd", "mapeamento", "abrir rd", "preencher rd", "meus mapeamentos"],
        "answer": (
            "Quando houver **RD de mapeamento pendente**, ela aparece como prioridade no painel do piloto.\n"
            "Abra a RD, preencha as informacoes pedidas e salve.\n\n"
            "Esse passo normalmente acontece antes da OS quando o servico precisa de mapeamento."
        ),
    },
    {
        "title": "Criar OS",
        "keywords": ["criar os", "gerar os", "contrato aguardando os", "nova os"],
        "answer": (
            "Se o contrato ja estiver aprovado e ainda nao tiver OS, use **Criar OS**.\n"
            "A OS organiza a execucao do servico e vira o documento principal do campo.\n\n"
            "Depois de criada, voce pode continuar o preenchimento conforme a operacao avanca."
        ),
    },
    {
        "title": "Preencher OS",
        "keywords": ["preencher os", "campos da os", "editar os", "continuar os", "formulario os"],
        "answer": (
            "Ao **preencher a OS**, revise os dados da propriedade, equipe, piloto, equipamentos e informacoes da aplicacao.\n"
            "A regra pratica e simples: quanto mais completa a OS, melhor fica o relatorio final e o historico da operacao."
        ),
    },
    {
        "title": "Checklist antes de executar",
        "keywords": ["checklist", "antes de executar", "antes da operacao", "campo", "pre operacao"],
        "answer": (
            "**Checklist rapido antes da operacao**:\n"
            "[] Conferir se esta na OS correta.\n"
            "[] Revisar propriedade, cidade e cultura.\n"
            "[] Verificar equipe e equipamento.\n"
            "[] Confirmar se ha RD pendente antes da execucao.\n"
            "[] Preencher os dados necessarios para nao deixar a OS incompleta."
        ),
    },
    {
        "title": "Finalizar servico",
        "keywords": ["finalizar", "concluir", "encerrar os", "finalizar servico", "concluir os"],
        "answer": (
            "Para **finalizar corretamente**:\n"
            "- conclua o preenchimento da OS\n"
            "- revise os dados operacionais\n"
            "- confirme que nao ficou campo essencial em branco\n\n"
            "Quando a OS fica redonda, o administrativo consegue puxar o relatorio final com muito menos retrabalho."
        ),
    },
    {
        "title": "Relatorio final para o administrativo",
        "keywords": ["relatorio final", "administrativo", "pdf", "entregar relatorio", "resultado final"],
        "answer": (
            "O **relatorio final** sai da OS preenchida.\n"
            "Entao o seu papel e deixar a ordem completa e coerente.\n\n"
            "Depois disso, o administrativo consulta ou gera o PDF final do servico."
        ),
    },
    {
        "title": "Equipamentos da equipe",
        "keywords": ["equipamento", "equipamentos", "drone", "equipe", "recurso"],
        "answer": (
            "No painel do piloto existe uma area com os **equipamentos vinculados a sua equipe**.\n"
            "Ela ajuda a confirmar identificacao, modelo, funcao e status antes da execucao."
        ),
    },
]


def normalize_chatbot_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def clean_admin_answer(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def can_access_admin_chatbot(user) -> bool:
    return getattr(user, "tipo_usuario", None) in ADMIN_CHATBOT_TYPES


def can_access_agro_admin_chatbot(user) -> bool:
    return getattr(user, "tipo_usuario", None) in AGRO_ADMIN_CHATBOT_TYPES


def can_access_agro_piloto_chatbot(user) -> bool:
    return getattr(user, "tipo_usuario", None) in AGRO_PILOTO_CHATBOT_TYPES


def _match_best_faq(message: str, faq_items: list[dict]):
    normalized_message = normalize_chatbot_text(message)
    best_item = None
    best_score = 0

    for item in faq_items:
        score = 0
        for keyword in item["keywords"]:
            if keyword in normalized_message:
                score += 1
        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


def _build_faq_response(
    message: str,
    *,
    faq_items: list[dict],
    empty_message: str,
    fallback_message: str,
    suggestions: list[str],
    sanitizer=None,
):
    msg = (message or "").strip()
    if not msg:
        return {"answer": empty_message}, 400

    best_item, best_score = _match_best_faq(msg, faq_items)
    if not best_item or best_score == 0:
        return {
            "answer": fallback_message + "\n- " + "\n- ".join(suggestions),
            "matched": None,
            "confidence": 0,
        }, 200

    answer = best_item["answer"]
    if sanitizer is not None:
        answer = sanitizer(answer)

    return {
        "answer": answer,
        "matched": best_item["title"],
        "confidence": best_score,
    }, 200


def build_uvis_chatbot_response(message: str):
    return _build_faq_response(
        message,
        faq_items=UVIS_FAQ,
        empty_message="Escreva sua duvida (ex.: o que significa Em Analise?).",
        fallback_message="Nao encontrei essa duvida diretamente no manual.\n\nTenta uma dessas perguntas:",
        suggestions=[
            "O que significa Pendente/Em Analise/Aprovado/Aprovado com Recomendacoes/Negado?",
            "Quais campos sao obrigatorios na Nova Solicitacao?",
            "O que fazer se o CEP nao encontrar?",
            "Qual o checklist antes de enviar?",
            "Como funciona Notificacoes e Agenda?",
        ],
    )


def build_admin_chatbot_response(message: str):
    return _build_faq_response(
        message,
        faq_items=ADMIN_FAQ,
        empty_message="Digite sua duvida (ex.: como exportar Excel?).",
        fallback_message="Nao achei essa duvida direto no guia.\n\nSugestoes:",
        suggestions=[
            "Como filtrar por status/unidade/regiao?",
            "Como salvar decisao (status/protocolo/justificativa)?",
            "Como editar completo?",
            "Como exportar Excel?",
            "Como funciona Agenda/Relatorios?",
            "Como gerenciar UVIS?",
        ],
        sanitizer=clean_admin_answer,
    )


def build_agro_admin_chatbot_response(message: str):
    return _build_faq_response(
        message,
        faq_items=AGRO_ADMIN_FAQ,
        empty_message="Digite sua duvida do Agro (ex.: como criar um orcamento?).",
        fallback_message="Nao encontrei essa duvida no guia do Agro.\n\nTente uma destas:",
        suggestions=[
            "Qual e o fluxo completo do Agro?",
            "Como cadastrar um cliente?",
            "Como criar um orcamento?",
            "Quando usar RD de mapeamento?",
            "Como montar o contrato pelo sistema?",
            "Como acompanhar a OS e o relatorio final?",
        ],
    )


def build_agro_piloto_chatbot_response(message: str):
    return _build_faq_response(
        message,
        faq_items=AGRO_PILOTO_FAQ,
        empty_message="Digite sua duvida operacional (ex.: como preencher uma OS?).",
        fallback_message="Nao achei essa duvida no guia do piloto Agro.\n\nExperimente perguntar:",
        suggestions=[
            "Qual e o fluxo do piloto Agro?",
            "Como preencher uma RD de mapeamento?",
            "Como criar ou continuar uma OS?",
            "Qual o checklist antes da operacao?",
            "Como finalizar o servico corretamente?",
            "Como o administrativo gera o relatorio final?",
        ],
    )
