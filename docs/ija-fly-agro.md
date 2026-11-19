# IJA Fly no Agro

O sistema usa duas identidades sobre a mesma infraestrutura de IA e consultas:
Azul nas áreas gerais e IJA Fly no Agro. O contexto é selecionado pelo servidor;
o nome da identidade não concede permissões.

- Rotas `/agro/` e canais Agro usam IJA Fly; pilotos Agro mantêm essa identidade também no chat completo.
- O atalho do chat completo mantém o contexto via `/azul?area=agro`.
- Nome, apresentação, mascote, cores, rótulos acessíveis e guias acompanham a área.
- O IJA Fly mantém as ferramentas existentes de pendências, buscas, períodos e detalhes/conferência de OS e RD. Consultas continuam usando as permissões e vínculos atuais.
- O histórico visual de Azul e IJA Fly fica separado na aba, preservando a vinculação existente à sessão e ao escopo de acesso. Ao mudar de usuário ou de permissões, ambos são descartados.
- O guia e o treinamento do IJA Fly priorizam módulos Agro autorizados. O PDF já publicado continua disponível no mesmo endereço.
- Voz e transcrição continuam compartilhando as regras de acesso, cotas e consentimento. No IJA Fly a chamada começa escutando, sem reproduzir a gravação de apresentação da Azul.

Não há migração de banco, novo usuário de serviço, nova chave de IA nem duplicação de registros. As rotas técnicas `/api/azul/` são mantidas por compatibilidade.

## Prospecção regional por busca web

No chat Agro, use **Buscar parceiros na região**. A consulta padrão pesquisa
cooperativas e lojas agropecuárias para café, milho, soja e pastagem, considerando
pulverização, monitoramento, mapeamento, geoprocessamento e distribuição de sólidos.
Itajubá/MG é o centro de referência, com raio solicitado de 200 km em linha reta.
Quando a chave Google Maps de servidor está disponível, o sistema geocodifica
as referências municipais e calcula a distância em linha reta até Itajubá. São
estimativas entre municípios, não distâncias rodoviárias nem coordenadas da loja;
o endereço da unidade ainda precisa de confirmação. Referências além de 200 km
são sinalizadas para expansão. Falhas de geocodificação não descartam candidatos
com fontes. A lista não comprova cobertura geométrica completa ou demanda contratada.

Três frentes web independentes executam em paralelo: municípios próximos,
cafeicultura e parceiros de grãos/pastagem. Cada frente busca até quatro candidatos
e verifica contatos em fontes públicas. Uma etapa final consolida até 12 unidades,
elimina duplicações por nome/cidade e organiza a abordagem comercial. Não há
quantidade mínima garantida: depende de fontes verificáveis. Números sem respaldo
nos relatórios citados e fontes fora da pesquisa são descartados da consolidação.

O painel DEV tem modelo e limite de saída exclusivos da prospecção:
`prospecting_search_model` (pesquisa: `gpt-6.1-terra`), `prospecting_model`
(consolidação: `gpt-6.1-sol`) e `max_output_prospecting` (6.000 tokens
por etapa). As demais conversas mantêm seus modelos. A pesquisa usa raciocínio
baixo e até três chamadas web por frente. São até três chamadas de pesquisa e
uma de consolidação por pedido; todas usam reserva e medição de custo existentes.
As reservas são feitas na requisição original antes de iniciar os trabalhadores,
que não recebem contexto Flask, banco, sessão ou ferramentas privadas.

Requer acesso a fontes Agro, chave de IA, geração habilitada e `web_search_enabled`
(na configuração inicial, `PORTAL_CHATBOT_WEB_SEARCH_ENABLED`). A busca é do
provedor de IA, enquanto Google Maps é usado somente para estimar distâncias municipais. Os limites financeiros
e diários continuam valendo. As fontes de saúde continuam restritas aos domínios
já autorizados; a prospecção aceita fontes comerciais HTTPS verificadas na pesquisa.

Uma frente sem resposta não descarta resultados das outras. Se a consolidação
falhar ou não puder iniciar por limite, o chat devolve as pesquisas com fontes e
avisa que a lista está parcial e pode conter duplicatas. Sem nenhuma pesquisa com
fonte válida, informa o erro. Os tempos de espera são 50 segundos por pesquisa em
paralelo, 40 segundos na consolidação e 130 segundos no chat IJA Fly, incluindo a consulta geográfica com timeout de quatro
segundos por município (até seis em paralelo).

Continuações como “mais parceiros de café”, “aprofunde os primeiros” e “priorize os
mais próximos de Itajubá” reutilizam pedidos públicos anteriores. Somente os nomes
e municípios da última lista são guardados na sessão assinada, por até uma hora,
vinculados ao login/escopo. Respostas privadas de OS/RD nunca são encaminhadas à
pesquisa. As fontes da resposta permanecem no histórico visual da aba ao recarregar.
Não há cadastro automático de leads, envio de mensagens ou monitoramento periódico.
