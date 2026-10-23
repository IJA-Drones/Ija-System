# Território, planejamento LIRAa e acesso de agente

Entrada da coordenação: **Vigilância → Focal e LIRAa → Planejar levantamento**,
`/vigilancia/planejamento`. Usa a ativação `VIGILANCIA_IMPORT_ENABLED` e as
permissões de consulta e edição de vigilância existentes. O perfil de agente
possui uma área própria, descrita abaixo.

A **COVISA de cada prefeitura** coordena o planejamento municipal: cadastra o
território, define estratos, metas e quarteirões, atribui contas aos agentes e
libera/encerra os levantamentos. Tanto o perfil `covisa` quanto a conta legada
`visualizar` com região `COVISA` são reconhecidos. A conta precisa estar vinculada
à prefeitura; parâmetros enviados pelo navegador não permitem mudar esse vínculo.
Administradores globais e Admin Prefeitura mantêm o acesso de apoio existente.

O acesso da COVISA é padrão quando não há configuração de TI substituindo o
perfil. Uma configuração explícita da Central de TI continua válida, inclusive
consulta sem edição e revogação de acesso. Nenhuma seleção salva é sobrescrita
por esta atualização. O cadastro de contas de agente continua sob as regras
de administração de usuários; atribuir um agente não concede esse poder.

Em 19/10/2026, a coordenação por COVISA foi validada com os dois formatos de
perfil, incluindo gravação via HTTP, liberação e atribuição de agente, bloqueio
entre prefeituras, ausência de vínculo municipal e restrições explícitas de TI.
A consulta somente de leitura no Neon confirmou que a COVISA usa a configuração
padrão; não foi necessário alterar seleções salvas, contas ou schema do banco.

## Preparar e executar

1. Selecionar a prefeitura existente e demonstração ou dados autorizados.
   Contas municipais não podem trocar para outra prefeitura.
2. Cadastrar os quarteirões do Reconhecimento Geográfico, com código estável,
   bairro, área, número de imóveis e referência da fonte. O código precisa ser
   único no município/modo; se a numeração local se repete entre bairros,
   utilizar um código composto que preserve essa distinção.
3. Criar levantamento com código novo, nome, datas, responsável técnico e fonte
   do plano amostral. O cadastro estende `CampoLevantamento`, sem copiar OS ou
   criar outra identidade para o mesmo levantamento.
4. Cadastrar os estratos com sua população de imóveis, meta da amostra e
   características. Adicionar os quarteirões já selecionados pela coordenação,
   sua meta e, opcionalmente, uma conta responsável da mesma prefeitura.
5. Conferir e liberar. A soma das metas dos quarteirões deve fechar a meta de
   cada estrato. Metas não podem exceder suas populações. A coordenação declara
   que revisou o plano amostral. A liberação não homologa a metodologia nem os
   índices; não há sorteio ou cálculo automático de tamanho de amostra.
6. Registrar visitas pelo quarteirão. O contexto de levantamento, estrato,
   bairro e área é preenchido. Confirmação revalida vínculo, período e situação
   do plano na mesma transação das inspeções. CSV legado não pode contornar
   o planejamento de um levantamento que tenha plano cadastrado.
7. Acompanhar imóveis únicos inspecionados e com pendência por quarteirão.
   Essas contagens não representam resultados laboratoriais homologados.
   Encerrar o plano interrompe novas confirmações, inclusive de lotes pendentes.

## Seleção de áreas no mapa

No cadastro territorial, a coordenação pode seguir os três passos da tela:

1. Buscar município, bairro ou endereço e aproximar o mapa do quarteirão.
2. Clicar em **Desenhar área**, marcar ao menos três cantos e clicar em
   **Concluir desenho**. **Desfazer ponto** corrige o último canto durante o
   desenho; depois de concluir, os pontos podem ser arrastados para ajustar o
   limite. **Cancelar alteração** recupera o contorno do cadastro carregado.
3. Conferir código, bairro, área, quantidade de imóveis e referência. Marcar a
   confirmação do contorno e **Salvar quarteirão**. Desenhar ou clicar no mapa
   não grava dados automaticamente.

Os contornos cadastrados aparecem em azul; o contorno em edição aparece em
laranja. Clicar em uma área permite carregar seu cadastro. Em um levantamento
em rascunho, **Usar no levantamento** seleciona o quarteirão no formulário de
amostra. A coordenação ainda escolhe o estrato, a meta e o agente e salva essa
atribuição. O desenho não calcula imóveis, não sorteia quarteirões e não decide
a amostra. O código continua sendo o cadastro informado pela prefeitura.

O contorno é opcional e fica em `CampoQuarteirao.geometria`, como GeoJSON
`Polygon` com coordenadas `[longitude, latitude]`. O servidor valida o desenho,
limita a 200 cantos e rejeita coordenadas inválidas, pontos repetidos e linhas
cruzadas. Alterar ou remover um contorno existente exige confirmação e a versão
atual do cadastro. A importação CSV territorial preserva os contornos existentes.
Ao incluir um quarteirão no plano, sua geometria entra no retrato territorial
preservado; editar o RG depois não modifica esse retrato.

O mapa usa a configuração Google Maps já existente e o editor nativo de
polígonos, sem depender de DrawingManager. Se o mapa não carregar, o cadastro
por formulário continua disponível. A chave e as restrições de domínio foram
mantidas. Em localhost, a chave atual é recusada pelo Google; a conferência do
serviço real precisa ocorrer em um domínio autorizado. Não há mapa simulado
como alternativa na aplicação entregue.

## Conta individual do agente

Em **Usuários → Novo usuário**, o administrador pode escolher **Agente de
Endemias**, nome, login, senha individual e prefeitura ativa. Não existe senha
padrão nem criação automática de contas de produção. O cadastro/edição usa as
regras já existentes de administração e delegação de usuários.

O agente entra pelo **login principal** e é direcionado a **Meus levantamentos**,
`/vigilancia/agente`. A coordenação atribui sua conta aos quarteirões antes da
liberação do plano. A página lista somente seus quarteirões de planos liberados,
com separação entre demonstração e dados autorizados.

O agente seleciona um quarteirão, informa o imóvel, a data, a situação e o
resultado já identificado, declara participação do imóvel na amostra, revisa e
confirma a visita. Cada visita mantém a autoria pelo ID da conta. A área e o
bairro são obtidos do plano no servidor. Não são aceitos valores territoriais
substituídos no navegador.

O agente não acessa planejamento, SINAN, importações municipais, OS ou registros
de outra conta. Os bloqueios são aplicados nas rotas, além do menu, mesmo que
receba uma configuração ampla na Central de TI. Nesta entrega, o reaproveitamento
de OS continua na tela de campo da coordenação; não foi ampliado ao agente.

A confirmação volta a validar a atribuição, a prefeitura e o tipo atual da
conta. Uma mudança de vínculo da conta não autoriza concluir lotes antigos.

## Importação e preservação

Os modelos CSV disponíveis na tela são provisórios do IJA, com UTF-8, ponto e
vírgula, até 1 MiB e 5.000 linhas por arquivo. Não são layouts oficiais do governo.

- Território: `quarteirao;bairro;area;imoveis;referencia`. Adiciona ou atualiza
  os códigos informados. Erro em qualquer linha desfaz a operação inteira.
- Amostra: `estrato;imoveis_estrato;meta_estrato;criterio;quarteirao;meta_quarteirao;agente_id`.
  Substitui estratos e quarteirões de um rascunho de forma transacional. Códigos
  territoriais devem existir, dados repetidos do estrato precisam ser iguais e
  cada quarteirão aparece uma vez. A atribuição de conta é opcional.

O planejamento começa em **Quarteirões e contornos**, com o importador do CSV 01
aberto acima do mapa. O arquivo territorial pode cadastrar os quarteirões e seus
polígonos juntos, após a confirmação dos contornos. Depois, criar o rascunho do
levantamento e importar o CSV 02 na amostra. A criação do rascunho não exige CSV.
Sem cadastro territorial, a tela da amostra aponta para o CSV 01 antes de oferecer
a importação dos estratos e quarteirões. O CSV 03 de visitas continua exigindo a
liberação do plano e a confirmação posterior do lote.

Planos liberados/encerrados são protegidos contra edição da amostra. No liberado,
a coordenação pode **ampliar o período** para incluir as datas originais das
visitas: informar início/fim, justificativa e confirmação. O novo intervalo deve
conter todo o anterior; não pode reduzir datas, modificar a amostra, mudar datas
das visitas nem reabrir um levantamento encerrado. O histórico registra período
anterior/novo, justificativa, autor e instante. Em rascunho, usar a edição de
identificação existente. A importação informa o intervalo das visitas do CSV
quando ele não cabe no período selecionado, sem publicar o lote nem modificar
automaticamente o levantamento. O atalho da importação abre o período do
levantamento selecionado, preservando prefeitura e tipo dos dados.

Alterações concorrentes são detectadas pela versão. Escritas usam o mesmo lock
municipal do registro de campo. Cada alteração preserva ação, autor e instante.
Atualizar o RG não altera os dados territoriais já preservados no plano.

Registros legados continuam disponíveis. Não se pode transformar em plano novo
um código que já contenha inspeções anteriores; usar outro código e manter a origem.
Os índices de campo continuam preliminares, separados do tratamento focal.

## Instalação e limites restantes

A revisão aditiva `d8a31e62bc09`, posterior a `c7f2a9d810e4`, cria cinco tabelas:
`vigilancia_campo_quarteiroes`, `vigilancia_campo_planos`,
`vigilancia_campo_plano_estratos`, `vigilancia_campo_plano_quarteiroes` e
`vigilancia_campo_plano_visitas`. Não modifica linhas de OS, usuários ou inspeções
legadas. O novo tipo de usuário usa a coluna textual já existente.

```sh
.venv/bin/python -B scripts/upgrade_planejamento_liraa.py
.venv/bin/python -B scripts/upgrade_planejamento_liraa.py --apply
```

O primeiro comando apenas confere o plano. O segundo aceita exclusivamente o
parent esperado, instala o DDL e atualiza a revisão na mesma transação. Não
executa migrações de outros módulos. Reiniciar a aplicação para carregar rotas,
modelos, permissões e templates. As requisições não criam tabelas.

Em 19/10/2026, a revisão foi instalada no Neon configurado neste projeto e a
aplicação local reiniciada. Conferência somente de leitura confirmou as cinco
tabelas novas vazias e zero contas do tipo `agente_endemias`. Nenhum cadastro
de demonstração foi inserido no schema operacional.

A revisão seguinte, `e91c7b4a203d`, acrescenta somente a coluna JSON opcional
`geometria` em `vigilancia_campo_quarteiroes`. Para um banco já na revisão
`d8a31e62bc09`, conferir e aplicar com:

```sh
.venv/bin/python -B scripts/upgrade_geometria_liraa.py
.venv/bin/python -B scripts/upgrade_geometria_liraa.py --apply
```

O comando sem `--apply` é somente de leitura; a aplicação da coluna e a
atualização da revisão ocorrem na mesma transação. Nenhuma área, conta ou
inspeção de demonstração é criada por essa migração.

Em 19/10/2026, essa revisão foi aplicada no Neon. A conferência de leitura
confirmou `e91c7b4a203d`, a coluna JSON anulável, as cinco tabelas de
planejamento ainda vazias e nenhuma conta `agente_endemias` criada.

Validação: 171 testes automatizados e 505 subtestes; fluxo completo em navegador
com dados locais fictícios, desktop/celular e tema escuro; sete verificações em
schema temporário PostgreSQL, removido ao final, incluindo migração/modelos,
atribuição individual, confirmação, contagem e bloqueio após encerramento.
Após acrescentar o bloqueio de campos repetidos no formulário do agente, os 15
testes de planejamento, cadastro e acesso individual foram executados novamente.

A seleção no mapa foi validada separadamente com 141 testes Python e 459
subtestes, dois testes JavaScript e nove verificações em schema PostgreSQL
temporário, removido ao final. O fluxo de navegador usou dados fictícios e um
adaptador de mapa exclusivo do teste, identificado como **MAPA SIMULADO · TESTE
LOCAL**: busca, desenho, confirmação, persistência, reabertura, seleção para a
amostra, arraste dos pontos com nova confirmação, desfazer, cancelamento,
remoção com confirmação, cadastro por formulário com mapa indisponível,
celular sem transbordamento horizontal e tema escuro. Isso não atesta o
funcionamento do Google Maps real no domínio de produção.

Esta entrega cobre cadastro territorial, planejamento informado e distribuição
individual inicial. Permanecem: sorteio nativo validado, cadastro completo de
imóveis/endereço, coleta/laboratório com resultados pendentes e outras espécies,
retificações de planos liberados e boletins oficiais. O [painel de
resultados](vigilancia-resultados-poc.md) usa os contornos históricos para
mapear os índices por estrato/área e oferece gráficos e relatórios de consulta.

Também permanecem os limites do armazenamento de campo: um lote por visita,
200 lotes por prefeitura/modo e base combinada de 1 MiB/5.000 inspeções.
Não iniciar campanha municipal de grande volume sem completar essa evolução.

Referência metodológica: Ministério da Saúde, manual LIRAa (2013), capítulos
2 e 4: https://bvsms.saude.gov.br/bvs/publicacoes/manual_liraa_2013.pdf.
O cadastro e o plano amostral reais de cada município do CONDOMAR ainda devem
ser fornecidos e revisados pela vigilância responsável.
