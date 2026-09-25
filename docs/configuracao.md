# Configuração e integrações

Referência conferida em 25/09/2026 contra [config.py](../config.py), [run.py](../run.py), [Procfile](../Procfile) e os serviços citados abaixo. O [.env.example](../.env.example) contém um modelo sem credenciais reais.

`load_dotenv` carrega o `.env` da raiz sem substituir variáveis já exportadas. A classe `Config` é avaliada na importação; alterações exigem reiniciar todos os processos. Nem toda configuração Flask é automaticamente lida do ambiente: use os nomes consumidos pelo código. Credenciais vazias significam integração não configurada.

## Aplicação e dados

| Variável | Padrão no código | Uso |
| --- | --- | --- |
| `DATABASE_URL` | Sem padrão | Obrigatória para inicializar SQLAlchemy. `postgres://` é normalizado para `postgresql://` no Config. |
| `SECRET_KEY` | Chave aleatória com prefixo `dev-` se ausente | Defina chave estável em qualquer ambiente persistente, igual entre workers. Sessão e CSRF opcionais exigem pelo menos 32 caracteres e recusam a chave `dev-`. |
| `FLASK_SECRET_KEY` | Sem padrão | Alternativa lida quando `SECRET_KEY` está ausente. |
| `FLASK_DEBUG` | `1` ao executar `python run.py`; debug desligado normalmente na factory | Controla debug e comportamento HTTPS do Talisman. Use `0` em produção. |
| `FLASK_USE_RELOADER` | `0` em `run.py` | Habilita recarga de Python no servidor local. |
| `CSS_BUNDLE_AUTO_BUILD` | `0` no Config; `run.py` usa `setdefault(..., "1")` | Recompila bundle desatualizado antes da requisição. Produção já constrói no Procfile. |
| `IJA_CREATE_ALL` | Inativo | Somente o valor `1` aciona `db.create_all()` ao executar `run.py` diretamente; não substitui Alembic. |
| `USER_PRESENCE_UPDATE_INTERVAL_SECONDS` | `300` | Intervalo de atualização de presença. Não é o timeout da sessão. |
| `AUDIT_RETENTION_MAX_RECORDS` | `15000` | Limita quantidade de registros de auditoria; não expressa dias de retenção. Deve ser inteiro. |

A porta de `run.py` é fixa em **5002**. Não existe leitura de `PORT` nesse arquivo. `APP_ENV` não seleciona configuração Flask nem desliga tarefas. Não existe suporte atual a `IJA_AUTO_DB_MIGRATE`: o Procfile executa migrações em toda inicialização.

## Sessões, senhas e CSRF

| Variável | Padrão do Config | Regras |
| --- | --- | --- |
| `SECURITY_CONTROLS_ENABLED` | `0` | Ativa timeout e política de senha. |
| `CSRF_PROTECTION_ENABLED` | `0` | Ativação independente; exige token para escritas autenticadas e formulários de login. |
| `SESSION_IDLE_TIMEOUT_MINUTES` | `120` | Inteiro de 1 a 1440. `run.py` em DEBUG adota **480** se a variável não estiver definida. |
| `SESSION_IDLE_TIMEOUT_SECONDS` | Ausente | Override de 5 a 59 segundos, somente DEBUG/TESTING; configuração ativa é rejeitada fora deles. |
| `SESSION_MAX_LIFETIME_HOURS` | `0` | `0` desliga duração máxima; de 1 a 168 horas impõe limite absoluto. |
| `PASSWORD_MIN_LENGTH` | `9` | De 8 a 128 quando o controle está ativo; máximo aceito da senha é 128. |
| `PASSWORD_REQUIRE_UPPERCASE` | `1` | Exigir maiúscula. |
| `PASSWORD_REQUIRE_LOWERCASE` | `1` | Exigir minúscula. |
| `PASSWORD_REQUIRE_DIGIT` | `1` | Exigir número. |
| `PASSWORD_REQUIRE_SYMBOL` | `1` | Exigir símbolo. |

As flags do Config aceitam `1`, `true`, `yes` e `on` como verdadeiro. O exemplo de homologação de [segurança](seguranca-sessoes-senhas.md) usa 15 minutos e senha de 15 caracteres como configuração explícita; esses valores não são os defaults do Config. Senhas antigas continuam válidas. Confira nesse documento ativação, reversão, múltiplas abas e limitações da sessão por cookie.

## Endereços, clima e dados públicos

| Variável | Padrão | Integração |
| --- | --- | --- |
| `KEY_API_GOOGLE_MAPS` | Ausente | Chave frontend, injetada nas páginas; também é fallback em alguns clientes backend. |
| `GOOGLE_MAPS_KEY_BACK` | Ausente | Preferida para geocodificação backend. Configure restrições adequadas ao uso de cada chave. |
| `CORREIOS_CEP_TOKEN` | Ausente | Token preferido da API de CEP dos Correios. |
| `CORREIOS_API_TOKEN` | Ausente | Alternativa ao token acima. |
| `CORREIOS_CEP_BASE_URL` | `https://api.correios.com.br/cep` | Base à qual o cliente adiciona caminhos de consulta. |
| `INFODENGUE_GEOCODE` | `3550308` | Código municipal consultado. |
| `INFODENGUE_CITY` | `São Paulo` | Nome exibido; mantenha coerente com o código. |
| `INFODENGUE_DISEASE` | `dengue` | Seleção inicial; o portal também trata `chikungunya` e `zika`. |
| `INFODENGUE_LOOKBACK_WEEKS` | `8` | Janela do resumo da página pública. |

Fontes: [cliente CEP](../app/clients/cep_client.py), [Google Maps](../app/clients/google_maps_client.py), [health_news.py](../app/modules/portal_cidadao/health_news.py), [painel operacional](../app/modules/painel_operacional/service.py).

O CEP consulta Correios quando há token, depois ViaCEP e, em falha de consulta, BrasilAPI. Um CEP explicitamente inexistente pode encerrar a busca com 404. O cliente genérico ViaCEP/BrasilAPI usa `verify=False`; a correção está registrada na [revisão técnica](revisao-documentacao-2026-09-25.md). Clima e feeds de notícias têm endpoints definidos no serviço, sem credencial configurável no Config. A disponibilidade real dessas fontes não foi testada nesta revisão.

`GOOGLE_MAPS_API_KEY` aparece como fallback de `current_app.config` em uma rota de OS, mas não é carregada do ambiente por `Config`; prefira os dois nomes documentados na tabela.

## Arquivos e WebDAV

| Variável | Padrão | Uso |
| --- | --- | --- |
| `SKYBOX_WEBDAV_URL` | Ausente | URL DAV completa do armazenamento. |
| `SKYBOX_USERNAME` | Ausente | Usuário do armazenamento. |
| `SKYBOX_APP_PASSWORD` | Ausente | Senha de aplicativo WebDAV. |
| `SKYBOX_BASE_DIR` | `dados ordens de serviço` | Diretório remoto base. |
| `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASS`, `WEBDAV_BASE_DIR` | Fallback para os equivalentes `SKYBOX_*` | Compatibilidade dos fluxos de OS; se ambos existirem, `WEBDAV_*` prevalece nesses fluxos. O helper genérico Skybox continua usando `SKYBOX_*`. |
| `WEBDAV_CONNECT_TIMEOUT_SECONDS` | `30` | Timeout de conexão no fluxo WebDAV de OS. |
| `WEBDAV_TRANSFER_TIMEOUT_SECONDS` | `3600` | Timeout de transferência no mesmo fluxo. |
| `WEBDAV_UPLOAD_CHUNK_SIZE_BYTES` | `1048576` | Tamanho de bloco no envio WebDAV. |
| `VIDEO_BACKGROUND_UPLOAD_WORKERS` | `2` | Threads por processo para jobs de vídeo; inteiro positivo. |
| `VIDEO_CONVERSION_TIMEOUT_SECONDS` | `7200` | Limite para conversão. |
| `FFMPEG_PATH` | Procura `ffmpeg` no PATH | Caminho alternativo do executável. `ffprobe` é procurado no PATH. |

Fontes: [skybox.py](../app/shared/skybox.py), [rotas de OS](../app/modules/piloto_os/routes.py). Não assuma que os timeouts WebDAV de OS configuram todos os consumidores Skybox. Os arquivos locais são resolvidos em `upload-files/`; não existe variável `UPLOAD_FOLDER` lida pelo [helper atual](../app/shared/uploads.py).

## Dropbox e Gemini

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` | Ausentes | Backup e armazenamento de currículos do banco de talentos. |
| `PROJECT_NAME` | `backup` | Prefixo do arquivo de backup. |
| `APP_ENV` | `prod` | Parte do nome do backup. |
| `GEMINI_API_KEY` | Ausente | Análise de currículos e normalização de importação de drones. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modelo preferido no código, com tentativas alternativas implementadas no serviço. Não comprova disponibilidade do modelo no provedor. |

Currículos são enviados ao Dropbox e seu conteúdo pode ser enviado ao Gemini no processamento. A classificação de IA deve ser conferida por uma pessoa. O chatbot do sistema é um FAQ baseado em regras; ele não usa essa configuração Gemini.

Fontes: [backup](../app/modules/backup/service.py), [banco de talentos](../app/modules/agro/talent_bank_service.py), [importação de drones](../app/modules/drones_import/service.py).

## Exportações PDF

| Variável | Padrão | Faixa/comportamento |
| --- | ---: | --- |
| `PDF_EXPORT_MAX_CONCURRENT` | 1 | Limite por processo; `0` desativa o semáforo. Sem coordenação entre workers. |
| `PDF_IMAGE_DPI` | 350 | 120–350, PDF de OS. |
| `PDF_IMAGE_JPEG_QUALITY` | 95 | 70–95, PDF de OS. |
| `PDF_REMOTE_MEDIA_MAX_MB` | 100 | 1–100, leitura remota de mídia no exportador de OS. |
| `RELATORIO_PDF_DETALHE_MAX_ROWS` | 300 | 50–2000, linhas de detalhe no relatório. |
| `RELATORIO_COLETA_IMAGENS_MAX_EXPORT_ITEMS` | 40 | Quantidade máxima no fluxo de coleta de imagens. |
| `RELATORIO_COLETA_IMAGENS_PDF_ASYNC_WORKERS` | 1 | Mínimo 1, threads por processo. |
| `RELATORIO_COLETA_IMAGENS_PDF_IMAGE_DPI` | 150 | 120–350. |
| `RELATORIO_COLETA_IMAGENS_PDF_JPEG_QUALITY` | 78 | 70–95. |
| `RELATORIO_COLETA_IMAGENS_PDF_IMAGE_SPOOL_MB` | 1 | 1–8, limiar do buffer temporário de imagem. |
| `RELATORIO_COLETA_IMAGENS_PDF_REMOTE_PREFETCH` | 0 | 0–3, controle de prefetch do exportador. |

Fontes: [exportador de OS](../app/modules/piloto_os/exporters.py), [rotas](../app/modules/relatorios/routes.py) e [exportadores de relatórios](../app/modules/relatorios/exporters.py). São limites de processos e exportações específicos, não um limite global de memória ou upload.

## Gunicorn e watchdog

| Variável | Padrão | Onde é lida |
| --- | ---: | --- |
| `GUNICORN_TIMEOUT` | 180 | Procfile, segundos. |
| `WEB_CONCURRENCY` | 2 | Procfile, workers. |
| `GUNICORN_THREADS` | 4 | Procfile, threads por worker. |
| `GUNICORN_MAX_REQUESTS` | 700 | Procfile, reciclagem do worker. |
| `GUNICORN_MAX_REQUESTS_JITTER` | 100 | Procfile, variação na reciclagem. |
| `WATCHDOG_HEALTH_URL` | Obrigatória no script | URL de saúde; o workflow define o destino operacional. |
| `RENDER_DEPLOY_HOOK_URL` | Obrigatória no script | Segredo que permite disparar deploy. |
| `WATCHDOG_EVENT_URL` | Ausente | Destino opcional para registrar eventos. |
| `WATCHDOG_EVENT_TOKEN` | Ausente | Segredo compartilhado entre workflow e receptor de eventos. |
| `WATCHDOG_RETRIES` | 3 | Tentativas iniciais. |
| `WATCHDOG_RETRY_DELAY_SECONDS` | 20 | Intervalo inicial. |
| `WATCHDOG_TIMEOUT_SECONDS` | 10 | Timeout HTTP. |
| `WATCHDOG_RECOVERY_RETRIES` | 45 | Tentativas de recuperação. |
| `WATCHDOG_RECOVERY_DELAY_SECONDS` | 10 | Intervalo durante recuperação. |

O [workflow](../.github/workflows/render-watchdog.yml) usa GitHub Actions vars/secrets, que são um ambiente diferente do `.env` da aplicação. Confira também o [script](../scripts/render_watchdog.py). Executá-lo manualmente pode disparar um deploy.

## Dados de demonstração

`scripts/seed_redgps_tracking_demo.py` exige `IJA_ALLOW_TEST_SEED=1` e usa `NEON_TEST_DATABASE_URL` ou `DATABASE_URL_TEST`, exigindo que o destino seja uma URL PostgreSQL. As variáveis apontam para um banco de teste escolhido pelo operador; seu nome não garante isolamento. Outros seeds não possuem a mesma proteção. Consulte a classificação dos scripts em [operação](operacao.md) antes de executá-los.
