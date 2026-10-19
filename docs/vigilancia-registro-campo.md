# Registro de visitas e consulta Focal/LIRAa

Acesso: **Vigilância > Focal e LIRAa**, `/vigilancia/campo`. Usa a mesma
ativação `VIGILANCIA_IMPORT_ENABLED=1` da carga de campo. O registro direto
reaproveita as cinco tabelas já preparadas para o importador, sem nova coluna
ou tabela para as contagens de recipientes: elas ficam no JSON da inspeção.
As rotas não criam tabelas automaticamente. A instalação e a transferência do
armazenamento são feitas pelo procedimento de atualização descrito abaixo.

## Central de Vigilância

O menu **Vigilância** abre `/vigilancia`, com os acessos **SINAN · Arboviroses**,
**Focal e LIRAa** e **Importação e validação**. A Central de Relatórios mantém
somente um atalho para essa central. As telas dos módulos oferecem retorno à
central, e os perfis delegados precisam de `prefeitura.vigilancia.consultar`,
sem depender da permissão para relatórios gerais.

A central não consulta as bases de campo nem do SINAN e abre antes da migração
de campo. Os links de módulos desativados por configuração são substituídos
pela indicação de que aguardam ativação. Ela não executa migrações nem altera
as configurações do ambiente.

## Fluxo entregue

1. Selecionar a prefeitura cadastrada e o modo demonstração/dados autorizados.
   Usuários municipais ficam limitados à prefeitura da conta.
2. Registrar uma visita: atividade FOCAL/LIRAA, códigos estáveis do imóvel e
   inspeção, data, área, bairro, situação, positividade identificada e coordenadas
   opcionais em par. LIRAa também exige levantamento e estrato.
3. Opcionalmente preencher as sete contagens de recipientes positivos para
   **Aedes aegypti**, conforme as categorias do manual: A1, A2, B, C, D1, D2, E.
   Os campos representam recipientes, não larvas, tubitos ou depósitos apenas
   suspeitos. Os resultados da espécie precisam ter sido identificados pela equipe.
4. Clicar em **Revisar registro antes de gravar**. O sistema cria um lote
   validado, preserva seu CSV de origem e apresenta a prévia. A visita só será
   publicada em **Confirmar carga validada**. Falhas ou conflitos desfazem a
   confirmação. Reenvios idênticos reaproveitam o lote/inspeção.
5. Voltar a **Registrar visita e consultar indicadores**. Filtrar por atividade,
   levantamento, estrato e intervalo de datas. Consultar até 100 visitas por
   página e exportar todo o recorte, respeitando o limite da base.

## Reaproveitamento de OS

O atalho **Registrar inspeção · Focal/LIRAa** no formulário da OS abre a visita
com sua referência. Também é possível informar o número da solicitação/OS na
tela de campo. São respeitados os acessos de prefeitura, região, UVIS e equipe
do sistema, além da permissão de vigilância. O vínculo exige modo autorizado.

Bairro, coordenadas e referência do responsável são reaproveitados; endereço,
equipe, data da aplicação e observações de larva/criadouro aparecem para
conferência. O código estável do imóvel, a data efetiva, a situação da inspeção,
o levantamento, o estrato e o resultado não são deduzidos da OS. Uma OS pode
abranger vários imóveis. Para LIRAa vinculado à OS, o responsável declara que
o imóvel pertence à amostra; isso não substitui o planejamento amostral nem
a identificação da espécie.

A tabela `vigilancia_campo_os` guarda a referência à solicitação por lote. A
declaração do responsável fica no relatório preservado do lote. O sistema não
copia a OS para outro cadastro e não modifica seus dados operacionais. A
referência é validada novamente na confirmação; mudança de prefeitura,
remoção da OS ou referência conflitante a outra OS bloqueiam a publicação.

A situação `NAO_INSPECIONADO` registra visita sem inspeção completa. Ela,
assim como fechado e recusado, não recebe positividade e não entra no total
de imóveis inspecionados. Registros antigos não são convertidos automaticamente.

## SINAN no PostgreSQL

O padrão `SINAN_STORAGE_BACKEND=database` usa `vigilancia_sinan_lotes` e
`vigilancia_sinan_casos` no banco configurado pelo IJA. Mantém a privacidade
por conta/prefeitura, a separação entre demonstração e dados autorizados, o
limite de 100 registros por importação, a publicação transacional, o cancelamento
e um único importador ativo por banco. Workers recebem o engine, sem depender
do contexto HTTP. Uma falha de schema/conexão não desvia a gravação para SQLite.

O caminho `SINAN_STORAGE_PATH` identifica a origem legada. A classe SQLite
continua disponível com `SINAN_STORAGE_BACKEND=sqlite`, para uso local explícito.
Antes da troca, interromper importações e parar os processos antigos. Executar:

```sh
.venv/bin/python -B scripts/upgrade_vigilancia_storage.py
.venv/bin/python -B scripts/upgrade_vigilancia_storage.py --apply
```

O primeiro comando apenas confere o plano. O segundo instala exclusivamente a
revisão aditiva `c7f2a9d810e4`, cria backup SQLite consistente e privado em
`instance/sinan/backups`, preserva IDs, autores, filtros, estados, resumos e casos,
e compara a cópia com a origem. A transferência é transacional e repetível:
registros iguais são reutilizados e divergências bloqueiam sobrescritas. Nenhum
arquivo de origem é excluído. Reiniciar a aplicação após a cópia. Backups e
arquivos SQLite são ignorados pelo Git. Em outros servidores, transferir também
os respectivos arquivos legados antes de reiniciar esses ambientes.

O levantamento é identificado pelo código informado na visita. A evolução de
[território e planejamento](vigilancia-planejamento.md) acrescenta cadastro do RG,
estratos, metas, quarteirões selecionados e contas individuais de agente. A
seleção é informada pela coordenação; não há cálculo de tamanho de amostra ou
sorteio automático. Endereço detalhado, terreno baldio,
amostras, tubitos, responsáveis técnicos, resultados de **Aedes albopictus** e
supervisão completa do BCL permanecem como evolução. Não chamar a tela de
reprodução integral ou substituta homologada do boletim oficial.

## Fórmulas e integridade

Fonte: Ministério da Saúde, *Levantamento Rápido de Índices para Aedes aegypti
no Brasil - LIRAa*, 2013, páginas impressas 19-20 (índices), 34-37 (categorias)
e 59-62 (campo/laboratório e resumo). Manual disponibilizado pelo usuário em
`/Users/pedrohenriquevb/Downloads/manual_liraa_2013.pdf`. Referência pública:
https://bvsms.saude.gov.br/bvs/publicacoes/manual_liraa_2013.pdf

- IIP = 100 × imóveis positivos / imóveis inspecionados, contando imóveis únicos
  em cada levantamento/estrato/área. Focal, fechado e recusado não entram no
  denominador. A mesma visita reutilizada em vários lotes é contada uma vez.
- Breteau = 100 × recipientes positivos / imóveis inspecionados. Pode ultrapassar
  100; não é percentual de imóveis positivos.
- ITR da categoria = 100 × recipientes positivos da categoria / total de
  recipientes positivos. Com zero recipientes positivos, o Breteau é zero e o ITR
  fica sem denominador. Ausência de informação não é convertida em zero.
- Se qualquer contagem for fornecida, as sete categorias devem conter inteiros
  entre 0 e 10.000. A soma precisa ser coerente com a positividade do imóvel;
  fechado/recusado não aceita contagens, nem mesmo sete zeros.
- Se alguma inspeção pesquisada estiver sem contagens, Breteau/ITR ficam
  indisponíveis para o grupo. Com mais de uma inspeção do mesmo imóvel no mesmo
  grupo, os recipientes não são somados: é necessária revisão para evitar dupla
  contagem. O IIP continua contando imóveis únicos.
- Indicadores são preliminares do recorte de registros confirmados. Um filtro
  de datas pode representar apenas parte da amostra. A validação da amostragem,
  o tratamento de resultados oficiais e a interpretação de risco continuam sob
  responsabilidade da vigilância. Não há cálculo automático de risco de surto.

O CSV original de 13 colunas continua aceito. A extensão opcional adiciona as
sete colunas `depositos_a1`, `depositos_a2`, `depositos_b`, `depositos_c`,
`depositos_d1`, `depositos_d2`, `depositos_e`. Quando uma delas estiver no
cabeçalho, todas devem estar presentes. Uma linha com todas vazias mantém
contagem desconhecida. Dados fornecidos são normalizados e preservados na
inspeção e na origem do lote. O formato continua provisório do IJA.

## Permissões e limites

Consulta: `prefeitura.vigilancia.consultar`; registro e confirmação:
`prefeitura.vigilancia.editar`; exportação: `prefeitura.relatorios.exportar`,
com acesso de consulta à vigilância. POST sempre exige CSRF da sessão.
As respostas recebem `Cache-Control: private, no-store`.

O registro direto gera um lote por visita e utiliza os limites já existentes:
até 200 lotes por prefeitura/modo e base de até 5.000 inspeções/1 MiB para
revalidação. Para registrar volumes maiores, o fluxo de importação agrupa
diversas visitas em um lote; não iniciar uma campanha grande de digitação sem
revisar esses limites e o planejamento de lotes. Demonstração e dados
autorizados têm identidades independentes. O SINAN mantém seu limite próprio
de 100 registros por importação.

O CSV de consulta é exportado com aspas e BOM UTF-8; textos que começam como
fórmula de planilha recebem apóstrofo de proteção. Por isso ele não deve ser
usado para restaurar códigos modificados pela proteção. Para reconciliação
exata, baixar o arquivo original preservado no lote.

## Integração das branches

O merge recebido tinha conflito no final de `app/models.py`. A resolução
preserva o registro dos modelos de campo e os modelos adicionais recebidos
de `main`. A revisão vazia `b6e9d2a4f017` unifica os heads `a41c9e7f26b0` e
`d82b46fa910c`, sem DDL próprio. Conferir o estado instalado e o plano de
migração completo antes de aplicar qualquer atualização no banco real.

## Verificação isolada

```sh
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_vigilancia_capture.py tests/test_vigilancia_field_store.py \
  tests/test_vigilancia_field_routes.py tests/test_vigilancia_field_migration.py \
  tests/test_vigilancia_preview.py tests/test_vigilancia_routes.py \
  tests/test_central_ti_permissions.py
```

As verificações utilizam dados fictícios, serviços simulados e SQLite
descartável. A aceitação em PostgreSQL e a implantação são etapas separadas.
