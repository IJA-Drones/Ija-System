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

No chat Agro, use **Buscar parceiros na região** ou peça “Busque cooperativas e
lojas agropecuárias perto de Itajubá”. A pesquisa sob demanda usa a busca web do
provedor de IA (não uma integração direta com Google Maps), com padrão de 200 km
em linha reta e foco em café, milho, soja e pastagem. Os serviços considerados são
pulverização, monitoramento, mapeamento, geoprocessamento e distribuição de sólidos.

A resposta solicita até três candidatos, contatos comerciais publicados, culturas
comprovadas, fontes clicáveis e sugestões de abordagem. Potencial parceria não é
demanda confirmada. Sem evidência geográfica, a unidade deve aparecer como candidata
com distância a confirmar; esta versão não implementa geocodificação nem filtragem
geométrica automática. Não há garantia de cobertura completa da região.

Requer acesso a fontes Agro, chave de IA, geração habilitada e `web_search_enabled`
(na configuração inicial, `PORTAL_CHATBOT_WEB_SEARCH_ENABLED`). Usa o modelo interno,
a contabilização de custos e os limites existentes, com até duas chamadas web por
consulta. Resultados sem busca concluída ou sem citações são recusados. As páginas
comerciais são exibidas como fontes HTTPS; a restrição de domínios de saúde continua
valendo para consultas de saúde.

A consulta pública não recebe resultados privados de OS/RD nem ferramentas de
cadastro. Não envia mensagens, não salva leads e não executa monitoramento periódico.
Histórico de continuação inclui somente pedidos do usuário sobre prospecção.

A prospecção usa raciocínio baixo e uma primeira rodada de até 450 palavras para
não consumir todo o limite de saída antes de entregar resultados. O limite de
tokens configurado continua sendo respeitado. O provedor tem até 60 segundos e
o chat IJA Fly espera até 75 segundos; erros aparecem como “Não concluído”,
não como orientação do guia local. Respostas incompletas continuam recusadas,
com diagnóstico de status/motivo nos logs, sem gravar perguntas ou contatos.
