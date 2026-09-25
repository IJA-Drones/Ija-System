# Guia de execução das novas demandas de vigilância

**Sistema:** IJA System  
**Documento relacionado:** [Relatório de Análise de Aderência e Novas Demandas](relatorio-novas-demandas-vigilancia-epidemiologica.md)
**Objetivo:** orientar a equipe sobre o que fazer primeiro, como decompor o trabalho e quais evidências devem existir para considerar cada etapa concluída.

> Este é um guia de execução. Ele não altera o código e não transforma uma recomendação em requisito contratual. As decisões sobre fontes, indicadores, conteúdo de saúde, privacidade, SLA e aceite precisam ser aprovadas pelo contratante e pela vigilância.

## 1. Ordem recomendada em uma página

1. **Fechar o escopo e as fontes.** Obter o termo completo, os anexos, os layouts reais de focal, LIRAa e SINAN, os sistemas de origem, os períodos, os volumes, os responsáveis e os critérios de aceite.
2. **Preservar uma linha de base.** Registrar a revisão auditada, executar a suíte existente, inventariar ambientes e criar uma matriz requisito–evidência–responsável. Nenhuma entrega futura deve depender de memória da equipe.
3. **Proteger o terreno.** Corrigir isolamento entre entes, autorização por objeto, CSRF, segredos, TLS, uploads e backup antes de colocar dados de saúde ou relatos públicos no sistema.
4. **Definir o modelo canônico.** Separar imóvel, inspeção, depósito, levantamento, caso, notificação oficial, relato cidadão, pendência e ordem de serviço. Não usar `Solicitacao` ou `OrdemServico` como substituto semântico desses objetos.
5. **Construir a fundação de dados.** Implementar contratos versionados, staging, quarentena, reconciliação, auditoria, outbox e worker durável. O fluxo deve sobreviver a reinício, reenvio e falha de fornecedor.
6. **Entregar uma fatia vertical.** Com uma amostra aprovada (ou fixture sintético explicitamente marcado), executar extração/importação → validação → revisão → carga → consulta → indicador → relatório/mapa. Só depois ampliar para os demais processos.
7. **Adicionar as fontes oficiais.** Implementar focal e LIRAa para alimentar a camada entomológica; implementar SINAN como domínio epidemiológico separado, com regras de atualização e geocodificação revisável.
8. **Integrar território e operação.** Calcular IIP e demais indicadores aprovados, cruzar camadas, tratar pendências e produzir o mesmo resultado em tabela, gráfico, mapa e exportação.
9. **Abrir a jornada cidadã.** Entregar IEC mobile, relato com triagem, protocolo, alerta para a gestão e devolutiva. O cidadão, a equipe de campo e o gestor devem ter permissões e dados diferentes.
10. **Só então fechar IA, redes sociais e transição.** O assistente deve responder com conteúdo aprovado e fonte rastreável; canais sociais devem ter contas homologadas, contingência e monitoramento. A virada deve ocorrer após ensaios de migração, coexistência e restauração.

Esta ordem pode ter trabalho paralelo. O que não deve ser paralelizado é a dependência: não calcular indicadores antes de definir o dado que os alimenta; não liberar dados sensíveis antes de fechar acesso e recuperação; não prometer conector antes de confirmar a interface da origem.

## 1.1 Se você ainda não possui essas informações

Isso não impede o início do projeto. Significa que a primeira entrega é **descoberta e preparação**, e não o conector definitivo. Nunca preencha uma lacuna com um palpite e depois apresente esse palpite como regra oficial.

Use quatro estados para tudo que ainda não está confirmado:

| Estado | Como tratar |
|---|---|
| Confirmado | Há documento, fonte ou aprovação identificável. Pode virar regra de produção. |
| Provisório | Hipótese de trabalho usada somente em protótipo ou fixture sintética. Tem dono e data de revisão. |
| Pendente | A informação é necessária, mas ainda não foi obtida. Não deve bloquear tarefas independentes. |
| Bloqueante | Sem a informação não é possível homologar ou liberar a etapa. Deve ter responsável de escalonamento. |

Enquanto as fontes oficiais não chegam, faça o seguinte:

1. **Congele o que já é conhecido:** requisitos recebidos, código auditado, capacidades atuais, falhas reproduzidas e limites da análise.
2. **Abra um registro de pendências:** item, pergunta, responsável externo, evidência esperada, impacto e próxima ação. A ausência de resposta também precisa ficar documentada.
3. **Escreva contratos provisórios:** nomes dos campos, tipos, estados, erros, chaves e exemplos. Marque cada campo como `provisorio`; não acople a implementação a nomes inventados de arquivo ou endpoint.
4. **Crie fixtures sintéticas:** pequenos arquivos que exercitem linha válida, duplicidade, correção, cancelamento, coordenada inválida, endereço ambíguo e dado ausente. Não use dados pessoais reais para preencher a lacuna.
5. **Implemente somente fundações independentes:** autorização por objeto, segregação de domínios, staging, quarentena, reconciliação, auditoria, outbox, worker, observabilidade e testes. Essas peças não dependem do layout final.
6. **Adie o aceite oficial:** um protótipo pode demonstrar o fluxo técnico, mas deve ser identificado como “não homologado”. O status contratual só muda depois de amostra, regra e aprovação da fonte competente.
7. **Envie um pacote objetivo de solicitação:** uma lista curta de perguntas e o formato de resposta esperado reduz a chance de receber apenas uma explicação informal que não possa ser implementada.

### Pacote mínimo para solicitar ao contratante ou à SMS/MS

Solicite, por processo, os itens abaixo:

- nome do sistema e versão;
- responsável técnico e responsável de negócio;
- método de acesso e ambiente de homologação;
- exemplo anonimizado de arquivo/API e dicionário de dados;
- códigos, tabelas de domínio e identificadores estáveis;
- periodicidade, janela, volume e histórico;
- regra para inclusão, atualização, correção e cancelamento;
- campos pessoais, finalidade e perfil que pode acessá-los;
- exemplo do resultado esperado para um pequeno conjunto;
- critérios de aceite e contato para tirar dúvidas.

### O que fazer nesta semana sem nenhuma fonte

1. Criar a matriz de requisitos e o registro de pendências.
2. Nomear quem fará as solicitações e quem aprovará as respostas.
3. Registrar a linha de base do sistema e executar os testes já existentes.
4. Preparar as fixtures sintéticas e o contrato provisório da primeira fatia.
5. Planejar as correções de isolamento, CSRF, segredos, TLS e backup.
6. Desenhar o modelo conceitual de imóvel, inspeção, depósito, levantamento, caso, relato e lote, sem escolher ainda os nomes do arquivo oficial.

O resultado dessa semana não é “o requisito atendido”. É um projeto preparado para receber a informação correta sem retrabalho e sem criar evidência falsa.

## 1.2 O seu caso: fonte oficial operacional já existe

Pelo contexto informado, o fluxo atual é:

`Prefeitura envia endereços → IJA agenda e executa pulverização → IJA devolve OS e relatórios`

Esse é um fluxo oficial de operação da Prefeitura e deve ser aproveitado imediatamente. Ele fornece a primeira fonte real para a fatia vertical. A ausência de um layout SINAN ou LIRAa não invalida esse fluxo; apenas mostra que ele cobre uma camada operacional diferente da camada epidemiológica.

### O que documentar desse fluxo agora

1. **Entrada:** como a Prefeitura envia os endereços (tela, planilha, e-mail, API, arquivo ou outro), quem envia, em que periodicidade e qual campo identifica o pedido.
2. **Recebimento:** quando o endereço passa a ser uma solicitação válida, como duplicidade e endereço incompleto são tratados e qual ente é responsável pelo dado.
3. **Execução:** como a solicitação vira agenda, equipe, ordem de serviço, pulverização, tratamento, mídia e motivo de não realização.
4. **Retorno:** quais campos da OS são enviados de volta, em que formato, para quem, com qual status e como uma correção posterior é comunicada.
5. **Relatórios:** quais filtros, totais, períodos, áreas e evidências a Prefeitura recebe e qual relatório é considerado oficial.
6. **Chaves e histórico:** como relacionar o pedido original, a OS, um retorno, uma nova tentativa e o imóvel sem contar o mesmo imóvel como novo.

Se hoje o envio ocorre manualmente, isso ainda é uma operação oficial, mas não prova uma API institucional síncrona ou assíncrona. Registre o meio atual e trate a automatização como uma evolução do processo.

### O que esse fluxo já pode comprovar

- recebimento de demanda municipal;
- execução e acompanhamento de pulverização;
- geração de ordem de serviço;
- devolução de resultado e relatório;
- geolocalização operacional, fotos, vídeos e motivos de não realização, quando registrados;
- continuidade do processo operacional entre Prefeitura e IJA.

### O que ele ainda não comprova sozinho

- levantamento amostral LIRAa;
- importação de ações de tratamento focal conforme layout oficial de vigilância;
- indicadores SINAN;
- caso suspeito ou confirmado de arbovirose;
- cálculo oficial do IIP;
- área de risco epidemiológico;
- alerta originado por relato da sociedade civil;
- assistente público 24/7 em rede social.

Não transforme endereço recebido em caso de saúde, nem OS de pulverização em inspeção LIRAa. Faça os vínculos quando a regra da vigilância e a origem oficial confirmarem que eles representam o mesmo objeto.

## 2. Como um time sênior deve trabalhar

### 2.1 Papéis mínimos

| Papel | Responsabilidade de decisão |
|---|---|
| Dono do produto/contrato | Prioridade, interpretação do edital, aceite e mudança de escopo. |
| Vigilância epidemiológica/entomológica | Definição de conceitos, indicadores, positividade, risco, alertas e conteúdo. |
| Arquiteto | Limites dos domínios, contratos, segurança, integração, dados e decisões registradas. |
| Backend | Modelo, regras, APIs, jobs, auditoria e migrações. |
| Dados/geoprocessamento | Extração, qualidade, reconciliação, geometrias, indicadores e desempenho espacial. |
| Frontend/produto | Jornadas de gestão, campo e cidadão, acessibilidade e estados de falha. |
| Infraestrutura/SRE | Ambientes, segredos, fila, armazenamento, backup, restauração e observabilidade. |
| Proteção de dados | Finalidade, acesso a casos, exposição geográfica, retenção e contratos com fornecedores. |
| Responsável pelos sistemas de origem | Layout, credencial, periodicidade, chaves, correções, cancelamentos e amostras. |

Uma pessoa pode acumular papéis, mas cada decisão deve ter um nome responsável. “A equipe” não é um aprovador auditável.

### 2.2 Unidade de trabalho

Trabalhar em entregas pequenas, cada uma com uma finalidade verificável. Cada pull request deve conter:

- objetivo de negócio e requisitos cobertos;
- decisão arquitetural, se houver, em um ADR curto;
- migração de banco e impacto de compatibilidade;
- regra de acesso e tratamento de dados sensíveis;
- testes do caminho feliz, rejeição e repetição;
- observabilidade e procedimento de reversão/compensação;
- documentação da operação e evidência esperada.

Evitar uma grande reescrita ou um “módulo genérico” sem processo de negócio. O monólito Flask modular existente pode evoluir por módulos e serviços internos; separar processos em serviços independentes só deve ocorrer se houver necessidade operacional comprovada.

### 2.3 Ambientes e promoção

Manter, no mínimo, desenvolvimento, homologação e produção com configurações e dados separados. Uma promoção deve seguir:

1. revisão de código e migração;
2. testes automatizados e de contrato;
3. fixture anonimizada ou sintética reproduzível;
4. homologação da área de vigilância;
5. checklist operacional e plano de retorno;
6. janela de mudança e evidência arquivada.

O banco de produção não deve ser usado para experimentar regras. Migrações destrutivas, cargas e reprocessamentos devem ser comandos/jobs explícitos, com logs e autorização próprios, e não efeitos colaterais do startup web.

## 3. Fase 0 — escopo, evidência e linha de base

### Objetivo

Eliminar ambiguidades que mudariam o banco, o conector ou o critério de aceite.

### Como fazer

1. Criar uma planilha ou documento de rastreabilidade com as colunas: requisito, processo, fonte, público, dados pessoais, interface, periodicidade, responsável, evidência e aceite.
2. Para cada sistema SMS/MS, registrar versão, ambiente, método de acesso (API, arquivo, banco, SFTP ou outro), autenticação, janela, limite, chave de origem, atualização/cancelamento e contato técnico.
3. Obter amostras pequenas e dicionários de dados reais, preferencialmente anonimizados. Se ainda não houver acesso, criar fixture sintético com o mesmo contrato e marcar a evidência como provisória.
4. Formalizar fórmula do IIP, denominadores, estratos, periodicidade, critérios de positividade, regra de risco e definição de imóvel pendente.
5. Formalizar quem pode ver caso nominativo, localização precisa, mídia, relato cidadão e conversa com o bot.
6. Confirmar canais sociais, contas institucionais, provedores, custos, limites, política de conteúdo, transferência para atendimento humano e SLA/SLO.
7. Registrar volumes históricos, volume diário, tamanho de mídia, janela de migração, período de coexistência, RTO e RPO.

### Saída obrigatória

- matriz de rastreabilidade aprovada;
- catálogo de fontes e layouts versionados;
- amostras/fixtures com hash e origem;
- dicionário de termos e indicadores;
- lista de decisões pendentes, cada uma com responsável e prazo contratual;
- critérios de aceite por requisito.

### Critério para avançar

É possível apontar, para cada requisito, qual dado entra, qual processo acontece, quem usa, qual saída é produzida e como a fiscalização irá comprovar. Onde isso não for possível, a dependência fica explícita; não se estima prazo final como se estivesse resolvida.

## 4. Fase 1 — segurança, isolamento e recuperação

Esta fase não entrega os itens funcionais, mas torna seguro desenvolvê-los.

### Sequência técnica

1. Mapear todos os papéis, entes, regiões, UVIS, objetos e ações. Aplicar a autorização no objeto carregado, comparando o ente do usuário com o ente do recurso e exigindo permissão explícita para visão global. Ausência de vínculo deve negar por padrão, com uma permissão administrativa separada para operações globais.
2. Repetir o teste com dois entes, duas regiões, exportação, download de KML, mídia, mapa e endpoints de detalhe. Um filtro visual não substitui autorização no servidor.
3. Ativar proteção CSRF para formulários e requisições de navegador autenticadas; definir contrato separado para APIs de máquina com autenticação própria, idempotência e proteção contra replay. Tokens inseridos em templates não provam proteção do endpoint. [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
4. Tornar `SECRET_KEY` e demais segredos obrigatórios e estáveis em produção; retirar segredos dos logs; validar TLS de clientes externos; rotacionar credenciais que tenham sido expostas.
5. Fazer o backup ter estados independentes: dump criado, envio concluído, checksum conferido, retenção aplicada e restauração testada. Falha de upload deve gerar falha operacional e alerta. Garantir que banco e mídias tenham cópia consistente.
6. Definir logs estruturados com `correlation_id`, usuário/serviço, ente, objeto, ação, resultado, origem e erro. Não gravar payload clínico ou token em texto livre.
7. Colocar no CI os testes existentes e os regressivos desta fase. O workflow de watchdog não deve ser confundido com pipeline de testes.

### Evidência de saída

- relatório de testes negativos de autorização;
- verificação de CSRF/API e configuração de confiança de proxy;
- inventário de segredos sem valores;
- checksum/idade de backup e restauração em ambiente separado;
- painel de erros, duração e jobs pendentes;
- procedimento de resposta a falha e responsável de plantão.

### Critério para avançar

Um usuário de um ente não consegue inferir ou baixar objeto de outro ente; um backup falho não aparece como sucesso; uma reinicialização não apaga jobs; e a equipe consegue restaurar uma cópia dentro do RTO/RPO aprovado.

## 5. Fase 2 — fundação de dados e integração

### 5.1 Domínios e chaves

Criar um domínio de vigilância separado do operacional atual. No mínimo, distinguir:

- `ImovelVigilancia` e seu identificador estável;
- `InspecaoCampo`, `DepositoInspecionado` e resultado da inspeção;
- `Levantamento`, `Estrato` e `AmostraLiraa`;
- `Caso`, episódio, notificação oficial e status de confirmação;
- `RelatoCidadao` e seu protocolo de triagem;
- `PendenciaImovel`, tentativa e resolução;
- `AcaoControle`, ordem de serviço e evidência de execução;
- origem, lote de importação, versão de layout, erro, reconciliação e evento de integração.

OS, Google Place ID, endereço digitado e coordenada são referências ou eventos; não são, sozinhos, a identidade do imóvel ou do caso. Correção, cancelamento e retificação devem preservar histórico.

### 5.2 Pipeline de migração/importação

Implementar uma máquina de estados por lote:

`RECEBIDO → EXTRAÍDO → VALIDANDO → QUARENTENA/PRONTO → REVISADO → CARREGADO → RECONCILIADO → PUBLICADO`

Cada etapa deve registrar ator, horário, versão do contrato, contagem e erro. O fluxo recomendado é:

1. **Extrair:** salvar o arquivo texto bruto imutável, manifesto, hash, origem, período e autorização.
2. **Validar sintaxe:** encoding, colunas, tipos, tamanho, datas, coordenadas, obrigatoriedade e versão do layout.
3. **Validar semântica:** chaves, domínios, duplicidades, temporalidade, vínculo territorial e consistência entre numeradores e denominadores.
4. **Enriquecer de forma determinística:** dicionários aprovados, códigos territoriais, geocodificação revisável e atributos derivados com versão de regra.
5. **Quarentenar:** separar linhas rejeitadas, motivo, severidade e ação; nunca descartar silenciosamente.
6. **Revisar e carregar:** permitir aprovação de exceções e gravar dados normalizados sem apagar o bruto.
7. **Reconciliar:** comparar origem, aceitos, rejeitados, atualizados, inalterados e destino; explicar cada diferença.
8. **Publicar:** somente após autorização, com projeção restrita para dados nominativos e projeção agregada para mapas públicos.

O reenvio do mesmo lote deve ser seguro. Usar chave de origem e versão para decidir criar, atualizar, manter, cancelar ou encaminhar para revisão. Hash de arquivo é evidência de integridade, não regra suficiente para identificar uma atualização oficial.

### 5.3 Contratos de API e jobs

Para cada processo, definir uma operação de negócio com contrato versionado. Ela pode ter entrada síncrona e processamento assíncrono, desde que a regra seja a mesma e o estado possa ser consultado. O contrato deve informar autenticação, idempotency key, correlação, paginação, limites, erro, retentativa e versão.

Gravar o evento de domínio e o registro de outbox na mesma transação. Um worker externo publica/entrega a mensagem com retentativas limitadas, backoff, lease, dead-letter e deduplicação. O usuário deve enxergar `recebido`, `em validação`, `aguardando revisão`, `concluído` ou `falhou`, e não uma falsa resposta final. A aplicação Flask usa factory e blueprints; preservar esse limite facilita testes isolados e múltiplas configurações. [Flask Application Factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/). Para a tecnologia de fila escolhida, documentar retry e comportamento após falha; a semântica deve ser pelo menos uma vez com idempotência, não “exatamente uma vez” presumida. [Celery Tasks](https://docs.celeryq.dev/en/latest/userguide/tasks.html).

### Critério para avançar

Um lote sintético com linhas válidas, duplicadas, corrigidas, canceladas, inconsistentes e ilegíveis percorre todas as fases; o total fecha; a repetição não duplica; a interrupção e a retomada são seguras; e a autorização determina o que cada perfil pode consultar.

## 6. Fase 3 — primeira fatia vertical

Escolher um processo pequeno que exercite toda a fundação. A recomendação é usar um conjunto sintético com **tratamento focal e LIRAa**, mantendo uma versão de SINAN em paralelo quando o layout estiver disponível. A fatia deve contemplar um único ente, período e área, sem fingir que fixture é homologação oficial.

### Roteiro da fatia

1. Receber o arquivo e gerar manifesto.
2. Validar e enviar uma linha ruim para quarentena.
3. Aprovar as linhas boas e criar imóvel, inspeção, depósito/levantamento e origem.
4. Reenviar o arquivo e comprovar idempotência.
5. Calcular o indicador aprovado, incluindo denominador zero e dado indisponível.
6. Exibir o mesmo filtro em tabela, gráfico, mapa restrito e exportação.
7. Registrar auditoria, métricas, origem e versão da regra.
8. Simular falha do worker, fornecedor geográfico e geração de relatório; observar estados e recuperação.

### Definição de pronto da fatia

- regra de negócio aprovada pela vigilância;
- dados de origem rastreáveis até a saída;
- teste automatizado e cenário de homologação;
- autorização negativa entre entes;
- relatório de reconciliação sem diferença não explicada;
- operação documentada e evidência arquivada.

Essa fatia reduz risco de construir três importadores incompatíveis. Depois dela, cada nova fonte deve reutilizar o contrato e substituir apenas o adaptador, o mapeamento e as regras específicas.

## 7. Fase 4 — dados oficiais e indicadores

### Focal e LIRAa — itens I, II, III e XII

Implementar adaptadores por layout, sem colocar regras de saúde dentro da rota HTTP. Normalizar imóvel, visita, depósito, espécie, positividade, tratamento, estrato, amostra e período. O IIP deve preservar numerador, denominador, fórmula, unidade territorial, versão e fonte. Não chamar “positivo” uma simples larva visualizada sem critério aprovado.

Homologar primeiro com amostras de referência da vigilância. Comparar contagens por período, estrato e área. Testar reenvio, visita repetida, imóvel sem coordenada, mudança de endereço, inspeção cancelada e amostra fora do período.

### SINAN — itens V e VI

Confirmar o meio de exportação e o dicionário do ente antes de escrever o conector. Separar pessoa, episódio, notificação, classificação e localização. Proteger campos nominativos e usar uma camada geográfica revisável: endereço ambíguo fica pendente, e o mapa público recebe somente agregação autorizada. O Portal SINAN documenta exportações e dicionários que variam por agravo/versão; isso reforça a necessidade de confirmar a interface concreta do ente antes de prometer uma API única. [Portal SINAN – dengue](https://portalsinan.saude.gov.br/dengue) e [Perguntas frequentes](https://portalsinan.saude.gov.br/perguntas-frequentes).

### Critério para avançar

Os valores reproduzem o conjunto de referência; alterações e cancelamentos não criam duplicidade; cada valor mostra origem e data; a localização incerta é revisável; e nenhum dado nominativo aparece em camada pública ou exportação sem autorização específica.

## 8. Fase 5 — território, pendências e relatórios

1. Definir sistema de referência, precisão, validade temporal e qualidade da coordenada. Migrar latitude/longitude textuais somente após validação de faixa, finitude e origem; considerar coluna espacial indexada quando PostgreSQL/PostGIS for aprovado. [PostGIS Getting Started](https://postgis.net/documentation/getting_started/).
2. Substituir a dependência de camada de mapa retirada pelo fornecedor e remover filtros de ano fixos. Testar mapa com poucos pontos, muitos pontos, nenhum ponto, anos diferentes, entes diferentes e coordenada inválida.
3. Calcular risco com regras explicáveis e versionadas. Mostrar fatores, dados faltantes, data de atualização e responsável pela aprovação. Um alerta não deve ser uma caixa-preta.
4. Definir população de pendências, tentativa, motivo, evidência, resolução e cálculo “antes/depois”. Não contar retorno de OS como imóvel novo.
5. Reusar o mesmo objeto de filtro para tabela, gráfico, mapa e exportação; comparar totais automaticamente para evitar quatro interpretações diferentes.
6. Separar visualização operacional restrita de projeção pública agregada, com redução de precisão e revisão de reidentificação.

### Critério para avançar

Para uma área e período aprovados, a equipe obtém os mesmos totais nos quatro formatos; o risco pode ser explicado; uma pendência muda de estado com evidência; e mapas públicos não revelam caso, endereço ou mídia identificável.

## 9. Fase 6 — cidadão, alertas e IEC mobile

### Jornada mínima

`conteúdo IEC → relato → validação/antispam → protocolo → triagem → alerta → ação de gestão → devolutiva`

Implementar como fluxo próprio. O relato cidadão não é uma notificação oficial SINAN e não deve criar automaticamente um caso confirmado. Guardar proveniência, consentimento/avisos, localização com precisão proporcional, mídia original protegida e derivado público quando permitido.

O item IX pede ambiente mobile; iniciar com uma jornada web responsiva/PWA se ela atender aos dispositivos e critérios de aceite. Só assumir aplicativo nativo, lojas ou offline após decisão formal. Testar rede lenta, acessibilidade, câmera, upload interrompido, duplicidade, abuso, acompanhamento e encerramento.

Alertas devem ter regra, severidade, destinatário, prazo, ciência, escalonamento, deduplicação e canal alternativo. Compartilhamento social deve publicar apenas conteúdo público aprovado, com prévia, log e falha visível.

### Critério para avançar

Uma pessoa sem perfil interno conclui o relato em celular, recebe protocolo, a gestão recebe o alerta correto e o cidadão recebe devolutiva sem acesso a dados de terceiros. O fluxo funciona quando um fornecedor de notificação falha.

## 10. Fase 7 — assistente de IA e redes sociais

Construir o assistente depois de existir um catálogo aprovado de conteúdo e dados de unidades, doenças, prevenção e áreas de risco. A camada de resposta deve consultar fontes permitidas, citar a origem internamente, aplicar escopo por público e encaminhar para humano quando não souber ou detectar urgência.

Antes de abrir um canal:

- homologar conta institucional, webhook, limites, custos e política do provedor;
- definir quais mensagens são públicas, quais exigem autenticação e quais não podem ser respondidas automaticamente;
- testar prompt injection, conteúdo desatualizado, pergunta fora de escopo, dado pessoal, indisponibilidade e escalonamento;
- medir disponibilidade, latência, erro, abandono, transferência para humano e avaliação por amostra;
- registrar versão do conteúdo e do modelo sem guardar dados desnecessários da conversa.

IA não deve decidir diagnóstico, prioridade clínica ou ação de campo sem regra e aprovação humanas. A disponibilidade 24/7 exige worker, canal, provedor, armazenamento, monitoramento e plantão compatíveis; um processo web funcionando não comprova esse SLA.

### Critério para avançar

Perguntas de referência recebem respostas corretas e apropriadas ao público, cada uma com fonte rastreável; perguntas não cobertas têm resposta segura e encaminhamento; o canal social continua observável durante falha do provedor.

## 11. Fase 8 — migração, coexistência e virada

Não deixar a migração histórica para o fim como uma única operação. Ensaiar cada novo adaptador em cópia controlada e repetir o processo com lotes crescentes.

### Roteiro

1. Congelar versão de layout, regras e dicionários.
2. Extrair período histórico e incremental, preservando bruto e manifesto.
3. Rodar validação, quarentena e reconciliação; obter assinatura da origem.
4. Carregar em ambiente de homologação e comparar indicadores, casos, imóveis, pendências e mídias.
5. Executar coexistência: definir sistema de registro por processo, direção do intercâmbio e tratamento de alteração/cancelamento.
6. Ensaiar janela de virada, monitoramento, comunicação, suporte e plano de retorno.
7. Fazer carga final incremental, bloquear escrita conforme plano aprovado e validar smoke tests.
8. Obter aceite formal por requisito; manter o legado somente pelo período definido e com acesso controlado.

### Critério para avançar

Não há diferença sem explicação entre origem e destino; todos os macroprocessos têm dono durante a coexistência; a equipe consegue retornar ao estado anterior; e a evidência de 4.6.1 e 4.7 está arquivada.

## 12. Testes que devem existir antes do aceite

| Camada | Cenários mínimos |
|---|---|
| Unidade | Fórmulas, estados, validações, deduplicação e regras de permissão. |
| Integração | Banco, fila, outbox, storage, geocoder, notificação e provedor de IA simulados. |
| Contrato | Layout/API válido, versão incompatível, paginação, erro e mudança de campo. |
| Dados | Lote repetido, atualização, cancelamento, duplicidade, linha rejeitada e reconciliação. |
| Autorização | Dois entes, perfis sem vínculo, exportação, mídia, mapa e endpoint de detalhe. |
| Geoespacial | Faixa inválida, precisão, SRID, endereço ambíguo, área sem dados e camadas atrasadas. |
| Frontend | Celular, acessibilidade, rede lenta, upload interrompido, mapa sem pontos e filtros de ano. |
| Resiliência | Restart no meio do job, timeout, retry, dead-letter, fornecedor indisponível e restauração. |
| Segurança | CSRF, sessão, segredo ausente, upload malformado, conteúdo ativo, rate limit e logs sem token. |
| Aceite | Demonstração de cada linha da matriz contratual com evidência assinada. |

O conjunto atual de testes aprovado na auditoria é uma linha de base, não prova os cenários acima. Cada falha reproduzida deve virar teste regressivo antes ou junto da correção.

## 13. Checklist de cada entrega

- [ ] O requisito e a decisão de negócio estão citados.
- [ ] O dado tem origem, chave, versão, período e política de correção.
- [ ] O objeto está no domínio correto e não foi confundido com OS, imóvel ou caso.
- [ ] Há autorização no servidor para leitura, escrita, exportação, mídia e mapa.
- [ ] Há idempotência, estado de falha e procedimento de retentativa.
- [ ] O bruto, o normalizado e o público estão separados quando necessário.
- [ ] A migração é compatível com a versão anterior e tem plano de retorno.
- [ ] Existem testes positivos, negativos, repetição e falha de dependência.
- [ ] Métricas, logs e alertas permitem descobrir que a entrega parou.
- [ ] A vigilância aprovou regra e amostra; proteção de dados aprovou exposição.
- [ ] Evidências, manual e responsável operacional foram arquivados.

## 14. O que não fazer

- Não contar biblioteca, rota genérica ou tela responsiva como requisito entregue.
- Não modelar caso de saúde em `Solicitacao` apenas para acelerar a primeira tela.
- Não importar diretamente para tabelas finais sem staging, quarentena e reconciliação.
- Não usar thread local, arquivo temporário ou scheduler em cada worker web para job crítico.
- Não tratar hash de arquivo como identificação completa de atualização oficial.
- Não publicar coordenada, foto, vídeo ou texto de relato antes da revisão de privacidade.
- Não deixar backup, alerta ou exportação informar sucesso sem verificação real.
- Não deixar o bot inventar fonte, regra epidemiológica ou orientação clínica.
- Não declarar 24/7 sem medir canal, fila, fornecedor, recuperação e plantão.
- Não fechar o projeto somente porque a suíte legada passou; demonstrar cada requisito.

## 15. Primeiras cinco entregas documentais/técnicas

Para começar imediatamente, sem alterar ainda o código funcional, preparar nesta ordem:

1. **ADR de escopo e fontes:** lista de sistemas, processos, layouts, chaves, períodos, canais e decisões pendentes.
2. **Matriz de aceite:** requisitos 4.6.1, 4.7 e I–XVI ligados a evidência, responsável, dependência e demonstração.
3. **Plano de segurança/recuperação:** A01–A04, testes negativos, segredos, CSRF, backup, restauração, RTO/RPO e operação.
4. **Contrato de dados da fatia vertical:** fixture, dicionário, estados do lote, regras do IIP e reconciliação esperada.
5. **Plano de homologação:** ambientes, massa sintética/anonimizada, roteiro de demonstração, critérios de saída e plano de retorno.

Depois dessas cinco entregas, o time pode abrir PRs de fundação com o risco conhecido e começar a primeira fatia vertical. O relatório consolidado continua sendo a fonte da classificação contratual; este guia é a sequência prática para transformar os achados em entregas comprováveis.
