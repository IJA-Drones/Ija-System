# IJA System

Sistema web desenvolvido para apoiar a gestão operacional de serviços com drones, reunindo em uma única plataforma fluxos de solicitação, agenda, ordens de serviço, equipes, pilotos, veículos, relatórios, anexos e operações agro.

O projeto nasceu para resolver uma dor prática: tirar processos importantes de planilhas, mensagens soltas e controles manuais, levando tudo para um ambiente com login, histórico, filtros, permissão por perfil e dados consultáveis.

> Este repositório representa um sistema real, construído e evoluído a partir de demandas operacionais. A documentação abaixo descreve o que existe no projeto e as principais decisões técnicas por trás dele.

## Visão Geral

O IJA System centraliza duas frentes principais:

- **Operação urbana / UVIS**: solicitações de voo, agendamento, aprovação, execução em campo, registros de OS, checklists, pilotos, equipes, veículos e relatórios.
- **Operação agro**: clientes, fornecedores, orçamentos, contratos, ordens de serviço, pilotos agro, equipamentos, financeiro, contas a pagar/receber, caixa diário e banco de talentos.

O sistema foi construído em Flask, com arquitetura modular por domínio, banco relacional via SQLAlchemy, migrações com Alembic/Flask-Migrate, templates Jinja2, exportações em Excel/PDF e integrações externas para mapas, CEP, armazenamento de arquivos e backup.

## Problema Que o Projeto Resolve

Antes de um sistema centralizado, uma operação desse tipo tende a depender de:

- planilhas separadas por área ou responsável;
- troca de arquivos por WhatsApp/e-mail;
- dificuldade para saber o status real de uma solicitação;
- perda de histórico entre aprovação, execução e conclusão;
- baixa rastreabilidade sobre quem alterou o que;
- retrabalho na geração de relatórios e documentos;
- dificuldade de filtrar dados por unidade, região, prefeitura, equipe ou piloto.

O IJA System organiza esse fluxo em uma aplicação única, com dados estruturados e telas voltadas para o trabalho diário.

## Principais Funcionalidades

### Autenticação e Perfis de Acesso

O sistema possui login com redirecionamento conforme o perfil do usuário. Entre os perfis tratados no código estão:

- desenvolvedor;
- administrador;
- administrador de prefeitura;
- regional;
- UVIS;
- equipe operacional da UVIS;
- piloto;
- equipe operacional;
- financeiro;
- financeiro admin;
- piloto agro.

Essa separação permite que cada usuário acesse apenas as telas e dados compatíveis com sua função. O projeto também aplica escopos por prefeitura e região em consultas sensíveis.

### Painel Administrativo

O painel administrativo concentra a gestão das solicitações e ordens de serviço. Ele permite:

- acompanhar solicitações recebidas;
- filtrar por status, período, endereço, UVIS, região e outros critérios;
- aprovar, atualizar, cancelar e consultar demandas;
- exportar dados em planilhas;
- acessar histórico de OS;
- consultar formulários preenchidos pelas equipes;
- acompanhar registros operacionais de campo.

### Fluxo UVIS e Equipe Operacional

As UVIS podem registrar demandas e acompanhar o andamento das solicitações. O sistema também contempla acesso operacional para equipes, com foco em execução e consulta de dados relevantes da demanda.

Recursos importantes desse fluxo:

- cadastro de solicitações com endereço, data, foco, tipo de operação e anexos;
- consulta de CEP e preenchimento de endereço;
- geolocalização e integração com Google Maps;
- visualização de agenda;
- acompanhamento de status;
- formulários de execução;
- histórico de solicitações e OS;
- retorno automático quando aplicável.

### Agenda e Notificações

O módulo de agenda organiza as operações por período e por perfil de usuário. Ele possui regras específicas para diferentes visões, como piloto, equipe, UVIS e administração.

Funcionalidades presentes:

- agenda operacional;
- filtros por período;
- exportação em Excel;
- notificações internas;
- marcação de notificações como lidas;
- limpeza e exclusão de notificações;
- rotas do dia para apoio ao deslocamento.

### Pilotos, OS e Execução em Campo

O sistema inclui área voltada para pilotos e equipes que executam ordens de serviço.

Entre os recursos implementados:

- fila de OS por piloto ou equipe;
- histórico de OS;
- conclusão de serviços;
- formulário operacional de execução;
- cálculos de dosagem;
- upload de imagem principal, imagens complementares e vídeos;
- exclusão controlada de mídias;
- exportação de OS em PDF e Excel;
- visualização de mapas e trajetos quando há coordenadas.

### Upload de Mídias e Armazenamento Externo

Um dos pontos técnicos relevantes do projeto é o tratamento de upload de mídias pesadas.

O sistema possui suporte para:

- upload em streaming;
- envio de imagens e vídeos por chunks;
- sessões de upload em segundo plano;
- acompanhamento de status de upload;
- armazenamento externo via WebDAV/Skybox/Nextcloud;
- remoção de arquivos remotos quando mídias são apagadas no sistema.

Essa solução reduz o risco de timeout em servidores Gunicorn e evita carregar arquivos grandes inteiros na memória da aplicação.

### Módulo Agro

O módulo agro amplia o sistema para uma operação comercial e operacional de drones no campo.

Ele contempla:

- dashboard agro;
- cadastro de clientes agro;
- cadastro de fornecedores;
- cadastro de equipes;
- cadastro de pilotos agro;
- cadastro de equipamentos agro;
- orçamentos;
- contratos;
- ordens de serviço agro;
- relatórios e documentos em PDF;
- anexos em orçamentos;
- mapeamentos;
- acesso específico para piloto agro.

O fluxo permite sair de um cadastro comercial, gerar orçamento, transformar em contrato, criar OS e acompanhar a execução.

### Financeiro Agro

O projeto possui uma área financeira voltada ao contexto agro, com separação entre entradas, saídas, contas, bancos e relatórios.

Recursos presentes:

- lançamentos financeiros;
- contas a pagar;
- contas a receber;
- categorias e subcategorias;
- bancos e conciliação;
- caixa diário;
- controle por competência;
- dashboard financeiro;
- fluxo de caixa;
- DRE gerencial;
- relatório geral de contas;
- exportação em Excel e PDF.

### Banco de Talentos Agro

O sistema também possui um banco de talentos para organizar currículos e candidatos relacionados à operação agro.

Esse módulo inclui:

- upload de currículo;
- armazenamento de metadados do arquivo;
- listagem de candidatos;
- detalhe do talento;
- download e visualização do PDF;
- organização por prefeitura quando aplicável.

### Veículos, Equipamentos e Checklists

O sistema controla recursos operacionais usados em campo.

Funcionalidades:

- cadastro de veículos;
- cadastro de drones e baterias;
- controle de equipamentos;
- logs de veículo;
- controle de quilometragem;
- abastecimentos por turno;
- upload de nota fiscal e foto de painel;
- checklist semanal de veículo;
- checklist semanal de drone;
- exportação de veículos e logs em Excel.

### Importação de Dados DJI

O projeto possui módulo para importar e analisar dados vindos de voos DJI.

Recursos identificados:

- importação de planilhas `.xlsx`;
- deduplicação por fingerprint;
- armazenamento de lotes de importação;
- registros de voo com piloto, equipe, drone, período, área pulverizada, duração e bateria;
- importação de rotas KML;
- visualização de rota em mapa;
- download de KML;
- relatórios de logs DJI.

### Relatórios e Exportações

O sistema oferece várias formas de extrair dados para análise ou prestação de contas.

Formatos e exemplos:

- Excel com OpenPyXL;
- PDF com ReportLab e WeasyPrint;
- relatórios de solicitações;
- relatórios de OS;
- relatórios de coleta de imagens;
- relatórios financeiros agro;
- exportação de agenda;
- exportação de histórico;
- documentos de orçamento, contrato e OS agro.

### Feedback e Melhoria Contínua

O sistema possui uma central de feedback para registrar sugestões, problemas e melhorias.

Recursos presentes:

- criação de tópicos por unidade ou usuário autorizado;
- categorias, prioridade e status;
- comentários internos ou visíveis conforme o fluxo;
- anexos em comentários;
- acompanhamento de resolução.

### Auditoria, Diagnóstico e Observabilidade

O projeto possui mecanismos internos para registrar atividade e diagnosticar problemas.

Recursos técnicos:

- auditoria automática de ações mutáveis (`POST`, `PUT`, `PATCH`, `DELETE`);
- registro de usuário, método, endpoint, path, status code, IP, user agent e horário;
- painel dev com métricas de erros, usuários ativos, checks de ambiente e runtime;
- health checks simples e completos;
- registro de eventos de watchdog/redeploy;
- tratamento padronizado para erros 404 e 500 em HTML ou JSON.

## Arquitetura

O projeto segue o padrão de aplicação Flask com factory (`create_app`) e separação por módulos de domínio.

```text
app/
  __init__.py              # Factory da aplicação, extensões, auditoria e health checks
  routes.py                # Registro central dos módulos
  models.py                # Modelos SQLAlchemy
  extensions.py            # SQLAlchemy, LoginManager e Migrate
  clients/                 # Clientes externos: CEP e Google Maps
  core/                    # Rotas, erros e helpers globais
  shared/                  # Validadores, filtros, upload, acesso e formatadores
  modules/
    admin_dashboard/
    admin_uvis/
    agro/
    agenda_notificacoes/
    auditoria/
    auth/
    backup/
    chatbot/
    clientes/
    dev_dashboard/
    dji_flight_logs/
    drones_import/
    equipamentos/
    feedback/
    mapas/
    piloto_os/
    relatorios/
    solicitacoes/
    veiculos/
  static/
  templates/
migrations/
tests/
```

Fluxo simplificado:

```mermaid
flowchart LR
    Usuario[Usuário autenticado] --> Auth[Autenticação e perfil]
    Auth --> Painel[Painel conforme permissão]
    Painel --> Operacao[Solicitações, OS, agenda e execução]
    Painel --> Agro[Clientes, orçamentos, contratos e financeiro agro]
    Painel --> Relatorios[PDF, Excel e dashboards]
    Operacao --> Banco[(Banco relacional)]
    Agro --> Banco
    Banco --> Auditoria[Auditoria e histórico]
    Operacao --> Storage[Uploads e storage externo]
    Operacao --> Mapas[CEP e Google Maps]
```

## Modelagem de Dados

O banco possui entidades para diferentes áreas do sistema. Alguns grupos importantes:

- **Usuários e acesso**: `Usuario`, `Prefeitura`, vínculos por perfil, prefeitura e região.
- **Operação UVIS**: `Solicitacao`, `OrdemServico`, `OrdemServicoEquipeUvis`, `Notificacao`.
- **Equipes e pilotos**: `Pilotos`, `PilotoUvis`, `Equipe`, `EquipePiloto`, `EquipeUvis`.
- **Agro**: `ClienteAgro`, `FornecedorAgro`, `OrcamentoAgro`, `ContratoAgro`, `OrdemServicoAgro`, `RdMapeamentoAgro`.
- **Financeiro agro**: `FinanceiroAgro`, `FinanceiroAgroEntrada`, `FinanceiroAgroSaida`, `FinanceiroAgroCategoria`, `FinanceiroAgroSubcategoria`, `BancoAgro`, `FinanceiroAgroCaixaDiario`, `FinanceiroAgroCompetenciaControle`.
- **Equipamentos e frota**: `Equipamentos`, `Drones`, `Baterias`, `Veiculos`, `LogVeiculo`, `Abastecimento`, checklists semanais.
- **DJI**: `DjiFlightLogImport`, `DjiFlightRecord`, `DjiFlightKmlRoute`.
- **Governança**: `AuditoriaUsuario`, `FeedbackTopico`, `FeedbackComentario`, `WatchdogDeployEvent`.

## Integrações

O projeto integra ou prepara integração com:

- **Google Maps**: mapas, geocodificação, rotas e visualização geográfica;
- **ViaCEP**: consulta de endereço por CEP e busca de CEP por endereço;
- **Skybox/Nextcloud via WebDAV**: armazenamento de mídias de OS;
- **Dropbox**: rotina de backup;
- **PostgreSQL**: banco de produção via `DATABASE_URL`;
- **SQLite/PostgreSQL local**: conforme configuração de ambiente;
- **Gunicorn**: execução em produção;
- **Flask-Migrate/Alembic**: versionamento de schema.

## Stack Técnica

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Flask-Migrate / Alembic
- Jinja2
- SQLAlchemy
- PostgreSQL
- OpenPyXL
- Pandas
- ReportLab
- WeasyPrint
- Pypdf
- Requests / HTTPX
- APScheduler
- Dropbox SDK
- WhiteNoise
- Flask-Talisman
- Gunicorn
- HTML, CSS e JavaScript

## Qualidade e Testes

O repositório possui testes automatizados cobrindo regras específicas de negócio e acesso, como:

- filtros da agenda operacional;
- escopo operacional de veículos;
- acesso ao painel dev;
- banco de talentos agro.

Os testes ficam em `tests/` e podem ser executados com:

```bash
python -m unittest discover tests
```

## Como Rodar Localmente

### 1. Clonar o repositório

```bash
git clone https://github.com/pedro-cruzz/IJA-System.git
cd IJA-System
```

### 2. Criar e ativar ambiente virtual

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto.

Exemplo mínimo:

```env
SECRET_KEY=uma-chave-local
DATABASE_URL=postgresql://usuario:senha@localhost:5432/ija_system
KEY_API_GOOGLE_MAPS=sua-chave-google-maps
GOOGLE_MAPS_KEY_BACK=sua-chave-google-maps-backend
```

Variáveis opcionais usadas por módulos específicos:

```env
DROPBOX_APP_KEY=
DROPBOX_APP_SECRET=
DROPBOX_REFRESH_TOKEN=
SKYBOX_WEBDAV_URL=
SKYBOX_USERNAME=
SKYBOX_APP_PASSWORD=
SKYBOX_BASE_DIR=dados ordens de serviço
```

### 5. Aplicar migrações

```bash
flask --app app:create_app db upgrade
```

### 6. Rodar a aplicação

```bash
python run.py
```

A aplicação sobe em:

```text
http://localhost:5000
```

## Deploy

O `Procfile` indica um fluxo de deploy com migrações antes da inicialização do servidor:

```text
flask --app app:create_app db upgrade && gunicorn "app:create_app()"
```

Também existem endpoints de saúde:

```text
/healthz
/healthz/full
```

O primeiro verifica a aplicação. O segundo também valida a conexão com o banco.

## O Que Este Projeto Demonstra

Para além das telas, este projeto demonstra experiência prática com:

- organização de um sistema Flask modular;
- modelagem relacional para um domínio com muitos fluxos;
- controle de permissão por perfil, prefeitura e região;
- formulários complexos com validação;
- geração de documentos PDF e planilhas Excel;
- integração com APIs externas;
- tratamento de upload pesado;
- auditoria e rastreabilidade;
- manutenção de migrations ao longo da evolução do produto;
- desenvolvimento de funcionalidades a partir de necessidades reais de operação.

## Nota de Portfólio

Este não é um projeto de estudo isolado. É um sistema operacional em evolução, com funcionalidades criadas para resolver problemas concretos de organização, rastreabilidade e produtividade.

Ao mesmo tempo, ele ainda carrega características naturais de um produto interno em crescimento: alguns módulos cresceram bastante, há pontos que podem ser refinados e a arquitetura continua evoluindo conforme novas demandas aparecem. Essa também é parte importante do aprendizado técnico do projeto.

## Autor

Desenvolvido por Pedro Cruz, com foco em sistemas web, automação de processos operacionais, gestão de dados e ferramentas internas para equipes de campo.
