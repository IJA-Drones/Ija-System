# Carga persistida de Focal/LIRAa - primeira entrega A1

Acesso em **Vigilância > Importação e validação**, `/vigilancia/importacoes`.
Ativação independente da prévia por `VIGILANCIA_IMPORT_ENABLED=1`, desabilitada
por padrão. Reinicie o backend após alterar código/configuração. A migração cria
cinco tabelas de vigilância sem alterar as tabelas operacionais existentes.

## Armazenamento e escopo

O módulo utiliza o PostgreSQL já configurado em `DATABASE_URL`, inclusive quando
o banco está hospedado no Render. Não exige disco persistente do servidor web,
arquivo SQLite próprio ou nova URL de conexão. Os CSVs originais de até 1 MiB são
preservados no próprio banco (BYTEA), junto com metadados e relatórios JSON.
As tabelas são `vigilancia_campo_lotes`, `vigilancia_campo_imoveis`,
`vigilancia_campo_levantamentos`, `vigilancia_campo_inspecoes` e
`vigilancia_campo_lote_inspecoes`; todas as cargas se vinculam à prefeitura.
Os dados passam a fazer parte do backup desse PostgreSQL; a retenção e a
restauração precisam ser conferidas no ambiente de implantação. Não há envio
automático ao Skybox, fila distribuída ou sincronização com legados. O módulo
SINAN também passou a usar o banco do IJA na revisão posterior `c7f2a9d810e4`.

### Aplicação da migração

A migração original `a41c9e7f26b0` (anterior `d9e4f81b203a`) cria as cinco
tabelas de campo. A revisão `c7f2a9d810e4` adiciona o vínculo das visitas à OS
e as tabelas SINAN. O procedimento de atualização e cópia do SQLite legado
está no [guia de registro](vigilancia-registro-campo.md). Em 19/10/2026, a
revisão nova foi instalada no Neon configurado neste projeto, com cópia dos
dois lotes SINAN existentes e preservação da origem e de um backup privado.

Em outros ambientes, conferir o banco de destino e a revisão instalada antes
de aplicar as migrações pelo procedimento de [operação](operacao.md). Habilitar
`VIGILANCIA_IMPORT_ENABLED=1` e reiniciar o serviço. A aplicação não cria tabelas
automaticamente nas requisições; se a migração não foi aplicada, o módulo
retorna uma mensagem controlada.

O downgrade remove somente as cinco tabelas novas, incluindo seus dados de
campo. Não é uma operação de recuperação de registros. Não o executar no banco
real sem avaliar e preservar os dados que já tenham sido importados.

Administradores globais selecionam uma prefeitura **existente** no cadastro
operacional. Demais usuários com permissão ficam obrigatoriamente limitados à
prefeitura da conta. O ID é `Prefeitura.id`, não IBGE. Consulta e edição usam as
permissões `prefeitura.vigilancia.consultar` e `prefeitura.vigilancia.editar`;
download da origem exige também `prefeitura.relatorios.exportar` em perfis
configurados na Central de TI. O acesso legado é de administradores globais e
administradores de prefeitura. As cargas são consultáveis pela equipe autorizada
do município; somente a conta que preparou o lote pode confirmá-lo.

## Fluxo

1. Informar prefeitura, fonte identificável e tipo dos dados: demonstração ou
   dados autorizados. O segundo exige confirmação de autorização.
2. Baixar o exemplo sintético ou enviar CSV no layout provisório já usado pela
   prévia. O serviço valida todo o arquivo antes de preparar o lote.
3. Conferir erros por linha, normalizações, contagens, registros e IIP preliminar.
   O lote preserva os bytes originais, nome sanitizado, fonte, hash SHA-256,
   versão do layout, autor e horários UTC de preparação/confirmação.
4. Confirmar o lote validado. A transação relê os bytes originais e confronta os
   registros com as inspeções da mesma prefeitura/tipo de dados. Nenhuma
   inspeção é publicada enquanto o lote estiver apenas validado.
5. Reabrir o histórico (últimos 20 lotes), consultar os registros e baixar o CSV
   original ou o relatório JSON. O JSON mantém os valores normalizados e a
   referência à linha original; os bytes de origem permitem reconciliar mudanças.

Qualquer linha inválida bloqueia a confirmação. Estrutura inválida impede a
preparação; erros de conteúdo geram lote `REJEITADO` com diagnóstico. Lotes
confirmados são `CONCLUIDO`. Conflitos com a base deixam o lote `VALIDADO` e
retornam erro HTTP 409; nenhum registro novo é publicado. Falhas de banco
desfazem toda a confirmação, inclusive a alteração do estado do lote.

Repetir arquivo/fonte/tipo na mesma conta/prefeitura reaproveita o lote. Mesmo
reformatando o CSV ou usando outra conta, as inspeções idênticas são
reutilizadas: identidade `(prefeitura, tipo de dados, origem, inspecao_codigo)`.
O lote informa quantas inspeções foram inseridas e reutilizadas. Imóveis e
levantamentos têm chaves próprias; estrato e coordenadas são preservados na
inspeção. A associação lote/inspeção mantém a linha na origem.

Dados divergentes de uma inspeção já existente não são sobrescritos. Mudanças
de área/bairro/coordenadas de um imóvel, estratos divergentes no mesmo
levantamento e resultados LIRAa contraditórios entre arquivos também bloqueiam
a gravação. Alterações oficiais e cancelamentos precisam de um fluxo posterior
com regras homologadas; nesta versão a equipe deve revisar a fonte.

## Indicadores e limites

Os indicadores exibidos são **do lote selecionado**, com imóveis únicos por
levantamento/estrato/área. Não são consolidação municipal nem índice oficial.
FOCAL não entra no denominador LIRAa; fechado/recusado não significa inspecionado;
sem denominador o IIP fica indisponível. Demonstrações e dados autorizados têm
identidades independentes, impedindo mistura de registros e conflitos entre eles.

Limites iniciais: 1 MiB e 5.000 linhas por arquivo; a base combinada da
prefeitura/tipo também deve caber em um CSV de 1 MiB/5.000 inspeções para permitir
revalidação integral. Até 200 lotes por prefeitura/tipo de dado. Não há descarte
automático de origem ou migração massiva. Solicite manutenção ao atingir limites.
As transações de escrita usam lock transacional por prefeitura no PostgreSQL,
compartilhado entre processos e instâncias, com espera máxima de 3 segundos pelo
lock. Os registros são inseridos em blocos na mesma transação. Falhas desfazem a
carga inteira. Os limites são próprios do importador de campo e não mudam os 100
registros por importação do SINAN.

O [registro direto e a consulta consolidada](vigilancia-registro-campo.md)
ampliam esta entrega com visitas digitadas na tela e contagens de recipientes
positivos por categoria, preservadas no JSON da inspeção. A consulta consolida
identidades confirmadas entre lotes, com filtros e índices preliminares.
O [planejamento inicial e acesso de agente](vigilancia-planejamento.md) acrescenta
território, estratos, metas e quarteirões informados pela coordenação.
Cadastro individual de depósitos/amostras e supervisão completos,
mapa de IIP, integração epidemiológica, risco oficial e importação de layouts
oficiais continuam como próximas etapas. Não há enriquecimento inventado de dados ausentes.

## Validação isolada

```powershell
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_vigilancia_field_store.py tests/test_vigilancia_field_routes.py tests/test_vigilancia_field_migration.py tests/test_vigilancia_preview.py tests/test_vigilancia_routes.py tests/test_central_ti_permissions.py
```

Os testes usam o backend SQLAlchemy com SQLite descartável e não alteram dados
reais. A migração é executada nesse banco de teste (upgrade/downgrade), comparada
com os modelos, e seu SQL é compilado para PostgreSQL sem conexão externa.
Isso não substitui o teste de execução e concorrência em PostgreSQL de homologação.
O aceite no ambiente
da PoC inclui importar o exemplo, confirmar, reiniciar o backend, reabrir o lote,
reenviar sem duplicação, conferir a origem preservada e testar outra prefeitura.
