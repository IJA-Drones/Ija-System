# Consulta pública de arboviroses para a prova de conceito

Acesso: **Vigilância → SINAN · Arboviroses**, em `/vigilancia/sinan`. A consulta exige administrador global/prefeitura ou a permissão `prefeitura.vigilancia.consultar` na Central de TI. `SINAN_ENABLED=1` habilita página e API; `0` desabilita ambas. Na mesma tela, **Consulta pública** mantém a paginação e **Dados salvos** reúne importações, exportação e mapa. Os filtros acima valem para ambas as abas.

## Importações e exportações

**Máximo de 100 registros por importação**, tanto pela API quanto pelo CSV. A consulta pública continua com 10 linhas por página; consultar não inicia uma importação automaticamente.

Em **Dados salvos → Importar da API**, a resposta retorna imediatamente e o processamento continua em segundo plano, com **uma importação por vez** por armazenamento compartilhado. A leitura usa páginas de 10, uma pausa de um segundo entre páginas e até 100 registros ou 2 minutos, além da requisição já em curso (timeout de leitura de 45 segundos). Atingir o limite produz um lote **Parcial**, nunca o total do município. Não há continuação automática. Uma nova importação começa no início do filtro e não soma os dados aos lotes anteriores. Cancelamento aguarda a requisição em curso e descarta sua resposta.

O histórico mostra até 10 lotes do usuário, preservando acesso à última importação completa da API. Uma falha ou leitura parcial não substitui esse lote. O andamento só é atualizado automaticamente enquanto a aba está visível; falhas de atualização oferecem tentativa manual. Exportar CSV lê somente o lote selecionado, sem consultar novamente a fonte. A exportação inclui origem, situação, escopo e horário de importação; agregados da API e casos do CSV têm formatos próprios.

**Importar CSV com coordenadas** aceita UTF-8, até 1 MiB e 100 casos. Colunas obrigatórias, nesta ordem: `referencia;doenca;municipio_ibge;ano;semana;classificacao;latitude;longitude`. Todos os registros precisam coincidir com os filtros. Referência deve ser um código sem identificação pessoal; nomes, documentos e endereços não são aceitos como colunas. Classificações: `suspeito`, `confirmado`, `descartado` ou `ignorado`, conforme o arquivo. Coordenadas precisam ser finitas e estar dentro da caixa geográfica do Brasil; a aplicação não confirma endereço ou pertencimento ao município. O arquivo inteiro é validado antes da publicação: 101 linhas ou uma linha inválida impedem a carga, sem publicar parcialmente os casos.

O modelo de São Paulo e Pesqueira contém dois casos **fictícios** identificados como demonstração. Outros municípios recebem cabeçalho vazio. Arquivos reais exigem a confirmação de autorização. A repetição de um CSV idêntico, no mesmo escopo e usuário, reaproveita o lote concluído. Arquivos maiores precisam ser divididos em lotes independentes, sem consolidação automática.

**Ver no mapa** abre o mapa dentro da mesma tela, sob o lote. A API consumida fornece indicadores municipais, sem coordenadas individuais; seu símbolo representa o município de notificação. Apenas o CSV apresenta pontos nas coordenadas fornecidas e filtro por classificação. Não há inferência de casos confirmados a partir de denúncias ou ordens de serviço. A chave Google existente é reutilizada, sem modificar restrições. A renderização real do mapa ainda precisa ser verificada em domínio autorizado: o ambiente local retornou erro de chave e o usuário informou bloqueio de localhost.

### Armazenamento e operação

`SINAN_IMPORT_ENABLED=1` habilita o fluxo; `0` mantém apenas a consulta. O padrão `SINAN_STORAGE_BACKEND=database` usa o PostgreSQL configurado para o IJA, nas tabelas `vigilancia_sinan_lotes` e `vigilancia_sinan_casos`, com transações curtas e no máximo 1.000 lotes. A API persiste somente contagens agrupadas; o CSV persiste os campos normalizados do modelo. Os lotes ficam restritos à conta importadora, inclusive entre administradores. POST exige CSRF; importação/cancelamento usam `prefeitura.vigilancia.editar`, exportação usa `prefeitura.relatorios.exportar` com os pré-requisitos de consulta da Central de TI.

O PostgreSQL coordena um único importador ativo entre processos por trava transacional e índice parcial único. Não há fila durável ou retomada de cargas após reinício: trabalhos sem progresso por 90 segundos são marcados como interrompidos e precisam ser iniciados novamente. Exportações não mantêm transações abertas durante o download. Os limites reduzem consumo, mas não substituem avaliação de carga no ambiente de produção.

O SQLite legado (`instance/sinan/sinan.sqlite` ou `SINAN_STORAGE_PATH`) foi mantido para transferência e uso local explícito com `SINAN_STORAGE_BACKEND=sqlite`. A revisão `c7f2a9d810e4` cria as tabelas no PostgreSQL; o procedimento com backup e verificação dos dados está no [guia de registro de campo](vigilancia-registro-campo.md#sinan-no-postgresql). O caminho de armazenamento não provoca retorno automático ao SQLite se houver falha no PostgreSQL.

## Consulta e paginação

Selecione **uma doença**, **um município** e **um ano**. Estão disponíveis dengue, zika e chikungunya, São Paulo capital e os 15 municípios do CONDOMAR. A seleção inicial é dengue / São Paulo capital / ano atual.

A tabela apresenta até **10 registros por página**, com posição na consulta, município de notificação, semana epidemiológica, classificação original e residência no mesmo município / outro município / não informada. A posição não é um identificador de caso. Nomes, documentos, endereços, números de notificação e outros campos pessoais não são solicitados nem devolvidos ao navegador.

**Próxima** busca o lote seguinte da fonte e substitui as linhas da tabela. **Anterior** recupera a página já consultada em memória. Uma falha mantém a página atual e oferece **Tentar novamente**, na mesma posição. **Interromper** cancela a leitura pendente; **Limpar busca** apaga dados e cache e restaura os filtros. Alterar qualquer filtro também limpa a consulta, e respostas atrasadas são ignoradas. O parâmetro `disease` aceita apenas `dengue`, `zika` ou `chikungunya`; quando omitido, usa dengue.

O rodapé informa a faixa de registros da página e se a leitura ainda é parcial. Não há total de páginas fornecido pela API, portanto ele não é inventado. Se a quantidade for múltipla de 10, uma próxima página vazia confirma o fim: a tela mantém a última página preenchida e desabilita **Próxima**. O limite de um milhão de registros por consulta permanece identificado como parcial.

Os gráficos e contagens ficam em **Indicadores desta página**, inicialmente recolhido; referem-se somente aos registros exibidos, não ao total do município nem ao acumulado das páginas visitadas. **Sobre os dados** reúne as fontes e notas metodológicas. Sem registros, a tabela orienta tentar outro ano e os gráficos ficam ocultos. Uma resposta vazia nunca é apresentada como ausência comprovada de casos.

## Recorte e fonte

São Paulo capital (IBGE 3550308) e os municípios listados pelo [CONDOMAR](https://www.condomar.pe.gov.br/municipios): Alagoinha, Arcoverde, Belo Jardim, Brejo da Madre de Deus, Buíque, Jataúba, Pedra, Pesqueira, Poção, Sanharó, São Caitano, Sertânia, Tamandaré, Tupanatinga e Venturosa. Lista consultada em 16/10/2026; códigos conferidos na [API do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/estados/26/municipios). O consórcio escreve São Caetano; o IBGE usa São Caitano.

O catálogo fica em `app/modules/vigilancia/sinan.py`, separado dos IDs internos de Prefeitura. A API usa seis dígitos do município da **unidade notificadora** (`id_municip`), não do residente. Os resultados podem incluir residentes de outras cidades e não representam o total de casos dos moradores. O filtro de ano é `nu_ano`, e a semana de notificação é `sem_not` (AAAASS), inclusive na virada do ano epidemiológico.

| Doença | Endpoint oficial | Envelope JSON | Catálogo |
| --- | --- | --- | --- |
| Dengue | `/arboviroses/dengue` | `dengue` | [Dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue) |
| Zika | `/arboviroses/zikavirus` | `zikavirus` | [Zika](https://dadosabertos.saude.gov.br/dataset/arboviroses-zika-virus) |
| Chikungunya | `/arboviroses/chikungunya` | `chikungunya` | [Chikungunya](https://dadosabertos.saude.gov.br/dataset/arboviroses-febre-de-chikungunya) |

[Documentação da API](https://apidadosabertos.saude.gov.br/v1/); domínio dos endpoints: `https://apidadosabertos.saude.gov.br` (sem `/v1` no endpoint). URLs e envelopes são fixos, nunca recebidos do cliente. A resposta é rejeitada se contém dados de outro município/ano ou envelope incompatível.

Embora o Swagger descreva `offset` como página, verificações reais nas três fontes confirmaram deslocamento de **registros**. A implementação avança 0, 10, 20, etc. Não elimina registros só porque os campos públicos são iguais: notificações distintas podem compartilhar esses valores. A fonte pode mudar entre páginas, sem garantia de versão estável ou ordenação fornecida pela API.

## Classificações

- [Dicionário de dengue](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/dic_dados_dengue.pdf), página 12, e [dicionário de chikungunya](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Chikungunya/dic_dados_chikungunya.pdf), página 11: 1 confirmado, 2 descartado, 8 inconclusivo e 0/9 ignorado.
- [Layout SINAN Online 2015](https://portalsinan.saude.gov.br/images/documentos/Agravos/Dengue/DIC_DADOS_ONLINE.pdf): 5 descartado, 10 dengue, 11 dengue com sinais de alarme, 12 dengue grave e 13 chikungunya; esses códigos foram observados na fonte atual.
- [Dicionário de zika](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Zikavirus/dic_dados_zika.pdf), página 6: 1 confirmado, 2 descartado e 9 ignorado. Não herda os códigos do SINAN Online.

A tela mantém códigos desconhecidos e campos ausentes. Notificações não são necessariamente casos confirmados; confirmação também não implica exame laboratorial. A consulta não calcula incidência, risco de surto ou casos prováveis.

## Verificação de disponibilidade em 16/10/2026

Foi solicitada uma linha de dengue para cada município e ano, com os filtros oficiais. Todos os 15 municípios retornaram registros em **2025**. Em **2026**, 12 retornaram registros; **Belo Jardim, Pedra e Poção** retornaram listas vazias (HTTP 200). Isso descreve o retorno da API no momento da consulta, não a ausência epidemiológica de casos nem a cobertura de zika/chikungunya.

Também houve retorno real de zika e chikungunya em Pesqueira/2025 e São Paulo capital/2026. Em Pesqueira/2025, zika retornou 2 notificações descartadas; chikungunya retornou 6 notificações, 3 com código 13 e 3 descartadas. A interface foi verificada com dengue São Paulo/2026 nas páginas 1 e 2 (registros 1–10 e 11–20), incluindo voltar e avançar novamente.

Lotes de 100/1000 falharam antes com HTTP 502 por volta de 60 segundos. O lote de 10 funciona nos recortes verificados, mas não garante disponibilidade de toda combinação. Limites: conexão 5 segundos, leitura 45 segundos, resposta 2 MiB. Erros HTTP, conexão, timeout e formato não viram zero. A tela permite tentar novamente preservando os registros anteriores.

## Demonstração e limites

Reinicie o backend após alterações em Python: `run.py` usa `FLASK_USE_RELOADER=0` por padrão. Recarregar só o navegador não atualiza o processo. Selecione doença/município/ano, consulte e demonstre **Próxima**, **Anterior**, **Limpar busca** e os detalhes recolhidos. Para Pedra, use dengue/2025; em 2026, o retorno verificado foi vazio.

Esta etapa demonstra consulta e importação limitada de indicadores (4.8 V), validação/carga do modelo CSV e visualização de coordenadas fornecidas (parte de 4.7 e 4.8 VI). Não comprova migração de todos os sistemas legados nem geolocalização individual a partir da API pública. A demonstração fictícia evidencia o fluxo técnico, não a existência de casos reais nesses pontos. O aceite depende dos arquivos disponíveis, da validação do mapa no domínio autorizado e do roteiro da prova de conceito. Os demais requisitos do edital permanecem fora deste escopo.

## Validação local

```sh
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sinan_import.py tests/test_sinan.py tests/test_vigilancia_routes.py tests/test_central_ti_permissions.py tests/test_mapas_filters.py tests/test_csrf_security.py
node --test tests/test_sinan_frontend.cjs
.venv/bin/python scripts/build_css_bundle.py --check
git diff --check
```

Os testes cobrem filtros, permissões, CSRF, seleção da fonte, colunas públicas, offsets, troca de doença, cancelamento, respostas atrasadas, falha ao avançar, cache e fim da paginação. Também verificam importação única concorrente, limites de 100, upload limitado antes dos middlewares, CSV atômico, persistência, acesso por usuário, exportação sem rede e preservação do lote concluído. A API real e a revisão de interface são verificações separadas dos testes automatizados.
