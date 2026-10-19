# Território, planejamento LIRAa e acesso de agente

Entrada da coordenação: **Vigilância → Focal e LIRAa → Planejar levantamento**,
`/vigilancia/planejamento`. Usa a ativação `VIGILANCIA_IMPORT_ENABLED` e as
permissões de consulta e edição de vigilância existentes. O perfil de agente
possui uma área própria, descrita abaixo. Os acessos dos outros perfis são mantidos.

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

Validação: 171 testes automatizados e 505 subtestes; fluxo completo em navegador
com dados locais fictícios, desktop/celular e tema escuro; sete verificações em
schema temporário PostgreSQL, removido ao final, incluindo migração/modelos,
atribuição individual, confirmação, contagem e bloqueio após encerramento.
Após acrescentar o bloqueio de campos repetidos no formulário do agente, os 15
testes de planejamento, cadastro e acesso individual foram executados novamente.

Esta entrega cobre cadastro territorial, planejamento informado e distribuição
individual inicial. Permanecem: sorteio nativo validado, cadastro completo de
imóveis/endereço, coleta/laboratório com resultados pendentes e outras espécies,
retificações de planos liberados, mapa por estrato e relatórios oficiais.

Também permanecem os limites do armazenamento de campo: um lote por visita,
200 lotes por prefeitura/modo e base combinada de 1 MiB/5.000 inspeções.
Não iniciar campanha municipal de grande volume sem completar essa evolução.

Referência metodológica: Ministério da Saúde, manual LIRAa (2013), capítulos
2 e 4: https://bvsms.saude.gov.br/bvs/publicacoes/manual_liraa_2013.pdf.
O cadastro e o plano amostral reais de cada município do CONDOMAR ainda devem
ser fornecidos e revisados pela vigilância responsável.
