# Território, planejamento LIRAa e acesso de agente

Entrada da coordenação: **Vigilância → Focal e LIRAa → Planejar levantamento**,
`/vigilancia/planejamento`. Usa a ativação `VIGILANCIA_IMPORT_ENABLED` e as
permissões de consulta e edição de vigilância existentes. O perfil de agente
possui uma área própria, descrita abaixo.

## Fluxo do levantamento em quatro passos

A entrada **Acessar Focal e LIRAa** da Central de Vigilância abre o fluxo do
próprio módulo, também acessível pela Central de Treinamentos. O LIRAa tem quatro
abas: **Levantamento, Quarteirões, Estratos e Visitas**. **Ver resultados** fica
em um botão separado. A aba Estratos permite selecionar um levantamento e abrir
diretamente seu cadastro manual ou a importação do arquivo 02, preservando
prefeitura, demonstração/dados autorizados e levantamento ao navegar.

1. **Cadastrar levantamento:** criar ou selecionar o levantamento, com código,
   período, responsável e fonte. Criar o rascunho mantém a aba Levantamento;
   o botão **Continuar para 2 · Quarteirões** abre a demarcação territorial.
2. **Demarcar quarteirões:** cadastrar e desenhar os contornos no mapa ou importar
   o CSV territorial (arquivo de teste 01). O código do levantamento permanece
   selecionado ao salvar. Os quarteirões continuam no cadastro territorial da
   prefeitura; a vinculação à amostra ocorre no passo seguinte.
3. **Adicionar estratos:** cadastrar estratos, metas, vínculos dos quarteirões e
   agentes, ou enviar o CSV de amostra (arquivo de teste 02). O campo de envio da
   amostra fica visível dentro do rascunho, sem depender de expandir um detalhe.
   O botão **Novo estrato** leva ao formulário **Cadastrar estrato**, sempre
   visível no rascunho, mesmo quando já existem estratos. Não exige arquivo CSV.
4. **Registrar visitas:** usar o registro manual com seleção do quarteirão ou
   importar o CSV de visitas (arquivo de teste 03), revisar e confirmar a carga.

Cada etapa apresenta somente seu cadastro, inclusive sem JavaScript. Quarteirões,
estratos/amostra e visitas têm o campo de anexo e o CSV de exemplo lado a lado.
Para São Paulo, os botões baixam o kit UVIS Sé; para Pesqueira, o kit existente.
Outros municípios recebem o modelo genérico. A tela de visitas permite anexar o
arquivo diretamente e encaminha à revisão antes de gravar.

Salvar um cadastro ou importar os quarteirões mantém a etapa atual, a prefeitura,
a origem dos dados e o levantamento selecionado. A importação territorial não
abre Estratos automaticamente. O avanço ocorre pelas abas ou pelos botões
**Continuar**. Liberar ou encerrar o levantamento mantém a aba Estratos.
A prévia e a confirmação de uma visita manual ou de um CSV enviado na aba
Visitas aparecem nessa mesma tela. Nenhum registro entra nos índices sem a
confirmação. A tela separada de importações também permanece nela após validar
e confirmar. No acesso individual do agente, levantamento e quarteirão continuam
selecionados após preparar ou confirmar uma visita.

As etapas são navegáveis; sua conclusão não é requisito para exportar. Cada tela
oferece a exportação do seu cadastro. O fluxo
oferece CSV de levantamentos, quarteirões com geometria, estratos/amostra e
visitas. Rascunhos, estratos ainda sem quarteirões e conjuntos vazios podem ser
exportados. Um conjunto vazio gera apenas o cabeçalho. As exportações mantêm
o escopo municipal, a separação entre demonstração e dados autorizados e a
permissão de exportação já usada nos relatórios. Consultas de exportação não
criam nem atualizam registros.

A exportação de amostra de um levantamento selecionado usa o layout da amostra;
sem selecionar um levantamento, o CSV acrescenta a coluna `plano` para identificar
a origem de cada linha. Amostras incompletas podem ser exportadas, mas ainda
precisam ser completadas e revisadas antes da liberação para novas visitas
planejadas. As validações de gravação, autoria e confirmação permanecem.

O arquivo de teste 04 contém notificações SINAN. Sua importação continua no
módulo SINAN e não é uma etapa do levantamento LIRAa.

O kit **UVIS Sé · São Paulo** fica em `app/resources/treinamentos/testes-sao-paulo`
e no ZIP disponível em Treinamentos. Mantém os quatro layouts de Pesqueira.
Endereços, coordenadas dos equipamentos e quadras fiscais são dados públicos
do GeoSampa consultados em 12/11/2026. Os polígonos são simplificados; os pontos
de visitas, imóveis, metas e dados de saúde são fictícios. As consultas e os
polígonos originais estão em `FONTES_GEOGRAFICAS.json`. O kit usa a prefeitura
interna 1, conferida por consulta somente de leitura neste ambiente, e IBGE
3550308 para SINAN. Em outra instalação, ajuste o ID interno das visitas.
Nenhum cadastro, visita ou caso foi inserido no banco real para montar o kit.

Verificação: `tests/test_vigilancia_survey_flow.py` cobre a ordem funcional com
os três CSVs LIRAa do kit, exportações antes da liberação e das visitas,
consultas sem escrita, separação entre municípios e demonstração/dados
autorizados. Os IDs 14 e 167 usados nesse teste são dados fictícios do banco
descartável, compatíveis com as referências do kit; nenhum cadastro real é criado.

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
   bairro e área é preenchido. Confirmação revalida vínculo e situação
   do plano na mesma transação das inspeções. CSV legado não pode contornar
   o planejamento de um levantamento que tenha plano cadastrado.
   Somente em **Demonstração**, a data da visita pode ficar antes ou depois do
   período cadastrado do levantamento. Ela é preservada como informada, tanto
   no cadastro manual quanto no CSV e no acesso web do agente. Nos dados
   autorizados, a data continua restrita ao período na preparação e confirmação.
   Os filtros continuam usando a data efetivamente registrada.
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

Planos liberados/encerrados são protegidos contra edição. Alterações concorrentes
no rascunho são detectadas pela versão. Escritas usam o mesmo lock municipal do
registro de campo. Cada alteração de plano preserva ação, autor e instante.
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
