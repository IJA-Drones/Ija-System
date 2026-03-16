import re
import unicodedata


ADMIN_CHATBOT_TYPES = {"admin", "operario", "visualizar"}


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
        "keywords": ["dashboard", "minhas solicitacoes", "tela inicial", "filtro", "detalhes", "nova solicitacao", "editar", "equipes", "informacoes", "modal", "equipe"],
        "answer": (
            "Na tela **Minhas Solicitacoes** voce encontra:\n"
            "- Botao **Nova Solicitacao** (abre o formulario)\n"
            "- **Filtro por status** (Pendente, Em Analise, Aprovado, Aprovado com Recomendacoes, Negado)\n"
            "- **Tabela** com data/hora, localizacao e foco\n"
            "- Botao **Detalhes** (abre um modal com informacoes completas)\n"
            "- Botao **Adicionar/Editar Equipes** (abre um modal para inserir a equipe responsavel)\n"
            "- Botao **Editar solicitacao** (abre para editar a solicitacao apenas quando esta pendente ou negada.)\n"
        ),
    },
    {
        "title": "Campos obrigatorios ao criar uma solicitacao",
        "keywords": ["novo", "nova solicitacao", "cadastro", "campos", "obrigatorio", "cep", "numero", "tipo de visita", "altura", "foco"],
        "answer": (
            "No cadastro de uma nova solicitacao, atencao aos campos:\n"
            "- **Data** e **Hora** (obrigatorios)\n"
            "- **CEP** (8 digitos) para preencher endereco automatico\n"
            "- **Logradouro** (confirmar) e **Numero** (preencher manualmente)\n"
            "- **Tipo de visita** (Monitoramento / Aedes / Culex)\n"
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
            "[] Tipo de visita e altura do voo selecionados\n"
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
        "keywords": ["acesso", "perfil", "permissao", "permissoes", "admin", "operario", "visualizar", "quem pode"],
        "answer": (
            "<b>Perfis do painel:</b><br>"
            "- <b>Administrador</b>: acesso total (<b>editar</b>, <b>excluir</b>, <b>gerenciar UVIS</b>, <b>relatorios</b> e <b>agenda</b>).<br>"
            "- <b>Operario</b>: consegue <b>salvar decisoes</b> (<b>status</b>, <b>protocolo</b> e <b>justificativa</b>).<br>"
            "- <b>Visualizar</b>: <b>apenas leitura</b>.<br>"
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
            "Se o perfil for <b>Visualizar</b>, fica em <b>somente leitura</b>."
        ),
    },
    {
        "title": "Editar completo",
        "keywords": ["editar", "editar completo", "corrigir", "alterar", "data", "hora", "endereco", "agendamento"],
        "answer": (
            "<b>Editar completo</b> serve para <b>corrigir todos os dados</b> do pedido:<br>"
            "<b>Data/Hora</b>, <b>Endereco</b>, <b>Foco</b>, <b>Tipo de visita</b>, <b>Altura</b> e <b>Observacoes</b>.<br>"
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


def build_uvis_chatbot_response(message: str):
    msg = (message or "").strip()
    if not msg:
        return {"answer": "Escreva sua duvida (ex.: o que significa Em Analise?)."}, 400

    best_item, best_score = _match_best_faq(msg, UVIS_FAQ)

    if not best_item or best_score == 0:
        suggestions = [
            "• O que significa Pendente/Em Analise/Aprovado/Aprovado com Recomendacoes/Negado?",
            "• Quais campos sao obrigatorios na Nova Solicitacao?",
            "• O que fazer se o CEP nao encontrar?",
            "• Qual o checklist antes de enviar?",
            "• Como funciona Notificacoes e Agenda?",
        ]
        return {
            "answer": "Nao encontrei essa duvida diretamente no manual.\n\nTenta uma dessas perguntas:\n" + "\n".join(suggestions),
            "matched": None,
            "confidence": 0,
        }, 200

    return {
        "answer": best_item["answer"],
        "matched": best_item["title"],
        "confidence": best_score,
    }, 200


def build_admin_chatbot_response(message: str):
    msg = (message or "").strip()
    if not msg:
        return {"answer": "Digite sua duvida (ex.: como exportar Excel?)."}, 400

    best_item, best_score = _match_best_faq(msg, ADMIN_FAQ)

    if not best_item or best_score == 0:
        suggestions = [
            "Como filtrar por status/unidade/regiao?",
            "Como salvar decisao (status/protocolo/justificativa)?",
            "Como editar completo?",
            "Como exportar Excel?",
            "Como funciona Agenda/Relatorios?",
            "Como gerenciar UVIS?",
        ]
        return {
            "answer": "Nao achei essa duvida direto no guia.\n\nSugestoes:\n- " + "\n- ".join(suggestions),
            "matched": None,
            "confidence": 0,
        }, 200

    return {
        "answer": clean_admin_answer(best_item["answer"]),
        "matched": best_item["title"],
        "confidence": best_score,
    }, 200
