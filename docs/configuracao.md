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
| `VIGILANCIA_PREVIEW_ENABLED` | `0` | Libera a prévia provisória de CSV focal/LIRAa para administradores autorizados, sem persistência. Ver [guia de validação](vigilancia-validacao-inicial.md). |
| `IJA_CREATE_ALL` | Inativo | Somente o valor `1` aciona `db.create_all()` ao executar `run.py` diretamente; não substitui Alembic. |
| `USER_PRESENCE_UPDATE_INTERVAL_SECONDS` | `300` | Intervalo de atualização de presença. Não é o timeout da sessão. |
| `AUDIT_RETENTION_MAX_RECORDS` | `15000` | Limita quantidade de registros de auditoria; não expressa dias de retenção. Deve ser inteiro. |
| `AUDIT_SKYBOX_INTERVAL_SECONDS` | `60` | Intervalo de consulta da fila de auditoria no banco; consultar não implica enviar ao Skybox. |
| `AUDIT_SKYBOX_BATCH_MAX_RECORDS` | `1000` | Máximo de eventos por lote e volume que libera o envio, separado por prefeitura e limitado também a 4 MiB. |
| `AUDIT_SKYBOX_BATCH_MAX_WAIT_SECONDS` | `300` | Espera máxima para acumular um lote menor, verificada no próximo ciclo do trabalhador. |

A porta de `run.py` é fixa em **5001**. Não existe leitura de `PORT` nesse arquivo. `APP_ENV` não seleciona configuração Flask nem desliga tarefas. Não existe suporte atual a `IJA_AUTO_DB_MIGRATE`: o Procfile executa migrações em toda inicialização.

## Proteção de login

Os três acessos compartilham limite por conta e origem, com bloqueio temporário e histórico. O recurso vem habilitado no Config e exige a migração `b82e0d5f314c`. Confira padrões, configuração de proxies e liberação pelo desenvolvedor em [Proteção de login](protecao-login.md).

## Validade das senhas

O DEV define o prazo em **Painel Dev → Proteção de login**. O padrão inicial é de 90 dias, configurável de 1 a 365, armazenado no banco e aplicado aos três acessos. Contas antigas só entram na regra na próxima troca de senha. A migração `d94f2a7610be` é necessária. Consulte [validade das senhas](expiracao-senhas.md).

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

## Rastreamento OLLOG / RedGPS

Configure `REDGPS_BASE_URL`, `REDGPS_API_KEY`, `REDGPS_USERNAME` e
`REDGPS_PASSWORD` somente no ambiente do servidor. `REDGPS_SYNC_ENABLED=true`
habilita a coleta; `REDGPS_POLL_INTERVAL_SECONDS=60` define o intervalo, com
mínimo de 60 segundos. Execute as migrações antes de ativar.

O painel `/veiculos/rastreamento` abre com as posições e a primeira rota já salvas,
sem esperar pela API externa. Novas leituras são consultadas em segundo plano
enquanto estiver visível, fora do modo de demonstração e da reprodução de trajetos.
O controle persistido e o lock transacional do PostgreSQL evitam consultas
duplicadas entre processos. Falhas também respeitam o intervalo, e as últimas
posições válidas são preservadas. Tokens ficam em memória e são renovados antes
de seis horas ou após a recusa de um token. Credenciais não são enviadas ao navegador.

As posições são associadas por placa normalizada apenas a veículos já cadastrados,
ativos e sem ambiguidade. Não são criados veículos nem alterados equipe, prefeitura
ou quilometragem cadastral. As permissões existentes do painel continuam valendo.
Datas do provedor são solicitadas em UTC; o painel usa America/Sao_Paulo. O odômetro
de `getdata` é convertido de metros para quilômetros. Veículos sem posição válida
continuam na lista sem marcador no mapa.

O histórico reúne as posições coletadas pelo IJA, sem duplicar a mesma leitura;
o painel busca o veículo e o período selecionados. O Google Maps já configurado em
`KEY_API_GOOGLE_MAPS` é o mapa principal: marcadores mostram veículo, condutor e
velocidade do último reporte; linhas mostram as coordenadas recebidas em ordem.
O mapa alternativo é usado quando o Google está indisponível. Não são utilizadas
rotas sugeridas pelo Google para representar percursos executados. A telemetria
mostra velocidade, ignição, odômetro, baterias, satélites e sinal GSM enviados pelo
aparelho; valores ausentes ou `-1` permanecem desconhecidos. A bateria do rastreador
é exibida na unidade informada pelo aparelho, sem presumir porcentagem. Alertas,
geocercas e outros sensores ainda não são sincronizados.

Para coletar sem manter o painel aberto, execute **uma instância** do worker no
ambiente configurado (supervisionado pelo serviço de hospedagem em produção):

```sh
python scripts/sync_redgps.py --watch
```

O worker pré-carrega as rotas de hoje, além das posições. Em `--watch`, também
recupera o dia anterior ao iniciar e na virada do dia; depois atualiza o histórico
a cada `REDGPS_HISTORY_SYNC_INTERVAL_SECONDS` (padrão 300 segundos, mínimo 60).
Use `--positions-only` para manter apenas a coleta de últimas posições.
Sem `--watch`, faz uma única passagem de posições e rotas, imprimindo
somente metadados e contagens. O `.env` local não configura o ambiente hospedado;
nesse ambiente, configure as variáveis e publique o código/migração separadamente.

### Condutor, rotas e conferência dos logs

Antes de publicar esta versão, aplique a migração `a3e5c7d901b2`, que acrescenta
`condutor_nome` e `encerrado_em` a `logs_veiculo` e `telemetria` a
`rastreamento_posicoes`. O Alembic mantém os dados antigos;
o downgrade remove somente essas três colunas. O teste de ida e volta usa SQLite
descartável; valide a migração no PostgreSQL de homologação antes da produção.

Nos novos turnos individuais, o nome do piloto/supervisor é preservado no log.
O acesso compartilhado `equipe_oceano` exige informar quem conduz ao abrir o turno.
O fechamento normal ou a retirada do veículo de operação registra o horário de
encerramento em Brasília. Corrigir um log antigo não inventa um horário de retorno;
reabrir pela correção de KM limpa o horário anterior. O responsável pelo cadastro
do veículo e o nome da equipe não são tratados como identidade do motorista.

A lista inicial e o destaque acima do mapa identificam, em campos separados, o
responsável cadastrado e o **condutor do PLOA**, que é o piloto titular vinculado
à equipe do veículo. Esse condutor aparece mesmo sem um turno aberto. Sem titular,
a tela informa a ausência do vínculo. O responsável usa o supervisor vinculado ou
o nome textual dos cadastros antigos. Busca e CSV da frota incluem os dois nomes.
Ao abrir um novo turno, o servidor copia o nome do titular do PLOA para
`condutor_nome`, sem aceitar um nome diferente enviado pelo formulário. Essa cópia
permanece no histórico quando o titular muda. Logs antigos conservam os nomes
registrados; não recebem retroativamente o nome do titular atual. O Flashback e
a conferência exibem a identificação gravada em cada turno. Os vínculos seguem
os veículos autorizados e, para piloto/equipe, os logs do ator.

O vínculo entre ponto e log usa veículo e intervalo de abertura/fechamento, com
GPS em UTC e turnos em Brasília. A conferência por turno calcula **KM GPS menos
KM declarado**, com tolerância de **2 km ou 5% do KM declarado**, o maior valor.
Os logs e o KM cadastral não são alterados pela conferência. É possível abrir o
log a partir do rastreamento, ver seu trecho e voltar ao mapa a partir dos logs.

O resumo separa KM coletado, KM dos logs encerrados dentro do período, velocidade
máxima medida, pontos sem log, diferenças e casos inconclusivos. A distância soma
incrementos válidos do odômetro. Sem odômetro, usa segmentos retos entre coordenadas
como estimativa, que não valida o KM do log. Lacunas maiores que 5 minutos ou três
intervalos de coleta (o maior) e saltos GPS acima de 200 km/h interrompem os
trechos no mapa e no KML. Uma falha apenas no odômetro invalida a distância daquele
trecho para a conferência, mas mantém a geometria GPS válida. Leituras isoladas
aparecem como pontos, sem inventar uma linha entre lacunas. Leituras fictícias não se misturam
às leituras reais de um mesmo veículo e não validam logs reais.

Logs sem fechamento conhecido, abertos, sobrepostos, parcialmente fora do período
ou sem cobertura suficiente ficam **inconclusivos**. Turnos que atravessam a
meia-noite podem ser conferidos quando o período inclui o turno inteiro.
A presença de amostras não
comprova cobertura integral. A velocidade antiga é identificada como última
leitura; o painel mantém o limiar de 15 minutos para marcar posição antiga.
CSV de frota, trajeto e conferência incluem condutor; o trajeto inclui horário e
log associado. Dados ausentes permanecem vazios, sem substituir velocidade por zero.

### Recuperação do histórico do provedor

O polling de `getdata` recebe apenas a última leitura por veículo. Para recuperar
os pontos intermediários, a seleção do veículo abre **Rotas percorridas** e
consulta primeiro os trajetos já persistidos. A atualização via `history/get`
ocorre automaticamente em segundo plano. O navegador envia `background: true`
a `/veiculos/rastreamento/historico`; a resposta HTTP 202 inicia ou consulta o
mesmo trabalho por veículo e período, sem manter a requisição presa à API.
Cada worker usa uma fila limitada, e os locks PostgreSQL coordenam os processos.
O navegador consulta o progresso e os pontos persistidos enquanto aguarda. O botão
manual de importação foi removido.
O filtro **De / Até** aceita data e horário, inclusive períodos que atravessam dias,
com limite de 15 dias. O minuto final é incluído. **Hoje** restaura o dia atual.
O mesmo intervalo é usado no mapa, na telemetria, no Flashback e nas exportações.
O Flashback mantém o trajeto desenhado e move somente o marcador, preservando o
zoom. **Pular paradas e lacunas** comprime os intervalos sem deslocamento ou sem
leituras; desmarque para respeitar todos os intervalos na velocidade selecionada.
Os horários originais e as exportações continuam preservados. Uma atualização
iniciada antes da reprodução não interrompe o Flashback. Sem rota no período, o
mapa pode mostrar a última posição recebida, com rótulo explícito; isso não habilita
uma reprodução inexistente.
Pontos amostrados, a linha do trajeto e os marcadores de parada são clicáveis.
O modal mostra a leitura original, a identificação gravada no turno, o titular
atual do PLOA, o responsável e links autorizados para os logs. Paradas são grupos
de leituras com velocidade de até 1 km/h, em um raio de 40 m, com pelo menos
1 minuto e sem lacunas de comunicação. A duração é apenas a observada entre
amostras. Intervalos de ignição só são classificados como ligada/desligada quando
as duas leituras adjacentes concordam; transições permanecem não determinadas.
A aba Street View consulta imagens até 80 m do ponto usando a chave Google Maps
existente, somente ao ser aberta. O panorama permanece no modal; se indisponível,
há mensagem e um link para o Google Maps. As imagens não são tratadas como registro
do momento do deslocamento. Os arquivos deste módulo usam versão por data de
modificação na URL, evitando reutilizar JavaScript antigo após uma atualização.
O gráfico de velocidade usa horários reais e escala proporcional em km/h, sem
cortar velocidades acima de 60 km/h. Lacunas e valores ausentes interrompem a
linha; o controle abaixo permite consultar cada leitura.
Consultar `/veiculos/rastreamento/dados` com `cached=1`, `vehicle_id`, `start` e `end`
lê os trajetos do banco sem esperar pelo provedor; a resposta identifica o intervalo
e quais veículos tiveram seu histórico carregado. `date` continua aceito para
links antigos de um único dia.
É necessário habilitar `REDGPS_SYNC_ENABLED` no servidor. A consulta usa o mesmo
escopo de veículos do painel, exige sessão e CSRF e não altera logs. Consultas
repetidas têm cache por veículo/período no navegador e por worker; o lock do
PostgreSQL impede importações simultâneas. Consultas antigas são canceladas e
respostas atrasadas são descartadas quando a seleção muda. Se outra coleta estiver
ocupando a integração, há novas tentativas automáticas. O percurso salvo continua
disponível para reprodução durante a atualização. Falhas preservam o histórico
anterior; pontos novos são gravados em lote, sem duplicar leituras.

`REDGPS_HISTORY_TIMEZONE` define o fuso do histórico, com padrão
`America/Sao_Paulo`. A integração consultada em 12/11/2026 retornou horários
coerentes com UTC−3; outro provedor/conta deve confirmar seu fuso. O campo `gmt`,
quando presente, é conferido contra o fuso configurado: discrepâncias rejeitam a
leitura em vez de deslocar silenciosamente o trajeto. O Flashback segue os
horários reais das amostras, permite pausar e mover o controle e oferece 1×,
30×, 60× (padrão) e 120×. O detalhe inferior passa a mostrar a telemetria e o
condutor do ponto reproduzido; o destaque superior permanece no turno atual.

Para recuperação pelo terminal, o worker também dispõe de:

```sh
python scripts/sync_redgps.py --history-date 2026-11-11 --history-timezone "FUSO_CONFIRMADO_COM_OLLOG" --plate ABC1D23
```

Substitua o fuso por um identificador IANA confirmado com a OLLOG (por exemplo
`America/Sao_Paulo` ou `UTC`). Esse parâmetro é obrigatório porque a documentação
de histórico não oferece `UseUTCDate`; o código não presume o fuso das leituras.
O comando consulta um dia de Brasília, convertendo o período para o fuso informado.
Sem `--plate`, recupera a frota ativa cadastrada. Pode repetir `--plate`.

A associação exige placa e dispositivo sem ambiguidade, tanto na consulta atual
como nos registros históricos. Datas, coordenadas, placa e dispositivo são
validados; tentativas repetidas não duplicam leituras do histórico nem do polling.
Uma falha do provedor desfaz a importação inteira. O comando não altera a última
posição, o condutor ou a quilometragem dos logs. Atualize o painel depois da coleta.

Para operação diária, supervisione o worker contínuo no servidor e programe a
recuperação de cada dia encerrado no agendador da hospedagem. Essa infraestrutura
não é ativada por abrir a tela nem por alterar o código local. A RedGPS recomenda
seu Web Service genérico para receber todos os reportes continuamente; essa
recepção por push ainda exige configuração e implementação próprias.

Referências: [autenticação](https://docs.redgps.com/books/webservice/page/metodo-de-autenticacion-gettoken/es),
[posições](https://docs.redgps.com/books/webservice/page/datos-de-unidades-getdata/es),
[histórico](https://docs.redgps.com/books/webservice/page/datos-historicos-equipo-historyget/es),
[linhas no Google Maps](https://developers.google.com/maps/documentation/javascript/shapes#polylines).

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
| `ACOES_PUBLICAS_ENABLED` | `0` | Habilita o editor e a consulta pública de ações após a migração `a73e5c9b204f`. Consulte [o fluxo e as permissões](acoes-publicas.md). |

Fontes: [skybox.py](../app/shared/skybox.py), [rotas de OS](../app/modules/piloto_os/routes.py). Não assuma que os timeouts WebDAV de OS configuram todos os consumidores Skybox. Os arquivos locais são resolvidos em `upload-files/`; não existe variável `UPLOAD_FOLDER` lida pelo [helper atual](../app/shared/uploads.py).

## Dropbox e IA

Azul é o nome da inteligência artificial apresentado aos usuários em todos os módulos. Novas funções de IA devem usar essa identidade nas telas, botões e mensagens, com instruções e permissões específicas por módulo. OpenAI e Gemini são provedores técnicos; seus nomes permanecem nas configurações e registros de diagnóstico. A restrição a saúde aplica-se à Azul do Portal do Cidadão, não à análise de currículos ou à importação de planilhas.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` | Ausentes | Backup e armazenamento de currículos do banco de talentos. |
| `PROJECT_NAME` | `backup` | Prefixo do arquivo de backup. |
| `APP_ENV` | `prod` | Parte do nome do backup. |
| `GEMINI_API_KEY` | Ausente | Normalização de importação de drones. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modelo preferido no código, com tentativas alternativas implementadas no serviço. Não comprova disponibilidade do modelo no provedor. |
| `OPENAI_API_KEY` | Ausente | Chave compartilhada pela Azul e pela análise de currículos. |
| `OPENAI_CHAT_MODEL` | `gpt-6-luna` | Modelo da Azul e padrão para currículos. |
| `OPENAI_TALENT_MODEL` | Vazio | Opcional: modelo próprio para currículos, compatível com PDFs e respostas JSON estruturadas na Responses API. |

Currículos são armazenados no Dropbox e enviados à OpenAI para extrair o perfil profissional, com `store=False` e sem pesquisa web. O perfil deve ser conferido por uma pessoa; a IA não atribui nota, ranking ou decisão de contratação. As instruções desse módulo são independentes das restrições de saúde do chat público da Azul. Perfis antigos continuam disponíveis; o botão de reprocessamento usa a nova integração. A coluna histórica `gemini_modelo` guarda o modelo utilizado, inclusive OpenAI, sem exigir migração do banco. A importação de drones continua usando Gemini.

A chamada tem timeout de 90 segundos, sem repetição automática. Em caso de falha, o PDF permanece salvo e pode ser reprocessado na tela do candidato. Erros do provedor são apresentados de forma genérica, sem conteúdo do currículo ou credenciais.

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


## Azul — ajuda interna contextual

O layout interno (`base.html`) apresenta a Azul aos usuários autenticados com acesso ao endpoint `/api/azul/ajuda`. A Central TI controla esse acesso por área. Os antigos endpoints de FAQ continuam funcionando, agora com exigência de consulta em vez de edição.

A Azul usa `OPENAI_API_KEY` e `OPENAI_CHAT_MODEL`, sem configuração adicional. `AZUL_HELP_DAILY_LIMIT` (padrão 500) limita chamadas por dia no host; também há limite de oito chamadas por minuto por usuário. A quota fica em `instance/azul_help_quota.sqlite`, compartilhada pelos workers do host, sem armazenar mensagens. Para múltiplos hosts, as quotas são independentes.

O servidor calcula perfil, capacidades efetivas da Central TI e atalhos para telas permitidas a cada pergunta. Sem um perfil configurado na Central TI, só confirma os poucos atalhos com verificações legadas explicitamente mapeadas; não apresenta a aproximação do catálogo como autorização. Links vêm do servidor, nunca da resposta do modelo. A página é identificada somente se corresponder a um atalho permitido, sem enviar parâmetros, IDs de registros ou o conteúdo da tela.

A Azul consulta o conteúdo dos guias locais. Não pesquisa na web e não modifica registros nem permissões. As consultas operacionais disponíveis são a prévia de exportação e o resumo de atenção descritos abaixo. Limites de prefeitura, equipe, empresa e estado dos registros continuam nas rotas de negócio. O histórico visual mantém até 40 mensagens no sessionStorage da aba por até 24 horas, separado por usuário e sessão de login; até seis mensagens são enviadas como contexto. Login/logout rotacionam a identificação do histórico. Limpar a conversa cancela a requisição e descarta o histórico salvo. Navegação preserva mensagens, atalhos e painel aberto; prévias de download não persistem tokens e precisam ser solicitadas novamente. Uma resposta interrompida pela navegação não é reenviada automaticamente. A chamada usa `store=False`, timeout de 30 segundos e nenhuma repetição automática. Falha, resposta incompleta, ausência de chave ou quota esgotada ativam o guia local, identificado na interface, sem tratar orientações genéricas como permissões efetivas.


### Exportação pela Azul (Diretor e DEV)

Somente `diretor` e `dev` podem solicitar arquivos no chat. O servidor também exige acesso à exportação de consultas (`prefeitura.relatorios.exportar`) e à exportação da fonte: `prefeitura.solicitacoes.exportar` para solicitações ou `prefeitura.relatorios.exportar` para OS. As permissões e o papel são verificados na prévia e novamente no download. Outros perfis continuam usando a ajuda, sem receber a ferramenta de exportação ou o botão de geração.

A IA pode chamar apenas `preparar_exportacao`, que recebe uma definição restrita, sem SQL, URLs, código ou fórmulas arbitrárias. São suportados Excel/PDF de solicitações e OS municipais, com filtros de início, fim, status da solicitação e bairro. O período filtra agendamento nas solicitações e aplicação nas OS. OS Agro e filtros não suportados exigem esclarecimento; não são substituídos silenciosamente. As colunas são definidas pelo servidor. Nenhum registro é enviado ao modelo.

A prévia apresenta fonte, formato, período, campo de data, filtros, colunas e contagem exata. `POST /api/azul/exportar` só gera o arquivo com confirmação explícita e token assinado, vinculado ao usuário e válido por dez minutos. O servidor refaz a consulta com os limites de prefeitura/região existentes e compara o conteúdo com a prévia; alteração de dados ou de acesso exige nova prévia. Os limites existentes são 10.000 registros para Excel e 2.000 para PDF, sem truncamento. Uma consulta vazia não oferece download.

Arquivos são baixados diretamente, com `Cache-Control: private, no-store`, sem e-mail, WhatsApp ou upload. A assinatura comprova a definição e o resultado aprovado, não concede permissão. O usuário pode cancelar a prévia; limpar a conversa impede downloads pendentes de serem iniciados pela interface.

O download tem limite de três tentativas por minuto e 50 por dia por usuário, compartilhado pelos workers do host via SQLite. A quota é independente das chamadas à IA; falha ao verificar a quota bloqueia a geração. Em múltiplos hosts, os limites continuam independentes e exigem armazenamento central para uma quota única.

Diretor e DEV são perfis globais na política atual de escopo (`GLOBAL_ADMIN_USER_TYPES`), portanto podem consultar várias prefeituras; ter `prefeitura_id` preenchido não restringe esses perfis. A Azul reutiliza essa regra, sem conceder acesso adicional. Para produção, habilite `CSRF_PROTECTION_ENABLED=1` com chave secreta fixa, desative debug e utilize o servidor de produção. O envio do cabeçalho CSRF no widget só é validado quando essa proteção está habilitada.

### Resumo operacional da Azul

“Minha atenção hoje” e perguntas equivalentes consultam as solicitações municipais pela mesma consulta e permissões do painel administrativo. O resumo conta pendentes/em análise de hoje, pendentes/em análise com agendamento passado e aprovadas sem equipe (qualquer data), com até dois exemplos por grupo. Usa o dia de São Paulo, pode haver sobreposição entre grupos e não infere atraso de execução. Links são criados pelo servidor para o painel filtrado por protocolo.

A resposta é montada no servidor sem enviar registros ao provedor. A ferramenta `consultar_atencao_hoje` permite reconhecer outras formulações da pergunta, mas também retorna o resumo diretamente, sem segunda chamada ao modelo. O botão e as frases diretas funcionam sem chave de IA. Cada consulta verifica novamente acesso e limites de prefeitura/região, usa a quota da ajuda e não altera registros. Outros módulos, períodos e filtros ainda não são cobertos.

O resumo “Minha atenção hoje” é exclusivo para cadastros com `trabalha_oceano_azul=True`, além da permissão para consultar o respectivo painel. O servidor aplica essa restrição ao botão, à ferramenta da IA e à consulta direta; um campo enviado pelo navegador não concede acesso. Para `dev`, consulta falhas HTTP nas últimas 24 horas e erros 5xx nos últimos sete dias seguindo `_failure_filter` do Painel Dev, mais bugs técnicos ativos quando houver acesso à tela de bugs. Não envia logs, descrições ou registros à IA. Outros perfis internos continuam recebendo o resumo municipal. Essa restrição não muda as regras dos relatórios ou das demais telas.

Para bases grandes, o resumo municipal retorna até dois exemplos por grupo e atalhos “Ver todas (N)”. Esses atalhos abrem o painel com `atencao` e `referencia`, inicialmente em páginas de 25 registros. Contagem e listagem compartilham os mesmos critérios. A referência fica fixa no link; os dados são atualizados ao abrir. A seleção aparece em um aviso no painel, é preservada na paginação, nos filtros adicionais e no Excel do painel, e pode ser limpa. O chat não carrega milhares de registros nem os envia ao modelo.

### Busca conversacional de solicitações

A ferramenta `buscar_solicitacoes` transforma pedidos em filtros validados de status, bairro exato (sem diferenciar maiúsculas), endereço, protocolo/ID e datas de agendamento. Exige permissão do painel administrativo a cada execução e reutiliza o escopo municipal/regional da listagem. Retorna contagem e link local paginado, sem enviar registros à IA, executar código gerado ou alterar dados. O filtro de bairro também aparece no painel e é preservado no Excel. Esta primeira versão não busca OS, Agro, canceladas ou critérios fora da ferramenta; nesses casos a Azul deve esclarecer o alcance. A busca não concede o resumo de atenção exclusivo para funcionários da Oceano Azul e não exige permissão de exportação. Requer disponibilidade da IA para interpretar a frase; os filtros convencionais do painel continuam disponíveis.

### Mini-drone, guia prático e voz da Azul

O perfil **dev** pode administrar a AZUL em **AZUL → Configurações** (`/azul/configuracoes`): som global, contextos separados, modelos, limites, tarifas/câmbio e consumo de novas interações. Consulte [Administração da AZUL](azul-administracao.md) para persistência, medição, reservas de orçamento e aplicação dos controles. As variáveis de ambiente abaixo continuam como padrões e desligamentos de emergência.

O mini-drone identifica a Azul nas telas internas autorizadas, na página `/azul`, nas páginas do Portal do Cidadão e no aplicativo web `/m/`. No portal, também aparece em boletins, contatos, relatos de saúde, recibos, ações públicas, download do aplicativo e privacidade. Ele acompanha o cursor quando está sob o ponteiro, acena ao abrir a conversa e muda de expressão enquanto a resposta ou o áudio são preparados. Durante a reprodução, a boca se anima. A preferência de redução de movimento do dispositivo é respeitada. O mascote não abre o chat nem inicia áudios automaticamente.

Arraste o botão do mini-drone com o mouse ou pelo toque para reposicioná-lo. Um clique ou toque sem arrastar abre a conversa. Com o botão em foco, **Shift + setas** também move o mascote. A posição proporcional fica no `localStorage` do navegador e é reutilizada entre páginas; os limites da tela mantêm o botão acessível. No computador, o painel acompanha a posição escolhida. No celular, o botão fica oculto enquanto o painel está aberto para preservar o espaço da conversa e do teclado.

Para começar, clique no mini-drone e escolha **Guia prático**. Isso abre **Aprender na prática**, uma sala de treinamento com telas simplificadas e dados fictícios. Escolha um exercício e use o controle destacado: o drone se move até ele e explica a próxima ação. **Ver a Azul demonstrar** executa a sequência somente na simulação; **Pausar demonstração** permite retomar a prática manual. Há controles para voltar, repetir e escolher outro tutorial. A narração de cada etapa continua opcional, no cabeçalho da sala.

O portal oferece três exercícios: relato de foco (sete passos), suspeita de adoecimento (cinco) e leitura do boletim (cinco). A sala interna acrescenta trilhas autorizadas de solicitações, OS municipais, clientes, orçamentos, contratos, OS Agro, talentos e consulta financeira. O servidor seleciona essas trilhas pelos módulos dos atalhos verificados da conta; parâmetros do navegador não concedem módulos. Pessoas, registros, município, números e localização dos exercícios são inventados. Não há inserção de dados de demonstração no banco operacional.

**Guia rápido em texto**, no cabeçalho da sala, mantém as orientações anteriores no chat. Use **Próximo**, **Voltar** e **Concluir** para percorrê-las. Os atalhos e as ferramentas são montados no servidor conforme o acesso atual. Há orientações para solicitações, OS, clientes, orçamentos, contratos, talentos e financeiro quando a página corresponde a um atalho autorizado; em outras telas, o guia explica como encontrar recursos e pedir ajuda contextual. **Perguntar à Azul** abre uma conversa sobre a etapa. Os treinamentos são oferecidos somente quando permitidos.

A sala é servida por `GET /azul/tutorial?publico=publico` ou `publico=sistema`; a segunda opção exige login e o acesso atual à ajuda da Azul. O documento abre em um iframe com `sandbox="allow-scripts"`, sem origem compartilhada, navegação externa ou envio de formulários. Sua política CSP bloqueia conexões de rede e submissões; os exercícios só alteram o estado em memória do próprio documento. Campos usam opções fixas, sem solicitar dados pessoais reais. Fechar a sala descarta o exercício. Não há chamadas ao modelo para conduzir o tutorial. Somente a narração opcional usa o serviço de voz existente: o documento informa a etapa ao contêiner, que valida a origem da mensagem pelo iframe atual e usa uma oferta assinada do servidor. O áudio para ao trocar de etapa ou fechar a sala. A sala precisa de conexão para o carregamento inicial; os exercícios não fazem consultas operacionais.

O guia público explica os caminhos de relato de foco, suspeita de adoecimento, boletim e contatos publicados, sem ferramentas internas. Os dados pessoais continuam nos formulários próprios. Na página inicial do portal, **Registrar relato** abre o formulário guiado existente; nas demais páginas, leva ao formulário. No aplicativo web, a aba Azul abre o mesmo assistente flutuante, sem criar uma segunda conversa. Essas alterações se aplicam ao site e à PWA; não geram um novo APK nativo nem alteram os canais externos.

Nas novas respostas, **Ouvir resposta** solicita a narração; no guia, use **Ouvir esta etapa**. O botão vira **Parar preparação** durante a geração e **Parar áudio** durante a fala. Fechar o chat, limpar a conversa, iniciar outra pergunta, trocar a etapa do guia, ocultar a aba ou navegar interrompe o áudio. O texto continua disponível se a voz falhar. A voz é identificada na interface como gerada por IA.

O campo de escrita reúne os controles à direita, sem seletor de modelo. O ícone de microfone permite **Ditar mensagem**: a transcrição preenche o campo para revisão e só é enviada quando a pessoa confirmar pela seta ou por Enter; Shift+Enter insere uma nova linha. O botão azul com ondas inicia **Conversar por voz** e dá lugar à seta quando há texto digitado. **Perguntas e atalhos** fica em uma sanfona fechada por padrão, tanto no portal quanto na ajuda interna e na página da AZUL.

Ao iniciar a conversa por voz, a área de mensagens dá lugar a uma tela de ligação dentro do próprio chat, com o drone centralizado e animado durante a escuta, o processamento e a reprodução. **Enviar fala** conclui a captura; **Falar agora** interrompe a resposta e abre outra fala. **Encerrar** desliga o microfone, cancela a resposta em andamento e restaura o chat e seu histórico. O ditado mantém o campo de escrita, sem abrir a tela de ligação. As animações respeitam a preferência de reduzir movimento do navegador.

Após a permissão do microfone, a AZUL inicia com uma saudação falada e então abre a escuta. Saudação e orientação para voltar ao escopo usam clipes fixos, gerados com a voz feminina da AZUL e servidos pelo próprio sistema; sua reprodução não chama o provedor. Perguntas bloqueadas ou ambíguas recebem essa orientação em voz e a chamada retoma a escuta, mantendo o bloqueio antes do modelo e da narração paga. Durante qualquer reprodução, a captura fica desligada para não transcrever a própria voz da AZUL. As demais respostas continuam usando as ofertas de narração assinadas do servidor e tocam automaticamente durante a chamada.

Além dos dois clipes da chamada, a biblioteca `app/static/audio/azul-falas/` contém 12 falas gravadas: apresentação da AZUL, cumprimento, agradecimento, boas-vindas do portal, suas quatro dúvidas frequentes e quatro orientações comuns do guia interno. O texto deve corresponder exatamente ao roteiro e à voz/modelo registrados no manifesto. Quando corresponde, a oferta inclui o endereço do áudio estático e o navegador o reproduz sem chamar o endpoint de geração. As quatro dúvidas frequentes também têm resposta local no servidor, mesmo para clientes que não passam pelos atalhos da interface. Conteúdo adicional ou fora do escopo não é tratado como uma dessas perguntas.

Para conferir a biblioteca sem gasto, execute `.venv/bin/python scripts/build_azul_recordings.py`. A opção explícita `--generate` grava somente roteiros ausentes ou alterados e tem custo de geração uma única vez; `--only apresentacao cumprimento` restringe os itens. A publicação de cada clipe exige a mesma conferência da transcrição contra o roteiro usada nas respostas dinâmicas. O manifesto só inclui instruções genéricas, nunca registros ou informações de usuários. O aplicativo móvel guarda esses clipes públicos em seu cache; respostas privadas não entram nele.

Áudios novos também são reutilizados por conteúdo durante até dez minutos dentro do mesmo processo, usuário, sessão e escopo de acesso. O cache usa chaves HMAC, voz/modelo e versão de interpretação, com limite total de 16 MiB e 32 áudios por processo; não grava respostas dinâmicas em disco. Entradas vencidas são removidas na próxima consulta ao cache. Assinatura, prazo do token, sessão e permissões são verificados antes de qualquer consulta. Gerações simultâneas do mesmo áudio não são duplicadas. Falas gravadas e acertos de cache não consomem a quota de geração; falhas continuam contando como tentativas e nunca entram no cache. Novos textos e transcrições ainda consomem a API, sujeitos às quotas existentes.

**Conversar por voz** ativa o microfone após a permissão do navegador, em HTTPS ou localhost. Fale normalmente e faça uma pausa: a fala é transcrita e enviada ao mesmo chat protegido do texto. A AZUL responde em áudio e retoma a escuta. **Enviar fala** encerra a captura sem esperar o silêncio; **Interromper e falar** cancela a espera ou a reprodução e inicia outra fala. **Encerrar voz**, fechar ou limpar o chat, abrir o tutorial, sair da tela ou ocultar a aba libera o microfone. Sem fala por oito segundos, a sessão para sem transcrição paga. A sessão também termina após cinco minutos ou dez falas. O modo funciona por turnos; não abre uma sessão de IA livre diretamente entre o navegador e o provedor.

Cada envio é um WAV PCM mono de 16 kHz, validado no servidor, com até 30 segundos e 1 MiB. A captura usa AudioWorklet local com alternativa compatível para navegadores restritos. Áudio e transcrição são processados em memória; a transcrição aparece como mensagem normal, com a política de histórico do chat. Nunca há gravação automática ao carregar uma página. O navegador não recebe a chave do provedor. A reprodução usa o contexto de áudio ativado pelo clique do usuário, e evita captar a própria resposta enquanto a AZUL fala. A narração é opcional nos tutoriais; a sala de prática continua sem acesso ao microfone.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `AZUL_VOICE_ENABLED` | `1` | Habilita a narração quando `OPENAI_API_KEY` está configurada. `0` desativa a voz. |
| `AZUL_VOICE_MODEL` | `gpt-realtime-2.1-mini` | Modelo de áudio da integração Realtime no servidor. |
| `AZUL_VOICE` | `marin` | Voz compatível com o modelo configurado; o padrão pede voz feminina suave, calma e conversacional em português brasileiro. |
| `AZUL_CONVERSATION_ENABLED` | `1` | Habilita o botão de microfone quando a voz e a chave da IA estão disponíveis. |
| `AZUL_TRANSCRIBE_MODEL` | `gpt-transcribe` | Modelo de transcrição de cada fala validada; não gera respostas livres. |
| `AZUL_TRANSCRIBE_DAILY_LIMIT` | `200` | Limite diário de transcrições internas por host. |
| `PORTAL_AZUL_TRANSCRIBE_DAILY_LIMIT` | `100` | Limite diário independente de transcrições públicas por host. |
| `AZUL_VOICE_DAILY_LIMIT` | `200` | Limite diário de gerações de áudio por host; `0` bloqueia novas gerações. |
| `AZUL_VOICE_PER_MINUTE` | `6` | Limite por minuto por usuário interno ou origem pública, para permitir turnos curtos sem ampliar os limites diários. |
| `PORTAL_AZUL_VOICE_ENABLED` | `1` | Habilita a narração pública, desde que a voz geral e a chave OpenAI também estejam habilitadas. |
| `PORTAL_AZUL_VOICE_DAILY_LIMIT` | `100` | Limite diário independente de gerações públicas por host; `0` bloqueia novas gerações públicas. |

A narração usa a mesma chave OpenAI da Azul, com cobrança adicional de áudio pelo provedor. Instale as dependências atualizadas de `requirements.txt`, incluindo `websockets==15.0.1`. A integração usa a [Realtime API](https://developers.openai.com/api/docs/guides/realtime-conversations), conforme a migração recomendada para os [modelos antigos de síntese em descontinuação](https://developers.openai.com/api/docs/deprecations). A disponibilidade depende do acesso da conta ao modelo e de créditos do provedor.

A interpretação vocal pede voz feminina macia, cadência tranquila, entonação variada e sotaque brasileiro estável, preservando as palavras aprovadas. Na conversa por microfone, o modelo recebe a orientação de usar até duas frases curtas e 450 caracteres, preservando informações essenciais e fontes. `marin` é uma das vozes recomendadas para qualidade na [documentação da Realtime API](https://developers.openai.com/api/docs/guides/realtime-conversations#voice-options). O ajuste de interpretação segue a [orientação de fala e ritmo da OpenAI](https://developers.openai.com/api/docs/guides/voice-prompting); não altera a velocidade de reprodução do arquivo. Uma configuração explícita de `AZUL_VOICE` no ambiente prevalece sobre o padrão `marin`.

`POST /api/azul/transcrever` exige login, a permissão da Azul e `X-Azul-Chat-Key` da sessão/escopo atuais. `POST /portal-cidadao/transcrever` exige `X-Portal-Chat-Token` da sessão pública. As transcrições têm quotas separadas de respostas e narração: seis tentativas por minuto e 30 por dia por usuário interno; no portal, seis por minuto e 50 por dia por origem e 30 por dia por sessão, além dos limites diários de host. Há no máximo duas operações de áudio simultâneas por processo, compartilhadas com a narração. A transcrição segue o fluxo oficial de [transcrição de arquivos da OpenAI](https://developers.openai.com/api/docs/guides/speech-to-text).

### Identidade e limite de assuntos da AZUL

O nome permanente é **AZUL**, fixado nas instruções de todos os canais. Perguntas de apresentação e cumprimentos têm resposta local, sem chamada ao modelo. O servidor admite somente orientações do sistema e assuntos de saúde, dengue, vigilância e epidemiologia. O chat público mantém suas informações institucionais e contatos publicados, sem ferramentas privadas. No chat interno, dúvidas gerais de saúde usam o contexto público e as fontes oficiais, sem enviar registros internos ao provedor.

Uma triagem local conservadora recusa temas reconhecidamente externos e pede esclarecimento para intenções não reconhecidas antes da geração de texto e da pesquisa web. Ela também limpa trechos fora do escopo no histórico. Pedidos mistos com entretenimento, programação ou outros desvios reconhecidos são recusados integralmente. Respostas curtas de continuidade podem aproveitar o tema permitido anterior; isso não amplia permissões nem concede novas ferramentas. A triagem usa vocabulário e padrões, e não é uma classificação semântica infalível: as instruções obrigatórias do modelo continuam limitando a resposta. Novos temas válidos podem exigir ampliação do vocabulário. Recusas e esclarecimentos não oferecem narração paga automática. Para áudio, a transcrição ainda tem custo, pois ocorre antes de o assunto ser conhecido; a recusa evita a geração da resposta, pesquisa e narração seguintes. Esta regra não altera o processamento especializado de currículos e importação de planilhas fora do chat.

`POST /api/azul/voz` exige login, a mesma permissão de área da ajuda da Azul e um token assinado pelo servidor, válido por dez minutos e vinculado ao usuário, à sessão e ao escopo atual. O navegador não escolhe o texto narrado. São aceitos textos de até 3.000 caracteres; respostas maiores permanecem somente em texto. Tokens de voz não são salvos no histórico da conversa: após navegar, peça uma nova resposta para ouvir a narração. Os tokens das etapas do guia são renovados ao carregar a página.

`POST /portal-cidadao/voz` aceita apenas textos assinados pelo servidor para a sessão pública atual, com validade de dez minutos, e exige o cabeçalho `X-Portal-Chat-Token` da mesma sessão. Sua assinatura é separada da voz interna. As ofertas incluem respostas públicas, orientações fixas e etapas do guia; o navegador não pode enviar texto livre para narração. Os limites públicos são de `AZUL_VOICE_PER_MINUTE` tentativas por minuto (padrão seis) e 50 por dia por origem, 30 por dia por sessão e o limite diário por host. Os identificadores de origem e sessão são armazenados como hashes no SQLite do portal, sem texto ou áudio. A quota pública é independente da conversa e da quota de usuários internos; o limite de duas gerações simultâneas por processo é compartilhado.

Somente o texto da resposta ou da etapa escolhida é enviado ao provedor de voz; não são enviados histórico, ferramentas, planilhas ou linhas originais de consultas. Ao contrário da consulta operacional em texto, ouvir seu resumo envia ao provedor o conteúdo desse resumo. O servidor confere a transcrição retornada contra o texto aprovado, ignorando apenas pontuação, espaços e caixa. Se as palavras ou os números divergirem, ou a resposta estiver incompleta, o áudio não é entregue.

O endpoint devolve WAV com `Cache-Control: private, no-store`. Áudios dinâmicos ficam somente no cache temporário em memória descrito acima. A interface mantém até três clipes em memória para repetir sem nova geração, descartados ao limpar a conversa ou sair da página; gravações públicas também usam o cache normal de arquivos estáticos. Há no máximo duas gerações simultâneas por processo, prazo total de 45 segundos, limite de 8 MiB de PCM e quotas independentes da conversa: `AZUL_VOICE_PER_MINUTE` tentativas de geração por minuto (padrão seis) e 30 por dia por usuário, além do limite diário por host. Reutilizações não gastam essa quota. As quotas ficam no mesmo SQLite da Azul, sem texto ou áudio; em múltiplos hosts, continuam independentes.
