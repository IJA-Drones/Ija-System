# IJA System

## Documentação Técnica Descritiva do Programa de Computador

**Finalidade:** apoio à identificação, caracterização funcional e documentação técnica do software para registro de programa de computador perante o Instituto Nacional da Propriedade Industrial (INPI).

**Nome do programa:** IJA System  
**Categoria:** sistema web de gestão operacional, administrativa, logística, documental e financeira para serviços com drones  
**Versão documental:** 1.0  
**Data de emissão:** 26 de agosto de 2026  
**Snapshot técnico analisado:** commit 4abad5d5cc80abad14538409fb7a8bb14935ca31, de 25 de agosto de 2026  
**Autores identificados no repositório:** Pedro Cruz e João Pedro  
**Titular dos direitos patrimoniais:** [PREENCHER PELO REQUERENTE]  
**CNPJ/CPF do titular:** [PREENCHER PELO REQUERENTE]  
**Versão comercial do software:** [PREENCHER, SE APLICÁVEL]  
**Classificação/campo de aplicação a declarar no pedido:** [VALIDAR PELO REQUERENTE OU PROCURADOR]

---

## Controle do documento

| Item | Conteúdo |
|---|---|
| Documento | Documentação Técnica Descritiva do IJA System |
| Revisão | 1.0 |
| Base de evidência | Código-fonte, migrações, templates, arquivos estáticos, testes, scripts e documentação do repositório |
| Repositório de origem | IJA-Drones/Ija-System |
| Escopo temporal | Estado do software em 25/08/2026 |
| Idioma | Português do Brasil |
| Confidencialidade sugerida | Uso controlado pelo titular; não anexar segredos, credenciais ou dados pessoais ao pacote técnico |

### Histórico de revisões

| Revisão | Data | Descrição | Responsável |
|---|---|---|---|
| 1.0 | 26/08/2026 | Emissão inicial, com descrição integral da arquitetura, módulos, dados, fluxos, tecnologias e operação | Elaboração técnica baseada no repositório |

### Nota de uso para registro

Este relatório descreve o software e permite reconhecer sua finalidade, estrutura interna, regras, componentes e fluxos. Ele não substitui o código-fonte nem a formação do objeto eletrônico que ficará sob guarda do titular. Conforme a orientação oficial vigente consultada no portal do INPI, a documentação técnica relevante para identificar e caracterizar o programa deve ser preservada pelo titular, e seu resumo digital hash é informado no pedido eletrônico. O guia básico atual também informa a necessidade de certificado digital qualificado compatível com ICP-Brasil para o requerimento.

Fontes oficiais consultadas:

- [Guia Básico de Programa de Computador — INPI](https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-basico/guia-basico)
- [Programa de computador — Manuais e Vídeo — INPI](https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/programa-de-computador-manual-completo)
- [Programa de computador — Mais informações — INPI](https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-completo-de-programa-de-computador)

Este documento não constitui parecer jurídico. Dados de titularidade, autoria, cessão, vínculo empregatício, procurador, classificação e documentos formais devem ser conferidos pelo requerente antes do protocolo.

---

# 1. Identificação e caracterização do software

## 1.1 Denominação

O programa é denominado **IJA System**. Trata-se de uma aplicação web responsiva, executada em servidor, destinada à centralização de processos de campo realizados com drones e de seus processos administrativos associados.

## 1.2 Propósito geral

O IJA System substitui controles distribuídos em planilhas, mensagens e arquivos avulsos por uma base operacional única. O software organiza solicitações, aprovações, agenda, ordens de serviço, equipes, pilotos, drones, baterias, veículos, anexos, geolocalização, execução em campo, retorno automático, registros de voo, relatórios, auditoria, manutenção, estoque e uma cadeia comercial/financeira específica para operações agro.

## 1.3 Contextos atendidos

O sistema contempla duas verticais de negócio integradas:

1. **Operação urbana e UVIS:** gestão de solicitações e ordens de serviço relacionadas a operações de drones, com uso indicado no repositório para apoio a rotinas da Oceano Azul e de UVIS de São Paulo em ações de campo, inclusive combate à dengue.
2. **Operação agro:** gestão comercial, operacional e financeira de serviços de drones no campo, desde o cadastro do cliente e orçamento até contrato, ordem de serviço, relatório, recebimentos, contas, bancos e caixa diário.

## 1.4 Usuários e partes interessadas

Os usuários são unidades solicitantes, gestores administrativos, direção, equipes operacionais, pilotos, equipes UVIS, áreas financeiras, suporte técnico e operadores do módulo agro. Clientes e fornecedores são entidades de negócio cadastradas, sem que o código analisado indique necessariamente acesso próprio ao sistema.

## 1.5 Natureza do produto

O IJA System é um sistema de informação transacional multiusuário, baseado em navegador, com autenticação, controle de acesso, persistência relacional, geração de documentos, importação e exportação de arquivos, integrações HTTP e armazenamento externo de mídias.

---

# 2. Escopo e método de levantamento

## 2.1 Escopo coberto

Foram considerados os componentes presentes no repositório:

- aplicação Python/Flask;
- 32 módulos de domínio registrados na aplicação;
- 55 classes de modelo SQLAlchemy;
- 328 declarações de rotas HTTP identificadas no código;
- 154 templates HTML/Jinja2;
- 171 arquivos CSS, incluindo temas e bundle gerado;
- 2 arquivos JavaScript próprios na área estática;
- 109 migrações Alembic;
- 16 arquivos de teste, com 119 casos identificados por funções/métodos de teste;
- scripts de manutenção, importação, vínculo de KML, bundle CSS e watchdog;
- documentação operacional existente.

As contagens representam o snapshot informado na capa e podem mudar em versões posteriores.

## 2.2 Método

A descrição foi produzida por inspeção estática da estrutura do repositório, módulos, rotas, serviços, modelos, migrações, templates, configurações, testes e documentação existente. Não foram utilizados valores do arquivo de ambiente e nenhum segredo foi reproduzido.

## 2.3 Limite de afirmação

Este documento descreve o comportamento implementado no código analisado. Recursos dependentes de credenciais, serviços externos, dados de produção ou configuração de infraestrutura são descritos conforme suas interfaces internas, sem afirmar disponibilidade permanente do serviço terceiro.

---

# 3. Visão funcional consolidada

## 3.1 Capacidades principais

O sistema oferece as seguintes capacidades de alto nível:

- autenticação e redirecionamento por perfil;
- segregação de dados por prefeitura, região, UVIS, equipe e usuário;
- cadastro, edição, análise, aprovação, negação, cancelamento e conclusão de solicitações;
- criação e execução de ordens de serviço urbanas e agro;
- bloqueio de nova solicitação para endereço concluído e marcado como bloqueado;
- geocodificação, place ID, mapa, rota, perímetro e KML;
- agenda e notificações internas;
- upload e streaming de imagens, vídeos e documentos;
- armazenamento local e WebDAV/Skybox/Nextcloud;
- cadastros de pilotos, equipes, veículos, drones, baterias e equipamentos;
- logs de veículo, abastecimento, limpeza e checklists semanais;
- estoque de peças, manutenção de equipamento e histórico de consumo;
- importação de planilhas de drones com normalização assistida pela API Gemini;
- importação, deduplicação, análise e vínculo de logs DJI e rotas KML;
- relatórios e exportações em PDF e Excel;
- orçamentos, contratos, RD de mapeamento e OS agro;
- contas a pagar/receber, entradas, saídas, bancos, conciliação, caixa diário, fluxo de caixa e DRE gerencial;
- banco de talentos agro e currículos;
- central de feedback/bugs com comentários e anexos;
- auditoria automática, presença de usuários, painel de diagnóstico e health checks;
- backup de banco de dados para Dropbox;
- PWA básica com manifesto e service worker.

## 3.2 Fluxo geral do sistema

~~~mermaid
flowchart TD
    A[Usuário acessa o IJA System] --> B{Autenticação e perfil}
    B -->|UVIS, equipe, piloto ou operação urbana| U[Vertical urbana e UVIS]
    B -->|Administração, direção ou dev| G[Gestão e governança]
    B -->|Agro, piloto agro ou financeiro| R[Vertical agro]

    U --> U1[Solicitação]
    U1 --> U2[Validação de endereço, geolocalização e duplicidade]
    U2 --> U3[Análise, aprovação e agendamento]
    U3 --> U4[Ordem de serviço]
    U4 --> U5[Execução, dosagem, formulário e mídias]
    U5 --> U6{Retorno necessário?}
    U6 -->|Sim| U7[Nova etapa no ciclo de retorno]
    U7 --> U3
    U6 -->|Não| U8[Histórico e relatórios]

    R --> R1[Cliente, fornecedor, equipe, piloto e equipamento]
    R1 --> R2[Orçamento e RD de mapeamento]
    R2 --> R3[Contrato]
    R3 --> R4[OS agro]
    R4 --> R5[Execução, KML, mapa e relatório]
    R5 --> R6[Financeiro agro]

    G --> G1[Usuários, prefeituras, UVIS e permissões]
    G --> G2[Auditoria, presença, suporte e diagnóstico]
    G --> G3[Backup, health checks e watchdog]

    U --> DB[(Banco relacional)]
    R --> DB
    G --> DB
    U5 --> FS[Arquivos locais ou WebDAV/Skybox]
    R3 --> FS
    R5 --> FS
~~~

---

# 4. Perfis de acesso e escopos

## 4.1 Perfis identificados

| Perfil técnico | Finalidade predominante | Escopo típico |
|---|---|---|
| dev | Desenvolvimento, diagnóstico e administração global | Global; painel dev e recursos de teste protegidos |
| diretor | Direção e administração global | Global |
| admin | Administração geral | Global |
| prefeitura_admin | Administração de uma prefeitura | Prefeitura vinculada |
| operario / operador | Operação administrativa com edição | Conforme filtros e vínculos aplicáveis |
| visualizar / visualizador | Consulta administrativa | Somente leitura; pode haver escopo regional/COVISA |
| regional | Consulta por região | Região vinculada; consultas sem região válida retornam conjunto vazio |
| uvis | Unidade solicitante | Própria UVIS/prefeitura e solicitações permitidas |
| equipe_uvis | Conta operacional da equipe UVIS | UVIS-mãe e equipe vinculada |
| piloto | Piloto urbano | OS do piloto/equipe e recursos operacionais |
| equipe_oceano | Equipe operacional urbana | OS e frota da equipe |
| financeiro_admin | Administração financeira agro | Módulo financeiro agro |
| financeiro | Operação financeira agro | Módulo financeiro agro |
| piloto_agro | Execução operacional agro | RD, contratos e OS compatíveis com o piloto/equipe |

## 4.2 Mecanismos de autorização

O sistema utiliza Flask-Login para sessão autenticada e funções de autorização internas. Os filtros principais são aplicados nas consultas SQLAlchemy:

- administradores globais podem operar sem restrição de prefeitura;
- usuário prefeitura_admin sem prefeitura válida recebe consulta vazia em recursos escopados;
- usuários regionais são filtrados por região normalizada;
- usuários UVIS e equipe UVIS são associados a unidade, prefeitura e equipe;
- telas e ações também validam o tipo de usuário antes de renderizar, editar, excluir ou exportar;
- anexos e mídias possuem verificações específicas de leitura e remoção;
- rotas mutáveis são auditadas quando correspondem a ações relevantes.

## 4.3 Fluxo de autenticação

~~~mermaid
sequenceDiagram
    actor Usuario
    participant Navegador
    participant Auth as Módulo auth
    participant DB as Banco de dados
    participant Presenca as Registro de presença

    Usuario->>Navegador: Informa login e senha
    Navegador->>Auth: POST /login ou login especializado
    Auth->>DB: Busca Usuario pelo login
    DB-->>Auth: Usuário, hash e vínculos
    Auth->>Auth: Verifica senha e perfil ativo
    alt credenciais válidas
        Auth->>Presenca: Marca login/último acesso
        Auth-->>Navegador: Cria sessão e redireciona por perfil
    else credenciais inválidas ou perfil incompatível
        Auth-->>Navegador: Exibe mensagem e mantém login
    end
~~~

---

# 5. Arquitetura do software

## 5.1 Estilo arquitetural

O projeto segue uma arquitetura web monolítica modular baseada no padrão application factory do Flask. A aplicação é construída em tempo de inicialização, configura extensões, segurança, auditoria, helpers de template e blueprints. Os domínios separam rotas HTTP e serviços, enquanto a persistência centraliza os modelos em app/models.py.

## 5.2 Camadas lógicas

| Camada | Componentes | Responsabilidade |
|---|---|---|
| Apresentação | templates Jinja2, CSS, JavaScript, manifesto e service worker | Formulários, tabelas, painéis, filtros, mapas, responsividade e temas |
| Interface HTTP | blueprints e arquivos routes.py | Rotas GET/POST, validação de acesso, respostas HTML/JSON e downloads |
| Aplicação/domínio | arquivos service.py, dosagem.py e helpers shared | Regras de negócio, consultas, cálculos, transições e integrações |
| Persistência | Flask-SQLAlchemy, modelos e migrações Alembic | Entidades, relacionamentos, índices, transações e evolução do schema |
| Exportação | exporters.py e excel_exporters.py | Geração de PDF, Excel e documentos operacionais |
| Integração | clients, Skybox, Dropbox, Gemini e APIs HTTP | CEP, mapas, clima, armazenamento, backup e normalização assistida |
| Operação | health checks, Gunicorn, WhiteNoise, Talisman e watchdog | Execução, arquivos estáticos, HTTPS, diagnóstico e recuperação |

## 5.3 Componentes de inicialização

1. run.py pode reconstruir o bundle CSS e cria a aplicação.
2. create_app carrega configurações do ambiente.
3. WhiteNoise atende arquivos estáticos.
4. SQLAlchemy, Migrate e LoginManager são inicializados.
5. Flask-Talisman aplica políticas de transporte; em modo de depuração, HTTPS forçado é desativado.
6. handlers de health check, auditoria, presença, variáveis globais e erros são registrados.
7. o blueprint auth e o blueprint principal são acoplados à aplicação.
8. app/routes.py registra os 32 módulos de domínio no blueprint principal.

## 5.4 Diagrama de componentes

~~~mermaid
flowchart LR
    Browser[Navegador / PWA] --> HTTP[Flask + Gunicorn]
    HTTP --> Auth[Autenticação e autorização]
    HTTP --> Routes[Rotas modulares]
    Routes --> Services[Serviços de domínio]
    Services --> ORM[SQLAlchemy]
    ORM --> PG[(Banco via DATABASE_URL)]
    Services --> Templates[Jinja2]
    Templates --> Browser
    Services --> Exports[OpenPyXL / ReportLab / WeasyPrint / Pypdf]
    Services --> CEP[ViaCEP / BrasilAPI]
    Services --> Maps[Google Maps / Geocoding]
    Services --> Weather[Open-Meteo]
    Services --> WebDAV[Skybox / Nextcloud WebDAV]
    Services --> Dropbox[Dropbox Backup]
    Services --> Gemini[Gemini API]
    HTTP --> Static[WhiteNoise + CSS/JS/imagens]
~~~

## 5.5 Ciclo de uma requisição

~~~mermaid
sequenceDiagram
    actor U as Usuário
    participant F as Flask
    participant A as Autorização
    participant S as Serviço
    participant D as SQLAlchemy/Banco
    participant T as Jinja2 ou JSON
    participant L as Auditoria

    U->>F: Requisição HTTP
    F->>A: Valida sessão, perfil e escopo
    A->>S: Encaminha dados validados
    S->>D: Consulta ou transação
    D-->>S: Entidades/resultado
    S-->>T: Contexto, arquivo ou payload
    T-->>U: HTML, JSON, PDF, Excel ou mídia
    opt método mutável e ação auditável
        F->>L: Registra usuário, endpoint, IP e status
    end
~~~

---

# 6. Catálogo completo de módulos

Os números de rotas são contagens de decoradores HTTP no snapshot analisado. Um mesmo endpoint pode aceitar mais de um método.

| Módulo | Rotas | Responsabilidade funcional |
|---|---:|---|
| admin_checklists | 3 | Listagem semanal consolidada e detalhe administrativo de checklists de veículos e drones |
| admin_dashboard | 12 | Painel administrativo, decisões, histórico de OS, filtros, mapas, exportações e trabalhos PDF |
| admin_uvis | 5 | Cadastro, edição, exclusão, listagem e exportação de UVIS |
| agenda_notificacoes | 7 | Agenda, rotas do dia, exportação Excel, leitura, exclusão e limpeza de notificações |
| agro | 101 | Núcleo comercial, operacional e financeiro agro, cadastros, documentos, OS, KML e relatórios |
| anexos | 3 | Visualização, download e remoção controlada de anexos de solicitações |
| auditoria | 1 | Consulta administrativa dos eventos de auditoria |
| auth | 4 | Login geral, login UVIS operacional, login piloto agro e logout |
| backup | 3 | Tela, status e acionamento de backup do banco |
| canceladas | 2 | Cancelamento de solicitação e listagem de canceladas |
| cep | 2 | Consulta de endereço por CEP e busca de CEP por endereço |
| chatbot | 4 | Assistentes FAQ determinísticos para UVIS, admin, agro admin e piloto agro |
| clientes | 5 | Cadastro, listagem, edição, exclusão e exportação de clientes urbanos |
| dashboard | 4 | Dashboard UVIS, histórico e formulários de OS UVIS |
| dev_dashboard | 5 | Diagnóstico de runtime, usuários ativos, erros, ambiente e health checks |
| dji_flight_logs | 9 | Importação, exportação, consulta, vínculo, visualização, download e exclusão de logs/KML DJI |
| drones_import | 3 | Tela e importação de planilhas de drones urbanos/agro, com normalização assistida |
| equipamentos | 21 | Drones, baterias, equipamentos, manutenções, peças e históricos |
| equipe_uvis_dashboard | 4 | Painel, formulário e histórico operacional de equipes UVIS |
| equipes | 5 | Cadastro, listagem, credenciais, edição e exclusão de equipes urbanas |
| estoque | 5 | Cadastro, edição, listagem, exclusão e exportação de peças de estoque |
| feedback | 16 | Tópicos, bugs, comentários, anexos, moderação, status e acompanhamento |
| mapas | 4 | Mapa de relatório, geolocalização, heatmap e dados geográficos |
| painel_operacional | 2 | Visão operacional/direção com métricas, mapa, tempo e contexto de campo |
| piloto_checklists | 1 | Preenchimento semanal de checklists de veículo e drone |
| piloto_os | 25 | Fila, formulário, conclusão, dosagem, mídias, uploads por chunks e exportações de OS |
| pilotos | 4 | Cadastro, listagem, edição e exclusão de pilotos urbanos |
| relatorios | 15 | Menu, solicitações, OS, coleta de imagens, retornos automáticos e exportações |
| solicitacoes | 4 | Verificação de bloqueio, criação, edição e exclusão de solicitações |
| usuarios | 9 | Usuários, prefeituras, edição, credenciais, alternância e exclusão |
| uvis_equipes | 12 | Equipes UVIS, membros, contas operacionais e administração central |
| veiculos | 23 | Veículos, logs, turnos, abastecimentos, limpeza, alertas, exclusões e exportações |

## 6.1 Componentes compartilhados

| Componente | Função interna |
|---|---|
| app/shared/access.py | Normalização de papéis e filtros de prefeitura/região |
| app/shared/formatters.py | Formatação de moeda e telefone |
| app/shared/geofencing.py | Detecção de áreas geográficas restritas |
| app/shared/os_history_filters.py | Filtros reutilizáveis de histórico e retorno automático |
| app/shared/place_id.py | Resolução e normalização de Google place ID |
| app/shared/presence.py | Registro limitado de presença e login/logout |
| app/shared/query_filters.py | Parsing de filtros e valores múltiplos |
| app/shared/redirects.py | Redirecionamentos seguros para destinos internos |
| app/shared/retorno_ciclo.py | Montagem, navegação e resumo do ciclo de OS de retorno |
| app/shared/skybox.py | Upload, download, streaming, range e exclusão via WebDAV |
| app/shared/solicitacao_focos.py | Catálogo e validação de foco, tipo de visita e imóvel |
| app/shared/timezone.py | Conversão para America/Sao_Paulo |
| app/shared/uploads.py | Pasta padrão e extensões permitidas |
| app/shared/validators.py | Validações reutilizáveis de entrada |
| app/clients/cep_client.py | ViaCEP com fallback BrasilAPI |
| app/clients/google_maps_client.py | Geocodificação direta e reversa pelo Google |

---

# 7. Especificação funcional por domínio

## 7.1 Solicitações urbanas e UVIS

A solicitação representa a demanda inicial. Ela contém data e hora de agendamento, foco, tipo de operação, tipo de visita, tipo de imóvel, altura de voo, distrito, endereço, coordenadas, place ID, perímetros, anexos, protocolo, justificativa, equipe, piloto, status e vínculo com o usuário solicitante.

No cadastro, o sistema:

1. valida que o logradouro não contenha indevidamente o número predial;
2. aceita número de imóvel controlado ou a marca S/N;
3. exige distrito administrativo;
4. define a UVIS responsável conforme perfil;
5. resolve o place ID quando necessário;
6. verifica se existe solicitação concluída e bloqueada para o mesmo local, respeitando prefeitura;
7. valida tipo de visita, tipo de imóvel e foco;
8. converte coordenadas e identifica área restrita;
9. grava a nova solicitação inicialmente como PENDENTE.

Usuários não administrativos podem editar apenas solicitações próprias e, em regra, somente quando PENDENTE ou NEGADO. Perfis administrativos podem alterar o estado, protocolo e justificativa conforme suas permissões.

### Fluxo da solicitação urbana

~~~mermaid
stateDiagram-v2
    [*] --> PENDENTE: cadastro válido
    PENDENTE --> EM_ANALISE: triagem administrativa
    EM_ANALISE --> APROVADO: autorização
    EM_ANALISE --> APROVADO_RECOMENDACOES: autorização condicionada
    EM_ANALISE --> NEGADO: decisão negativa
    NEGADO --> PENDENTE: correção e reenvio permitido
    APROVADO --> EM_EXECUCAO: abertura/preenchimento da OS
    APROVADO_RECOMENDACOES --> EM_EXECUCAO
    EM_EXECUCAO --> CONCLUIDO: formulário concluído
    PENDENTE --> CANCELADO: cancelamento autorizado
    EM_ANALISE --> CANCELADO: cancelamento autorizado
~~~

## 7.2 Administração e gestão

O painel administrativo reúne filtros por status, período, endereço, UVIS, região, prefeitura, equipe e piloto. Permite decidir solicitações, atribuir recursos, consultar andamento e histórico de OS, visualizar mapas, gerar relatórios e administrar cadastros estruturais.

A aplicação diferencia permissões de visualização e edição. Perfis de leitura não recebem automaticamente capacidade de mutação. Usuários regionais e de prefeitura têm consultas limitadas ao respectivo escopo.

## 7.3 Execução de ordem de serviço urbana

A OS urbana registra a execução: responsável, data e horários, situação da aplicação, larva visualizada, necessidade de retorno, produto, formulação, dosagem, quantidade aplicada, taxa/área, tipo de aplicação, drones de pulverização e monitoramento, clima, motivo de não realização, observações, piloto, auxiliar, assinaturas e mídias.

O sistema disponibiliza:

- fila de OS aprovadas por piloto/equipe;
- formulário operacional;
- cálculo e registro de dosagem planejada;
- associação de drones e preservação de snapshot dos dados do equipamento;
- conclusão transacional da solicitação/OS;
- exportação em PDF e Excel;
- leitura de mídia por usuários autorizados;
- criação do retorno quando o formulário determinar nova visita.

## 7.4 Retorno automático

Uma solicitação pode apontar para sua origem por origem_retorno_id e informar gerada_automaticamente. A lógica monta a cadeia com limite defensivo de 80 nós, protege contra ciclos inválidos e produz resumo de cada etapa.

Quando a execução pede retorno, uma nova solicitação é criada com herança dos dados necessários, permanece ligada à origem e retorna ao fluxo de agendamento/aprovação. O histórico pode filtrar:

- solicitações que são retorno;
- solicitações que geraram retorno;
- qualquer item pertencente a um ciclo;
- ciclo completo com OS inicial e etapas sucessoras.

~~~mermaid
flowchart LR
    S1[Solicitação/OS inicial] --> C1[Conclusão do formulário]
    C1 --> D{Campo de retorno indica nova visita?}
    D -->|Não| F[Fim do ciclo]
    D -->|Sim| S2[Nova solicitação automática]
    S2 --> A2[Agendamento e aprovação]
    A2 --> O2[Nova OS]
    O2 --> C2[Conclusão da etapa]
    C2 --> D2{Novo retorno?}
    D2 -->|Sim| S3[Próxima etapa encadeada]
    D2 -->|Não| F
~~~

## 7.5 Agenda e notificações

A agenda apresenta solicitações conforme período e perfil. Há visões e filtros por piloto, equipe, UVIS e administração, exportação Excel e cálculo de rotas do dia quando aplicável. Notificações registram título, mensagem, link, data, leitura e exclusão lógica, com escopo individual ou ampliado para perfis autorizados.

## 7.6 Equipes UVIS

O módulo permite criar equipes, adicionar até cinco membros, manter função e contato, gerar nomes e logins sugeridos, validar credenciais e criar conta equipe_uvis vinculada à UVIS-mãe. A equipe registra formulário próprio de execução e histórico, sem romper o escopo da unidade.

## 7.7 Pilotos e equipes urbanas

Pilotos possuem prefeitura, nome, região principal e alternativa, telefone e vínculos com UVIS/equipe. Equipes agrupam pilotos, credenciais e recursos operacionais. As consultas consideram prefeitura, região e composição da equipe para evitar exibição cruzada indevida.

## 7.8 Veículos e logística

O subsistema de veículos mantém cadastro, associação de equipes, logs por turno, quilometragem, abastecimentos, fotos de painel, notas fiscais, exclusões auditadas, limpezas e alertas. Há validação de variação máxima de 500 km por turno e janelas de alerta de limpeza de 14 dias para operação e 21 dias para administração.

Os checklists semanais cobrem iluminação, painel, fluidos, vidros, pneus, segurança, itens internos, lataria e assinatura do responsável. O checklist de drone cobre hélices, tanque, trem de pouso, câmeras, carregadores, baterias, cabos, correia, quantidades e observações.

## 7.9 Equipamentos, manutenção e estoque

Equipamentos usam uma entidade base com especializações para drones, baterias e veículos. O módulo registra equipamentos, manutenções, peças utilizadas, histórico e estoque. EstoquePeca controla peça, quantidade, unidade e metadados; ManutencaoPecaUso associa consumo de peça a uma manutenção. Exportações geram planilhas e relatórios de acompanhamento.

## 7.10 Logs DJI e rotas KML

Planilhas de voo são importadas em lotes. Cada registro recebe fingerprint único para deduplicação e armazena período, localização, aeronave, tipo de tarefa, área, quantidade, duração, cultura, piloto, equipe, campo, serial e bateria. Arquivos de rota KML recebem SHA-256, código de rota, metadados, pontos em JSON e podem ser vinculados a registros de voo e OS.

O vínculo pode usar place ID e outros critérios disponíveis, além de associação manual. O sistema permite visualizar a rota no mapa, baixar o KML, exportar registros e excluir a rota de forma controlada.

~~~mermaid
flowchart TD
    X[Planilha DJI XLSX] --> P[Leitura e normalização]
    P --> H[Fingerprint por registro]
    H --> D{Registro já existe?}
    D -->|Sim| SK[Ignora como duplicado]
    D -->|Não| FR[DjiFlightRecord]
    K[Arquivo KML] --> KH[SHA-256 e parsing]
    KH --> KR[DjiFlightKmlRoute]
    KR --> L{Encontrado vínculo compatível?}
    L -->|Sim| FR
    L -->|Manual| OS[Ordem de serviço]
    FR --> RP[Relatório/exportação/mapa]
~~~

## 7.11 Relatórios e exportações

O módulo de relatórios oferece visões de solicitações, OS, coleta de imagens e retornos automáticos. Os filtros incluem período, status, UVIS, região, prefeitura, equipe, piloto e atributos operacionais. As exportações preservam os filtros autorizados e podem gerar:

- planilhas Excel com formatação, tabelas e larguras controladas;
- PDFs com tabelas, gráficos, imagens, cabeçalhos e rodapés;
- relatórios de OS e formulários de campo;
- relatório de coleta de imagens com pré-busca e limite de memória;
- relatórios financeiros agro;
- documentos de orçamento, contrato e OS agro.

Trabalhos PDF de maior custo podem rodar de forma assíncrona em executor local, com acompanhamento de status.

## 7.12 Módulo agro — cadastros e fluxo comercial

O módulo agro mantém clientes, fornecedores, equipes, pilotos e equipamentos próprios. Um orçamento registra cliente, propriedade, cultura, serviço, área, risco, datas, valores, drones e endereço. Para serviços que exigem mapeamento, a RD coleta condições técnicas e riscos da área.

O orçamento pode originar um contrato com dados do contratante, propriedade, escopo, valores, prazos, foro, assinatura e comprovante de pagamento. O contrato aprovado e atribuído a uma equipe pode originar uma OS agro.

### Fluxo agro ponta a ponta

~~~mermaid
flowchart TD
    C[Cliente agro] --> O[Orçamento]
    F[Fornecedor] --> FIN[Contas e saídas]
    EQ[Equipe, piloto e equipamento] --> RD
    O --> Q{Serviço exige mapeamento?}
    Q -->|Sim| RD[RD de mapeamento]
    Q -->|Não| CT[Contrato]
    RD --> CT
    CT --> AP{Contrato aprovado e equipe definida?}
    AP -->|Não| REV[Revisão comercial]
    AP -->|Sim| OS[OS agro planejada]
    OS --> EX[Execução]
    EX --> LOG[Logs de voo, KML e mapa]
    LOG --> REL[Relatório final PDF]
    REL --> FA[Financeiro agro]
    FA --> RC[Recebimentos, bancos, caixa e conciliação]
~~~

## 7.13 Ordem de serviço agro

A OS agro registra contrato, orçamento, equipe, piloto, drones de pulverização/mapeamento, identificador único, status, data/período, cliente, propriedade, cultura, serviço, cidade, parâmetros de voo, condições climáticas, área, calda, taxa, produto, dosagem, classe toxicológica, arquivos de relatório/mapa, KML e observações.

Os estados implementados são PLANEJADA, EM EXECUCAO, CONCLUIDA e CANCELADA. Ao concluir, finalizado_em é preenchido. O piloto agro possui painel próprio para RD pendente, contratos aguardando OS, OS em andamento e concluídas.

## 7.14 Financeiro agro

O financeiro reúne três origens de movimento:

- recebíveis vinculados a contrato/OS em FinanceiroAgro;
- entradas manuais em FinanceiroAgroEntrada;
- saídas manuais em FinanceiroAgroSaida.

As entidades registram competência, vencimento, realização, banco, categoria, subcategoria, cliente/fornecedor, valores, parcelas, status e observações. O módulo oferece:

- contas a receber e a pagar;
- registro de recebimento parcial ou integral;
- bancos e saldos;
- conciliação por situação e movimento;
- categorias e subcategorias;
- caixa diário com abertura e fechamento;
- controle por competência;
- dashboard, fluxo de caixa e DRE gerencial;
- exportação Excel/PDF.

~~~mermaid
stateDiagram-v2
    [*] --> PENDENTE
    PENDENTE --> PARCIAL: recebimento parcial
    PARCIAL --> RECEBIDO: quitação
    PENDENTE --> RECEBIDO: recebimento integral
    PENDENTE --> VENCIDO: vencimento sem quitação
    PARCIAL --> VENCIDO: saldo vencido
    PENDENTE --> CANCELADO: cancelamento
    PARCIAL --> CANCELADO: cancelamento permitido conforme validação
~~~

Para saídas, o estado de realização é PAGO; para entradas, RECEBIDO. Itens cancelados são separados dos realizados e dos atrasados nos cálculos de conciliação.

## 7.15 Banco de talentos agro

CurriculoAgro registra candidato, contato, localização, currículo, metadados, status, análise e observações. Os estados são NOVO, EM_ANALISE, ENTREVISTA, APROVADO e ARQUIVADO. O serviço aceita armazenamento local/externo conforme configuração e permite listar, detalhar, visualizar ou baixar o currículo com controle de acesso.

## 7.16 Importação de drones assistida

O módulo drones_import lê planilhas, converte seus dados para texto estruturado e pode chamar a API Gemini por HTTP para normalizar campos conforme schema JSON. Há lista de modelos configuráveis e fallbacks. Depois da normalização, o sistema valida duplicidade de serial/registro e cria drone urbano ou equipamento agro conforme o contexto.

Essa integração é assistiva e não substitui as validações do domínio e do banco.

## 7.17 Assistente FAQ

O chatbot interno não depende de modelo generativo. Ele utiliza catálogos de perguntas e respostas, normalização de texto e pontuação por palavras-chave. Existem bases distintas para UVIS, administração, administração agro e piloto agro, com autorização por perfil.

## 7.18 Feedback e suporte

Tópicos de feedback registram unidade, autor, título, descrição, categoria, setor, status, prioridade, responsável e datas. Comentários podem ser internos, ter anexos de imagem e obedecer a moderação. O fluxo diferencia bugs ativos e finais e limita, por regra, a quantidade de bugs ativos por coordenação quando aplicável.

## 7.19 Auditoria, presença e diagnóstico

Após requisições mutáveis relevantes, o sistema tenta gravar evento de auditoria contendo usuário, login, tipo, método, tipo de evento, endpoint, path, query string, status HTTP, IP, user agent, referrer e data UTC. Falha na auditoria é registrada em log sem invalidar a resposta principal.

Presença de usuário registra primeiro/último acesso, login, logout, endpoint, IP e agente. O painel dev calcula usuários online e ausentes por janelas de cinco e trinta minutos e apresenta verificações de banco, ambiente e runtime.

## 7.20 Backup e watchdog

O backup executa pg_dump para o banco configurado, comprime o arquivo e o envia ao Dropbox em upload simples ou sessão por blocos de 8 MiB. O serviço mantém estado em memória para informar execução e erro. APScheduler permite rotinas em segundo plano.

O watchdog de deploy realiza health checks e pode acionar um hook de redeploy quando falhas consecutivas excedem o limite configurado. Eventos são gravados em WatchdogDeployEvent quando o endpoint e token correspondentes estão configurados.

---

# 8. Modelo de dados

## 8.1 Princípios de modelagem

O modelo é relacional, com chaves primárias inteiras, chaves estrangeiras, índices de busca, restrições únicas e timestamps. O sistema usa relacionamentos SQLAlchemy com carregamento lazy, joined ou selectin conforme o caso. Dados flexíveis, como listas de mídias, perímetros, pontos KML ou payloads de origem, podem ser armazenados como texto serializado/JSON.

## 8.2 Catálogo das 55 entidades

| Grupo | Entidades |
|---|---|
| Organização e acesso | Prefeitura, Usuario, UsuarioPresenca |
| Feedback e governança | FeedbackTopico, FeedbackComentario, FeedbackComentarioAnexo, AuditoriaUsuario, WatchdogDeployEvent, Notificacao |
| UVIS e operação urbana | EquipeUvis, Pilotos, PilotoUvis, Solicitacao, OrdemServico, OrdemServicoEquipeUvis, Clientes |
| Agro comercial | ClienteAgro, FornecedorAgro, OrcamentoAgro, ContratoAgro, RdMapeamentoAgro, OrdemServicoAgro |
| Agro financeiro | FinanceiroAgro, BancoAgro, FinanceiroAgroCategoria, FinanceiroAgroSubcategoria, FinanceiroAgroSaida, FinanceiroAgroEntrada, FinanceiroAgroCaixaDiario, FinanceiroAgroCompetenciaControle |
| Agro operacional e talentos | EquipeAgro, PilotoAgro, CurriculoAgro, EquipamentoAgro |
| Equipes e equipamentos urbanos | Equipe, EquipePiloto, Equipamentos, Drones, Baterias, Veiculos |
| Estoque e manutenção | EstoquePeca, ManutencaoPecaUso, ManutencaoEquipamento |
| Frota | LogVeiculo, Abastecimento, LimpezaVeiculo, LimpezaVeiculoAlertaCiencia, ChecklistSemanalVeiculo, ChecklistSemanalDrone |
| DJI urbano | DjiFlightLogImport, DjiFlightRecord, DjiFlightKmlRoute |
| Logs agro | AgroFlightLogImport, AgroFlightRecord, AgroFlightKmlRoute |

## 8.3 Relações centrais — operação urbana

~~~mermaid
erDiagram
    Prefeitura ||--o{ Usuario : possui
    Prefeitura ||--o{ Solicitacao : delimita
    Usuario ||--o{ Solicitacao : solicita
    Usuario ||--o{ EquipeUvis : organiza
    Pilotos }o--o{ Usuario : atende_UVIS
    Solicitacao ||--o| OrdemServico : gera
    Solicitacao ||--o| OrdemServicoEquipeUvis : gera_execucao_UVIS
    Solicitacao o|--o{ Solicitacao : origina_retorno
    Equipe ||--o{ EquipePiloto : compoe
    Pilotos ||--o{ EquipePiloto : integra
    Equipe ||--o{ OrdemServico : executa
    Drones ||--o{ OrdemServico : equipa
    DjiFlightKmlRoute o|--o| OrdemServico : documenta_rota
~~~

## 8.4 Relações centrais — agro

~~~mermaid
erDiagram
    Prefeitura ||--o{ ClienteAgro : delimita
    ClienteAgro ||--o{ OrcamentoAgro : solicita
    OrcamentoAgro ||--o| RdMapeamentoAgro : detalha
    OrcamentoAgro ||--o| ContratoAgro : formaliza
    ContratoAgro ||--o{ OrdemServicoAgro : autoriza
    EquipeAgro ||--o{ OrdemServicoAgro : executa
    PilotoAgro ||--o{ OrdemServicoAgro : pilota
    EquipamentoAgro ||--o{ OrdemServicoAgro : equipa
    OrdemServicoAgro ||--o{ FinanceiroAgro : gera_recebivel
    BancoAgro ||--o{ FinanceiroAgro : recebe
    BancoAgro ||--o{ FinanceiroAgroEntrada : recebe
    BancoAgro ||--o{ FinanceiroAgroSaida : paga
    FornecedorAgro ||--o{ FinanceiroAgroSaida : fornece
    AgroFlightKmlRoute o|--o| OrdemServicoAgro : documenta
~~~

## 8.5 Relações centrais — equipamentos e frota

~~~mermaid
erDiagram
    Equipamentos ||--o| Drones : especializa
    Equipamentos ||--o| Baterias : especializa
    Equipamentos ||--o| Veiculos : especializa
    Equipamentos ||--o{ ManutencaoEquipamento : recebe
    ManutencaoEquipamento ||--o{ ManutencaoPecaUso : consome
    EstoquePeca ||--o{ ManutencaoPecaUso : fornece
    Veiculos ||--o{ LogVeiculo : registra
    LogVeiculo ||--o{ Abastecimento : contem
    Veiculos ||--o{ LimpezaVeiculo : recebe
    Veiculos ||--o{ ChecklistSemanalVeiculo : verifica
    Drones ||--o{ ChecklistSemanalDrone : verifica
~~~

## 8.6 Integridade e rastreabilidade

O schema contém índices por campos operacionais de alta consulta, como status, data, prefeitura, região, equipe, piloto, place ID, serial e competência. Fingerprints e hashes evitam duplicidade em importações e arquivos KML. Relacionamentos de origem preservam a cadeia de retorno e snapshots de equipamento preservam dados relevantes mesmo se o cadastro mudar posteriormente.

---

# 9. Fluxos de dados e processos técnicos

## 9.1 Upload e streaming de mídia

O sistema suporta upload direto e, para vídeos grandes, sessão em segundo plano com chunks. A mídia pode ser enviada ao armazenamento WebDAV sem carregamento integral em memória. O streaming de leitura propaga Range quando suportado e, se o servidor remoto responder com o arquivo completo, o sistema pode construir uma resposta parcial localmente.

~~~mermaid
sequenceDiagram
    actor P as Piloto
    participant B as Navegador
    participant F as Flask
    participant W as WebDAV/Skybox
    participant D as Banco

    P->>B: Seleciona mídia
    B->>F: Inicia upload/sessão
    loop blocos do arquivo
        B->>F: Envia chunk
        F->>W: Transmite ou acumula conforme fluxo
        F-->>B: Confirma progresso
    end
    F->>W: Finaliza arquivo remoto
    W-->>F: Sucesso e caminho
    F->>D: Grava marcador skybox:// ou webdav://
    D-->>F: Commit
    F-->>B: Upload concluído
~~~

## 9.2 Consulta e geolocalização de endereço

~~~mermaid
flowchart TD
    A[Entrada de CEP/endereço] --> V[Validação e normalização]
    V --> C{Consulta por CEP?}
    C -->|Sim| VC[ViaCEP]
    VC -->|falha técnica| BA[BrasilAPI]
    C -->|Não| VA[ViaCEP por endereço]
    VC --> G[Google Geocoding]
    BA --> G
    VA --> G
    G --> P[Latitude, longitude e place ID]
    P --> R[Detecção de área restrita]
    P --> D{Local concluído e bloqueado?}
    D -->|Sim| X[Impede nova solicitação]
    D -->|Não| S[Persiste solicitação]
~~~

## 9.3 Exportação de relatório

~~~mermaid
flowchart LR
    U[Filtros do usuário] --> A[Aplicação de autorização e escopo]
    A --> Q[Consulta SQLAlchemy]
    Q --> N[Normalização e agregações]
    N --> E{Formato}
    E -->|XLSX| XL[OpenPyXL]
    E -->|PDF| PDF[ReportLab/WeasyPrint/Pypdf]
    E -->|HTML| J[Jinja2]
    XL --> D[Download]
    PDF --> D
    J --> B[Navegador]
~~~

## 9.4 Tratamento de erros

Erros HTTP são convertidos para HTML ou JSON conforme o path, tipo de conteúdo e Accept do cliente. O payload JSON inclui success, error, code e request_id. Exceções não tratadas são registradas e apresentadas como erro 500 sem expor stack trace ao usuário final.

---

# 10. Linguagens, frameworks e tecnologias

## 10.1 Linguagens e formatos

| Tecnologia | Uso no software |
|---|---|
| Python | Backend, regras, integrações, scripts, testes, migrações e exportações |
| HTML | Templates de páginas e documentos gerados |
| CSS | Design system, layout, componentes, páginas, tema agro e dark mode |
| JavaScript | Interações do formulário de focos, service worker e comportamento do navegador |
| SQL | Consultas geradas pelo ORM, health checks e operações de migração |
| Jinja2 | Template engine do frontend e de documentos HTML |
| JSON | APIs internas, configurações, payloads, pontos KML e dados serializados |
| XML/KML | Rotas geográficas e documentos Office/PDF intermediários |
| YAML | Workflow de automação do watchdog no GitHub Actions |

## 10.2 Frameworks e bibliotecas centrais

| Componente | Versão declarada | Finalidade |
|---|---:|---|
| Flask | 3.0.3 | Framework web e roteamento |
| Flask-Login | 0.6.3 | Sessões e usuário autenticado |
| Flask-SQLAlchemy | 3.1.1 | ORM integrado ao Flask |
| SQLAlchemy | 2.0.45 | Persistência relacional e consultas |
| Flask-Migrate | 4.0.5 | Integração das migrações |
| Alembic | 1.17.2 | Versionamento do schema |
| Jinja2 | 3.1.6 | Renderização de templates |
| Werkzeug | 3.0.1 | Segurança de senha, uploads e utilitários WSGI |
| Gunicorn | 23.0.0 | Servidor WSGI de produção |
| WhiteNoise | 6.11.0 | Entrega de arquivos estáticos |
| Flask-Talisman | 1.1.0 | HTTPS e cabeçalhos de segurança |
| Requests | 2.33.1 | Integrações HTTP e WebDAV |
| HTTPX | 0.28.1 | Cliente HTTP disponível no ambiente |
| OpenPyXL | 3.1.5 | Leitura e geração de planilhas Excel |
| Pandas | 3.0.3 | Processamento tabular disponível |
| ReportLab | 4.4.6 | Geração programática de PDF |
| WeasyPrint | 68.1 | Conversão HTML/CSS para PDF |
| Pypdf | 5.4.0 | Manipulação e composição de PDF |
| Pillow | 12.0.0 | Tratamento de imagens |
| Matplotlib | 3.10.8 | Gráficos de relatórios |
| APScheduler | 3.11.2 | Agendamento de tarefas de backup |
| Dropbox SDK | 12.0.2 | Armazenamento de backups |
| Psycopg2 Binary | 2.9.11 | Driver PostgreSQL |
| Pytest | 9.1.1 | Execução de testes |

As versões acima refletem requirements.txt do snapshot. A presença de uma dependência no ambiente não implica que todos os seus recursos sejam utilizados diretamente em cada módulo.

## 10.3 Frontend e identidade visual

O frontend é server-rendered. A folha global é gerada por scripts/build_css_bundle.py a partir de arquivos ordenados por base, componentes, módulos, páginas, utilitários e temas. Há tema claro, dark mode e modo agro. O bundle possui verificação automatizada para evitar divergência e cadeias locais de importação.

O manifesto define ícones e comportamento instalável, enquanto o service worker mantém cache básico de recursos e oferece suporte de PWA. O mapa e componentes de calendário podem carregar bibliotecas do navegador conforme o template.

---

# 11. Integrações externas

| Integração | Protocolo/API | Dados envolvidos | Tratamento interno |
|---|---|---|---|
| Google Maps/Geocoding | HTTPS REST e recursos frontend | Endereço, coordenadas, place ID e rotas | Chaves separáveis para frontend/backend; resultado normalizado |
| ViaCEP | HTTPS REST | CEP e endereço | Serviço primário de consulta |
| BrasilAPI | HTTPS REST | CEP e endereço | Fallback para falha técnica da consulta por CEP |
| Open-Meteo | HTTPS REST | Coordenadas e previsão/condição meteorológica | Utilizado no painel operacional |
| Skybox/Nextcloud | WebDAV | Imagens, vídeos, currículos, comprovantes e arquivos | Upload, MKCOL, streaming, Range, exclusão e marcadores internos |
| Dropbox | SDK/API | Backup comprimido do banco | Upload simples ou em sessão por blocos |
| Gemini | HTTPS REST | Texto tabular da planilha e JSON normalizado | Schema de resposta, modelos fallback e validação posterior |
| PostgreSQL | Protocolo do banco | Dados transacionais | URL de ambiente, pool_pre_ping e pool_recycle |
| GitHub Actions/Render | HTTPS/CI | Health status e hook de redeploy | Watchdog configurável e registro de eventos |

## 11.1 Dependência e indisponibilidade

As integrações externas são configuráveis por variáveis de ambiente. Quando uma integração é obrigatória para a operação solicitada e não está configurada, o módulo retorna erro controlado. Em casos específicos há fallback, como ViaCEP para BrasilAPI ou armazenamento local quando previsto pelo serviço.

---

# 12. Especificações internas

## 12.1 Configuração por ambiente

Variáveis identificadas no código incluem:

- SECRET_KEY ou FLASK_SECRET_KEY;
- DATABASE_URL;
- KEY_API_GOOGLE_MAPS e GOOGLE_MAPS_KEY_BACK;
- DROPBOX_APP_KEY, DROPBOX_APP_SECRET e DROPBOX_REFRESH_TOKEN;
- SKYBOX_WEBDAV_URL, SKYBOX_USERNAME, SKYBOX_APP_PASSWORD e SKYBOX_BASE_DIR;
- GEMINI_API_KEY e GEMINI_MODEL;
- USER_PRESENCE_UPDATE_INTERVAL_SECONDS;
- CSS_BUNDLE_AUTO_BUILD;
- limites e timeouts de WebDAV, vídeo, mídia remota e exportação PDF;
- WATCHDOG_HEALTH_URL, RENDER_DEPLOY_HOOK_URL, WATCHDOG_EVENT_URL e WATCHDOG_EVENT_TOKEN;
- opções de depuração e reloader do Flask.

Valores secretos não fazem parte deste documento e não devem integrar um arquivo público de depósito.

## 12.2 Persistência

DATABASE_URL é carregada do ambiente. URLs antigas iniciadas por postgres:// são normalizadas para postgresql://. O pool verifica a conexão antes do uso e recicla conexões periodicamente. Migrações são aplicadas com Flask-Migrate/Alembic.

## 12.3 Transações

Operações de escrita usam a sessão SQLAlchemy e realizam commit ao final. Em falhas, os serviços relevantes executam rollback e propagam erro controlado ou exibem mensagem. Alguns registros de telemetria, como auditoria, são deliberadamente desacoplados para não invalidar a operação principal.

## 12.4 Arquivos e mídia

Uploads simples aceitam, no helper compartilhado, PDF, PNG, JPG/JPEG/JFIF, DOC/DOCX e XLS/XLSX. Módulos especializados definem conjuntos próprios para imagens, vídeo, KML ou comprovantes. Nomes são higienizados com secure_filename quando aplicável. Caminhos WebDAV rejeitam componentes . e .. e são codificados por segmento.

## 12.5 Datas e fuso horário

O sistema usa UTC para timestamps técnicos em auditoria/presença e converte para America/Sao_Paulo para exibição e rotinas locais. Regras de agenda, vencimento e caixa usam datas de negócio conforme o domínio.

## 12.6 Observabilidade

Os endpoints /healthz e /healthz/full verificam, respectivamente, processo web e processo mais banco de dados. Logs de acesso do Gunicorn omitem esses caminhos para reduzir ruído. O painel dev e o watchdog completam a observabilidade operacional.

---

# 13. Segurança, privacidade e controle

## 13.1 Controles implementados

- senhas armazenadas por hash do Werkzeug, sem armazenamento de senha em claro no modelo;
- sessões autenticadas por Flask-Login;
- checagem de perfil nas rotas sensíveis;
- escopos por prefeitura, região, UVIS, equipe e usuário;
- proteção HTTPS/cabeçalhos por Flask-Talisman em produção;
- validação de extensão e higienização de nomes em uploads;
- prevenção de travessia de diretório em caminhos WebDAV;
- timeouts em chamadas externas;
- streaming para reduzir consumo de memória;
- auditoria de mutações relevantes;
- respostas de erro que não expõem detalhes internos;
- health check separado para banco;
- deduplicação por fingerprint/hash em importações.

## 13.2 Dados tratados

O sistema pode tratar dados cadastrais de usuários, pilotos, clientes, fornecedores e candidatos; endereço e geolocalização; registros operacionais; assinaturas desenhadas/base64; imagens, vídeos, documentos; dados financeiros; IP e user agent. O titular deve aplicar políticas de acesso, retenção, backup e descarte compatíveis com a legislação e com os contratos da operação.

## 13.3 Limitações observáveis

- a política de segurança de conteúdo do Talisman está desabilitada no código analisado;
- a consulta HTTP do cliente de CEP utiliza verify=False, o que merece revisão operacional;
- parte dos estados aceita grafias históricas com e sem acento, exigindo normalização defensiva;
- alguns executores e estados de trabalhos assíncronos são mantidos em memória do processo;
- o arquivo .env existe localmente no workspace, mas seu conteúdo não foi usado nem incluído nesta documentação;
- a documentação de registro deve excluir dados reais e segredos.

Esses itens não descaracterizam a função do programa; registram decisões e pontos técnicos relevantes do snapshot.

---

# 14. Requisitos não funcionais identificados

## 14.1 Desempenho

- pool de banco com pre_ping e reciclagem;
- paginação e filtros server-side;
- carregamentos SQLAlchemy joined/selectin em consultas críticas;
- upload e download em streaming;
- Range HTTP para mídia;
- limites de linhas, concorrência, tamanho e memória em exportações;
- processos assíncronos locais para PDFs mais pesados;
- bundle CSS estático e WhiteNoise.

## 14.2 Disponibilidade

- health checks simples e completos;
- watchdog com tentativas e redeploy configurável;
- backup agendado e externo;
- tratamento de indisponibilidade do banco e de serviços externos;
- fallback de CEP.

## 14.3 Manutenibilidade

- separação por módulos, rotas e serviços;
- helpers compartilhados para regras transversais;
- migrações versionadas;
- suíte automatizada;
- documentação específica de fluxos complexos;
- CSS componentizado e bundle verificável.

## 14.4 Usabilidade

- dashboards por perfil;
- filtros persistentes e resumos de resultado;
- tema claro/escuro e modo agro;
- formulários especializados;
- feedback visual e mensagens de validação;
- assistente FAQ contextual;
- responsividade e PWA básica.

---

# 15. Implantação e operação

## 15.1 Execução local

O fluxo esperado é criar ambiente virtual Python, instalar requirements.txt, configurar .env, aplicar migrações e executar run.py. A aplicação local atende, por padrão, na porta 5000. O reloader é configurável e o bundle CSS pode ser reconstruído automaticamente.

## 15.2 Produção

O Procfile aplica as migrações e inicia Gunicorn com app:create_app(). O logger customizado reduz ruído dos health checks. WhiteNoise serve os arquivos estáticos e Flask-Talisman força HTTPS fora de debug.

~~~mermaid
flowchart LR
    CI[Deploy/CI] --> MIG[flask db upgrade]
    MIG --> G[Gunicorn]
    G --> APP[Flask create_app]
    APP --> DB[(PostgreSQL)]
    APP --> ST[WhiteNoise/static]
    MON[Watchdog] --> H[/healthz/full]
    H --> DB
    MON -->|falhas consecutivas| HOOK[Hook de redeploy]
    APP --> BK[Backup agendado]
    BK --> DROP[Dropbox]
~~~

## 15.3 Scripts operacionais

| Script | Finalidade |
|---|---|
| scripts/build_css_bundle.py | Gera e valida o bundle CSS global |
| scripts/backfill_solicitacoes_place_id.py | Preenche place IDs em solicitações existentes |
| scripts/link_existing_kml_routes_to_os.py | Vincula rotas KML existentes a OS compatíveis |
| scripts/report_unlinked_kml_reasons.py | Diagnostica motivos de KML não vinculado |
| scripts/seed_demo_kml_os.py | Cria dados demonstrativos de KML/OS |
| scripts/seed_os_for_existing_kml_routes.py | Cria OS de apoio para rotas existentes |
| scripts/render_watchdog.py | Monitora saúde e aciona recuperação configurada |

---

# 16. Testes e qualidade

## 16.1 Cobertura funcional identificada

Há 16 arquivos e 119 casos de teste identificados. Eles cobrem:

- upload de comprovante agro para Skybox;
- banco de talentos agro;
- integridade do bundle CSS;
- acesso ao painel dev;
- vínculo automático de KML;
- filtros da agenda operacional;
- clima do painel operacional;
- redirecionamentos seguros;
- filtros de região/equipe nos relatórios;
- relatório de retornos automáticos;
- construção de ciclos de retorno e escopo por prefeitura;
- upload Skybox;
- bloqueio por place ID/endereço;
- acesso de UVIS a mídias de OS;
- escopo operacional de veículos.

## 16.2 Estratégia de verificação

Os testes usam Pytest e unittest conforme o arquivo. As verificações combinam unidades de regra, consultas com banco de teste, controle de acesso, mocks de integrações e validação de respostas/arquivos.

## 16.3 Migrações

As 109 migrações documentam a evolução do schema: usuários, equipes, OS, checklists, frota, retorno automático, place ID, DJI/KML, agro, financeiro, bancos, talentos, feedback, auditoria, uploads e watchdog.

---

# 17. Estrutura física do repositório

~~~text
Ija-System/
├── app/
│   ├── __init__.py              # factory, health, auditoria e configuração global
│   ├── extensions.py            # SQLAlchemy, Migrate e LoginManager
│   ├── models.py                # 55 modelos de persistência
│   ├── routes.py                # registro central dos módulos
│   ├── clients/                 # CEP e Google Maps
│   ├── core/                    # rotas globais, erros e templating
│   ├── shared/                  # regras e helpers transversais
│   ├── modules/                 # 32 módulos funcionais
│   ├── templates/               # 154 templates Jinja2
│   └── static/                  # CSS, JS, imagens, manifesto e service worker
├── migrations/                  # Alembic e 109 revisões
├── scripts/                     # manutenção, importação, bundle e watchdog
├── tests/                       # suíte automatizada
├── docs/                        # relatórios e manuais operacionais
├── config.py                    # configuração por ambiente
├── run.py                       # entrada de desenvolvimento
├── gunicorn.conf.py             # filtro de logs de health check
├── Procfile                     # comando de produção
└── requirements.txt             # dependências Python fixadas
~~~

## 17.1 Dimensão aproximada do snapshot

| Tipo | Quantidade |
|---|---:|
| Arquivos Python em app e scripts | 141 |
| Linhas Python em app e scripts | 55.549 |
| Templates HTML | 154 |
| Linhas HTML/Jinja2 | 46.798 |
| Arquivos CSS | 171 |
| Linhas CSS autorais sem contar o bundle gerado | 26.729 |
| Arquivos JavaScript estáticos | 2 |
| Linhas JavaScript | 203 |
| Modelos SQLAlchemy | 55 |
| Declarações de rota | 328 |
| Migrações | 109 |
| Arquivos de teste | 16 |
| Linhas de teste | 3.548 |

---

# 18. Matriz de rastreabilidade

| Capacidade | Módulos/arquivos principais | Entidades centrais |
|---|---|---|
| Autenticação e perfil | auth, shared/access.py, app/__init__.py | Usuario, Prefeitura, UsuarioPresenca |
| Solicitação urbana | solicitacoes, dashboard, admin_dashboard | Solicitacao, Usuario, Prefeitura |
| OS urbana | piloto_os, equipe_uvis_dashboard | OrdemServico, OrdemServicoEquipeUvis, Solicitacao |
| Retorno automático | shared/retorno_ciclo.py, relatorios | Solicitacao, OrdemServico |
| Agenda/notificação | agenda_notificacoes | Solicitacao, Notificacao |
| Frota | veiculos, piloto_checklists, admin_checklists | Veiculos, LogVeiculo, Abastecimento, LimpezaVeiculo, Checklists |
| Equipamento/estoque | equipamentos, estoque | Equipamentos, Drones, Baterias, EstoquePeca, ManutencaoEquipamento |
| DJI/KML | dji_flight_logs | DjiFlightLogImport, DjiFlightRecord, DjiFlightKmlRoute |
| Agro comercial | agro | ClienteAgro, FornecedorAgro, OrcamentoAgro, ContratoAgro, RdMapeamentoAgro |
| Agro operacional | agro, agro/flight_logs_service.py | OrdemServicoAgro, EquipeAgro, PilotoAgro, EquipamentoAgro, AgroFlight* |
| Financeiro agro | agro, agro/excel_exporters.py | FinanceiroAgro, Entrada, Saida, Banco, Categoria, Caixa, Competencia |
| Talentos | agro/talent_bank_* | CurriculoAgro |
| Relatórios | relatorios, exporters | Entidades de cada domínio consultado |
| Feedback | feedback | FeedbackTopico, FeedbackComentario, FeedbackComentarioAnexo |
| Auditoria/diagnóstico | auditoria, dev_dashboard, app/__init__.py | AuditoriaUsuario, UsuarioPresenca, WatchdogDeployEvent |
| Backup e arquivos | backup, shared/skybox.py, anexos | Campos de arquivo nas entidades de domínio |

---

# 19. Formação do objeto técnico e hash para o INPI

## 19.1 Recomendação de conteúdo

Para identificar o programa de modo reproduzível, recomenda-se que o titular forme um arquivo único contendo, no mínimo:

- código-fonte autoral do snapshot escolhido;
- templates, CSS e JavaScript autorais;
- migrações e scripts autorais;
- requirements.txt, Procfile e configurações sem segredos;
- esta documentação técnica e seus diagramas;
- arquivo MANIFESTO.txt com data, commit, versão e lista de arquivos;
- termo interno de aprovação da versão, se utilizado pela organização.

## 19.2 Exclusões obrigatórias sugeridas

Não incluir:

- .env ou qualquer arquivo com credenciais;
- bancos de dados e backups com dados pessoais;
- upload-files, mídias de produção ou currículos reais;
- .git, .venv, __pycache__, caches de teste e arquivos temporários;
- chaves privadas, certificados, tokens e segredos de deploy;
- dependências de terceiros instaladas, salvo quando juridicamente necessário e devidamente licenciadas.

## 19.3 Procedimento reprodutível

1. definir formalmente o commit/snapshot a registrar;
2. criar uma cópia limpa do repositório;
3. remover itens excluídos e artefatos de ambiente;
4. gerar um manifesto ordenado de arquivos;
5. compactar o conjunto em arquivo único, sem senha;
6. calcular o SHA-512 do arquivo final;
7. registrar nome, tamanho, algoritmo, hash, data, responsável e local de custódia;
8. manter o arquivo original imutável e cópias de segurança sob controle do titular;
9. informar no e-Software exatamente o hash correspondente ao arquivo preservado.

Exemplos de cálculo, executados somente depois de congelado o pacote:

~~~text
# Linux
sha512sum ija-system-inpi.zip

# macOS
shasum -a 512 ija-system-inpi.zip

# Windows PowerShell
Get-FileHash .\ija-system-inpi.zip -Algorithm SHA512
~~~

## 19.4 Registro de custódia

| Campo | Preenchimento |
|---|---|
| Nome do arquivo técnico | [PREENCHER] |
| Tamanho em bytes | [PREENCHER] |
| Algoritmo | SHA-512 |
| Hash | [GERAR APÓS CONGELAMENTO] |
| Data/hora de geração | [PREENCHER] |
| Responsável | [PREENCHER] |
| Local primário de custódia | [PREENCHER] |
| Cópia de segurança | [PREENCHER] |
| Commit/snapshot | 4abad5d5cc80abad14538409fb7a8bb14935ca31 ou outro deliberadamente escolhido |

O hash não foi preenchido nesta emissão porque qualquer edição posterior do pacote altera o resumo. Ele deve ser calculado pelo titular somente após a composição definitiva do objeto técnico.

---

# 20. Limitações e exclusões desta documentação

Este documento não:

- declara titularidade patrimonial;
- comprova cessão de direitos entre autores, empregados, contratados ou empresa;
- classifica juridicamente o software no formulário do INPI;
- reproduz código-fonte integral;
- contém credenciais ou valores de produção;
- garante disponibilidade de APIs de terceiros;
- substitui políticas de segurança, privacidade, continuidade ou LGPD;
- certifica que o snapshot não sofrerá alterações futuras.

Os campos marcados como [PREENCHER] devem ser concluídos pelo requerente. A versão final usada no registro deve ser conferida, aprovada e preservada junto com o arquivo que originar o hash.

---

# 21. Glossário

| Termo | Definição no contexto do sistema |
|---|---|
| UVIS | Unidade de Vigilância em Saúde participante do fluxo urbano |
| OS | Ordem de serviço que formaliza e registra a execução |
| RD de mapeamento | Relatório/dados de mapeamento agro anteriores ou complementares à execução |
| Place ID | Identificador de local retornado pelo Google e usado em vínculos/bloqueios |
| KML | Formato geográfico usado para representar rotas de voo |
| Fingerprint | Resumo derivado dos dados de um registro para evitar importação duplicada |
| WebDAV | Protocolo HTTP usado para gerenciar arquivos no armazenamento externo |
| Skybox | Denominação de configuração usada pelo sistema para armazenamento WebDAV/Nextcloud |
| Retorno automático | Nova solicitação gerada e encadeada após uma OS indicar necessidade de retorno |
| Competência | Mês e ano de reconhecimento financeiro |
| Conciliação | Classificação e conferência de movimentos financeiros e bancários |
| PWA | Aplicação web com manifesto e service worker, instalável em dispositivos compatíveis |
| Snapshot | Estado específico e identificável do código-fonte |
| Hash | Resumo criptográfico usado para verificar integridade do arquivo técnico |

---

# 22. Termo de conferência

Declara-se, para fins internos de conferência, que esta documentação foi elaborada a partir do snapshot identificado na capa e descreve, em nível funcional e técnico, os módulos, entidades, fluxos, integrações e tecnologias observados no repositório.

Antes de seu uso externo, o titular deverá:

- revisar nomes de autores e titular;
- completar os campos de identificação;
- confirmar o snapshot efetivamente escolhido;
- verificar a correspondência entre documentação e arquivo técnico;
- gerar e registrar o hash do pacote definitivo;
- validar a documentação formal e o procedimento vigente diretamente nos canais oficiais do INPI.

**Responsável pela conferência técnica:** [PREENCHER]  
**Cargo/função:** [PREENCHER]  
**Data:** [PREENCHER]  
**Assinatura:** [PREENCHER]

---

# Anexo A — Inventário nominal dos modelos

1. Prefeitura
2. Usuario
3. FeedbackTopico
4. FeedbackComentario
5. FeedbackComentarioAnexo
6. AuditoriaUsuario
7. WatchdogDeployEvent
8. UsuarioPresenca
9. EquipeUvis
10. Pilotos
11. PilotoUvis
12. Solicitacao
13. OrdemServico
14. OrdemServicoEquipeUvis
15. Notificacao
16. Clientes
17. ClienteAgro
18. FornecedorAgro
19. OrcamentoAgro
20. ContratoAgro
21. RdMapeamentoAgro
22. OrdemServicoAgro
23. FinanceiroAgro
24. BancoAgro
25. FinanceiroAgroCategoria
26. FinanceiroAgroSubcategoria
27. FinanceiroAgroSaida
28. FinanceiroAgroEntrada
29. FinanceiroAgroCaixaDiario
30. FinanceiroAgroCompetenciaControle
31. EquipeAgro
32. PilotoAgro
33. CurriculoAgro
34. EquipamentoAgro
35. Equipe
36. EquipePiloto
37. Equipamentos
38. Drones
39. EstoquePeca
40. ManutencaoPecaUso
41. ManutencaoEquipamento
42. Baterias
43. Veiculos
44. LogVeiculo
45. Abastecimento
46. LimpezaVeiculo
47. LimpezaVeiculoAlertaCiencia
48. ChecklistSemanalVeiculo
49. ChecklistSemanalDrone
50. DjiFlightLogImport
51. DjiFlightRecord
52. DjiFlightKmlRoute
53. AgroFlightLogImport
54. AgroFlightRecord
55. AgroFlightKmlRoute

# Anexo B — Evidências técnicas primárias

| Evidência | Conteúdo comprovado |
|---|---|
| app/__init__.py | Factory, extensões, auditoria, presença, health checks e erros |
| app/routes.py | Registro dos 32 módulos |
| app/models.py | Entidades, relacionamentos, estados, índices e regras do modelo |
| app/shared/access.py | Papéis e escopos |
| app/modules/solicitacoes | Cadastro, edição, place ID e bloqueio |
| app/modules/piloto_os | Execução, dosagem, mídias e conclusão |
| app/shared/retorno_ciclo.py | Encadeamento de retornos |
| app/modules/agro | Fluxo comercial, operacional e financeiro agro |
| app/modules/dji_flight_logs | Importação e KML urbano |
| app/modules/veiculos | Frota, turnos, abastecimento e limpeza |
| app/modules/equipamentos e estoque | Ativos, manutenção e peças |
| app/modules/relatorios | Consultas e exportações |
| app/shared/skybox.py | Armazenamento e streaming WebDAV |
| app/modules/backup | pg_dump e Dropbox |
| migrations/versions | Evolução do banco |
| tests | Verificações automatizadas |
| requirements.txt | Dependências e versões |
| Procfile e gunicorn.conf.py | Execução em produção |

# Anexo C — Resumo de originalidade funcional observável

Sem formular conclusão jurídica sobre originalidade, o conjunto implementado apresenta combinação própria de elementos: fluxo urbano/UVIS com bloqueio geográfico por place ID; execução de OS com drones, dosagem, clima, assinaturas e mídias; encadeamento de retornos automáticos; associação entre logs DJI, KML e OS; gestão integrada de frota, checklists, limpeza, manutenção e estoque; fluxo agro que une orçamento, RD, contrato, OS e financeiro; e infraestrutura de upload/streaming adequada a mídias pesadas. A identificação do programa decorre da combinação dessas regras, modelos, interfaces, relatórios e integrações no snapshot preservado.
