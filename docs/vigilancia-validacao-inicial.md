# Prévia de validação de vigilância

Esta primeira entrega permite conferir arquivos CSV de tratamento focal e LIRAa em memória e revisar uma prévia por levantamento, estrato e área. O layout `ija-vigilancia-preview-v1` é **provisório**: foi desenhado para exercitar validação, conflitos e cálculo com dados sintéticos. Não substitui layouts oficiais, não importa SINAN, não grava imóveis ou inspeções e não executa migrações de banco.

## Acesso local e arquitetura

A tela fica em `/vigilancia/validacao`, com ativação explícita por `VIGILANCIA_PREVIEW_ENABLED=1`. A flag fica desabilitada por padrão. Administradores globais (`dev`, `diretor`, `admin`) informam explicitamente o código interno da prefeitura; `prefeitura_admin` utiliza a prefeitura da própria conta. Outros perfis não acessam a prévia. A validação exige que todas as linhas correspondam à prefeitura autorizada. Esse identificador é `Prefeitura.id` do IJA, **não é código IBGE**. A prévia não consulta o banco para verificar a existência do identificador informado pelo administrador global.

Para experimentar em ambiente local já configurado, inicie o servidor com a flag:

```sh
VIGILANCIA_PREVIEW_ENABLED=1 .venv/bin/python run.py
```

Abra `/vigilancia/validacao`, informe o código interno da prefeitura quando solicitado e baixe o modelo sintético. Não use dados pessoais ou arquivos reais de saúde nesta prévia sem autorização e ambiente adequado. As cinco linhas do modelo são ficcionais, inclusive códigos, bairro, área e coordenadas. A data é fixa: `2026-01-10`.

O domínio e o serviço de validação usam somente a biblioteca padrão do Python. A camada HTTP controla autenticação, autorização e tamanho do upload; o serviço valida novamente os limites e o município. O gerador de amostra usa o mesmo cabeçalho definido pelo domínio. A CLI carrega esse pacote isoladamente para evitar a inicialização da aplicação Flask, leitura de `.env`, scheduler e conexões ao banco. Nenhum desses comandos executa uma carga definitiva.

## Layout provisório

O arquivo deve ser UTF-8, com ou sem BOM. Os delimitadores aceitos são vírgula e ponto e vírgula. O cabeçalho deve conter exatamente os 13 campos abaixo, sem repetições ou colunas adicionais. O modelo define a ordem recomendada:

```text
municipio_id,origem,imovel_codigo,inspecao_codigo,data_inspecao,bairro,area_codigo,levantamento_codigo,estrato_codigo,situacao,positivo_aedes,latitude,longitude
```

| Campo | Regra da prévia |
| --- | --- |
| `municipio_id` | Identificador inteiro de 1 a 2.147.483.647 da prefeitura informada/autorizada (`Prefeitura.id` interno, não IBGE). |
| `origem` | `FOCAL` ou `LIRAA`. |
| `imovel_codigo` | Código estável do imóvel na origem. Preservado como texto, incluindo zeros à esquerda. |
| `inspecao_codigo` | Código estável da inspeção na origem. Preservado como texto, incluindo zeros à esquerda. |
| `data_inspecao` | Data válida no formato `AAAA-MM-DD`. |
| `bairro` | Nome do bairro. |
| `area_codigo` | Código textual da área de análise. |
| `levantamento_codigo` | Obrigatório em `LIRAA`; vazio em `FOCAL`. |
| `estrato_codigo` | Obrigatório em `LIRAA`; vazio em `FOCAL`. |
| `situacao` | `INSPECIONADO`, `FECHADO` ou `RECUSADO`. |
| `positivo_aedes` | `SIM` ou `NAO` quando inspecionado; vazio para fechado/recusado. |
| `latitude` / `longitude` | Ambas vazias ou ambas numéricas finitas. Latitude de −90 a 90; longitude de −180 a 180. |

Os limites são 1 MiB e 5.000 linhas de dados. Arquivo vazio, encoding inválido, cabeçalho incompatível, CSV malformado, quantidade incorreta de campos e excesso dos limites impedem o processamento. Erros de conteúdo são exibidos por linha e campo; as linhas rejeitadas não participam dos registros aceitos.

## Duplicidade, conflitos e resultado

Uma linha idêntica da mesma inspeção é contada como duplicada e não cria outra inspeção. Se a mesma identidade de inspeção apresentar conteúdo diferente, **todas as linhas dessa identidade** são rejeitadas para revisão, incluindo uma versão que tenha aparecido antes no arquivo. As identidades incluem município e origem.

Imóveis repetidos precisam conservar sua identificação territorial. Um imóvel deve pertencer a um único estrato dentro do mesmo levantamento LIRAa; estratos divergentes rejeitam todas as ocorrências desse imóvel/levantamento para revisão. Levantamentos diferentes podem atribuir estratos diferentes. Inspeções LIRAa com resultados contraditórios para o mesmo imóvel, levantamento, estrato e área também exigem revisão: o serviço não escolhe silenciosamente o primeiro ou o último resultado. Múltiplas inspeções coerentes do mesmo imóvel não aumentam o denominador. Uma visita fechada/recusada deixa de contar como pendente neste lote somente quando há uma inspeção válida no mesmo grupo em data igual ou posterior à última pendência. Se a pendência for mais recente, o imóvel aparece uma vez nos totais históricos de inspecionados e também nos pendentes; a prévia não declara sua resolução definitiva.

O resultado contém registros normalizados, erros por linha/campo, resumo de aceitas/duplicadas/rejeitadas e indicadores por grupo LIRAa. `sem_coordenadas` conta registros aceitos sem coordenadas; não conta imóveis únicos. A situação geral é `VALIDADO` ou `COM_PENDENCIAS`. Os indicadores são identificados como `PREVIA` ou `INDISPONIVEL`.

**Qualquer linha rejeitada bloqueia o percentual de todo o arquivo**, evitando apresentar um índice calculado sobre uma amostra parcialmente rejeitada. Um grupo sem imóveis inspecionados também recebe percentual indisponível, em vez de zero. Os totais continuam visíveis para ajudar na revisão.

## Prévia de infestação predial

O serviço agrupa exclusivamente registros `LIRAA` por levantamento, estrato e área e utiliza imóveis únicos:

```text
prévia IIP = 100 × imóveis inspecionados positivos para Aedes / imóveis inspecionados
```

O modelo sintético contém três imóveis LIRAa inspecionados, um positivo, e um imóvel fechado. O resultado esperado é **33,33%**, com três no denominador e um pendente. A quinta linha é um tratamento focal positivo, mantido no resumo operacional e excluído da prévia LIRAa.

A fórmula de índice predial consta no [Manual LIRAa do Ministério da Saúde, seção 3.1, página 19 impressa](https://bvsms.saude.gov.br/bvs/publicacoes/manual_liraa_2013.pdf). O arquivo provisório não comprova desenho amostral, exame laboratorial, espécie, representatividade, período, estrato oficial ou regras de encerramento do levantamento. Esses aspectos e o mapeamento de `positivo_aedes` precisam ser homologados pela vigilância. **A prévia não confirma um índice oficial.**

## Validação sem servidor ou banco

Valide o conjunto sintético e, opcionalmente, salve a evidência local em JSON:

```sh
.venv/bin/python scripts/validate_vigilancia_preview.py --sample --municipio-id 1 --output /tmp/vigilancia-preview-sintetica.json
```

Para um arquivo próprio no mesmo layout:

```sh
.venv/bin/python scripts/validate_vigilancia_preview.py /tmp/meu-arquivo-sintetico.csv --municipio-id 1 --output /tmp/vigilancia-preview-validacao.json
```

Os dois modos são exclusivos. A CLI lê até o limite de tamanho mais um byte, valida em memória e imprime um resumo. O JSON opcional contém o resultado completo, inclusive registros; cuide do destino e descarte do arquivo quando usar uma fonte autorizada. O caminho de saída deve ser diferente do CSV de origem. Retornos: `0` para arquivo válido; `1` para conteúdo com linhas rejeitadas; `2` para estrutura, limite, leitura/escrita ou argumentos inválidos. Reexecutar o comando não altera banco, arquivos de origem ou serviços externos.

Os testes do serviço e da CLI são executados sem aplicação Flask:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_vigilancia_preview.py' -v
```

## Limites e próximos passos

A prévia não geocodifica endereços, calcula risco de surto, integra SINAN, sincroniza legados, persiste lotes, audita cargas definitivas ou migra dados. O download sintético não é um exemplo oficial do LIRAa. Não existe compromisso de disponibilidade ou canal social decorrente desta entrega.

Antes de evoluir para importação, obter layouts e amostras anonimizadas oficiais, chaves estáveis, regras de correção/cancelamento e critérios de aceite por município e fonte. Depois definir persistência separada para imóveis, inspeções, levantamentos e depósitos, preparação/quarentena dos lotes, aprovação e reconciliação. Esses passos exigem modelagem e migrações próprias, além de autorização para tratar fontes reais. SINAN depende de fonte, versão e acesso autorizados; não se presume a existência de uma API disponível.
