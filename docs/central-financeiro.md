# Central Financeiro — estrutura inicial

## Objetivo e escopo

A central reúne empresas, cada uma identificada pelo CNPJ, e permite abrir o ambiente financeiro da empresa selecionada. É uma área própria dentro da aplicação Flask existente, ao lado de Prefeitura e Agro. O cabeçalho das páginas financeiras usa a identificação **Central Financeiro**, com ícone bancário e sem o logo da Oceano Azul; a troca mantém o link para a central e se adapta ao tema e ao celular. A organização por empresa segue a ideia de aplicativos por CNPJ apresentada na [documentação do Omie](https://ajuda.omie.com.br/pt-BR/articles/5409954-compartilhamento-de-cadastros-entre-aplicativos), usando os componentes e as cores do IJA System.

O catálogo contém apenas a IJA, inicialmente com o CNPJ fictício `11.111.111/0001-11`, explicitamente identificado como demonstração. A lista e o ambiente recebem dados de empresa; não estão limitados visualmente à IJA. Os testes verificam também a renderização de duas empresas simuladas.

O cadastro de empresas ainda não foi implementado. O botão **Cadastrar empresa**, desativado e marcado como **Em breve**, aparece para `financeiro_admin` e `dev`, que pode validar a interface. O administrador financeiro será responsável pelo cadastro e pela configuração das empresas quando a função for desenvolvida. Os demais perfis não recebem esse controle.

A entrega inicial não criou tabelas ou registros financeiros. A configuração de identidade agora usa a tabela própria descrita ao final deste documento. A validação automatizada usa dados simulados e SQLite em memória; a validação visual lê o banco já conectado ao servidor local, sem executar lançamentos. O `Procfile` permanece inalterado. Os recursos financeiros existentes no Agro agora são acessados pelo ambiente da IJA na Central Financeiro. Suas URLs, serviços, consultas e regras de lançamento foram preservados; o escopo dos dados não foi alterado.

As abas financeiras foram removidas do menu e dos atalhos do dashboard Agro. Também foram retirados o contador de pendências financeiras e os atalhos para o financeiro na listagem operacional de contratos. Clientes, Fornecedores e Comercial continuam no Agro com suas telas e funções existentes. Os perfis financeiros não acessam o painel operacional Agro, mesmo que tenham o antigo campo `trabalha_agro` marcado; as URLs operacionais retornam 403. O dashboard Prefeitura encaminha esses perfis à Central Financeiro.

## Navegação e permissões

1. Entrar com um perfil `financeiro_admin` ou `financeiro`: o login abre sua própria central em `/financeiro`. O seletor de centrais no menu do usuário oferece somente **Financeiro** para os perfis financeiros. O `admin` pode escolher Prefeitura e Agro, mas não tem acesso ao Financeiro, inclusive sem o antigo vínculo operacional `trabalha_agro`; o DEV também recebe Financeiro para validação.
2. Em `/financeiro`, buscar uma empresa pelo nome ou CNPJ e selecionar **Acessar empresa**.
3. Em `/financeiro/empresas/ija`, conferir a identificação da empresa e selecionar uma funcionalidade. O menu e os atalhos incluem Clientes e Fornecedores, Comercial, Painel financeiro, Contas, Relatório Geral, Comprovantes, Caixa Diário, Recebíveis, Contas a Receber, Nova Entrada Manual, Contas a Pagar, Nova Saída Manual, Bancos e Conciliação Bancária.
4. Usar **Trocar empresa** para voltar ao catálogo.

O perfil `dev` mantém seu painel técnico como destino do login. Nesse painel, o atalho **Central Financeiro** abre `/financeiro`. Também pode usar o seletor de centrais ou acessar a URL diretamente. As abas financeiras continuam dentro da empresa, separadas das abas operacionais da Prefeitura e do Agro.

A sidebar segue o comportamento original do Agro, com grupos expansíveis:

- **Clientes e Fornecedores**: Visão Geral, Clientes e Fornecedores.
- **Comercial**: Orçamentos, Mapeamentos e Contratos.

As páginas dentro da empresa reaproveitam os mesmos controladores, templates, filtros, detalhes e arquivos das telas originais. A listagem de Clientes, Fornecedores, Orçamentos e Contratos mantém a paginação original de 12 registros; Mapeamentos mantém seu filtro de equipe e listagem original. Os filtros e links das consultas mantêm a empresa na URL. As rotas da empresa aceitam apenas GET e verificam a empresa antes de consultar os dados.

Os perfis financeiros consultam Clientes e Comercial sem receber edição operacional de clientes, orçamentos, equipes ou contratos. A gestão de Fornecedores e os comprovantes mantêm as permissões financeiras existentes, incluindo escrita e CSRF. O `admin` conserva suas ações operacionais; o DEV sem vínculo com o Agro não ganha essas ações operacionais ao validar o Financeiro.

**Abrir caixa** ganha um botão azul em destaque no cabeçalho de Caixa Diário, que leva ao formulário existente. O botão de confirmação também recebe mais destaque e ocupa a largura disponível em celular. A condição de exibição, o envio do formulário e as validações de abertura permanecem os mesmos; clicar no atalho do cabeçalho não abre nem grava um caixa.

| Perfil | Central | Ambiente demonstrativo da IJA | Cadastro/configuração |
| --- | --- | --- | --- |
| `financeiro_admin` | Sim | Sim, sem exigir vínculo operacional com o Agro | Configurações e Categorias existentes habilitadas; cadastro de empresas desativado |
| `financeiro` | Sim | Sim, sem exigir vínculo operacional com o Agro | Não |
| `dev` | Sim | Sim, para validação, sem exigir `trabalha_agro` | Configurações e Categorias habilitadas; prévia do cadastro de empresas desativada |
| `admin` | Não; mantém Prefeitura e Agro | Não | Não |
| `diretor` | Não | Não | Não |
| Demais perfis | Não | Não | Não |

O login e a rota raiz dos perfis financeiros abrem a central. Os destinos dos demais perfis são preservados, assim como o seletor Prefeitura/Agro dos administradores operacionais. Configurações e Categorias aparecem para `financeiro_admin` e `dev`.

Para compatibilidade, as telas reaproveitadas continuam em URLs como `/agro/financeiro/contas`, `/agro/caixa` e `/agro/bancos`. Essas rotas agora usam o contexto visual do Financeiro, mostram IJA/CNPJ no cabeçalho e retornam à empresa pelo botão Voltar. O nome técnico Agro na URL não autoriza outros perfis a acessá-las.

## Segurança e funcionamento

As páginas da central e todas as rotas das abas financeiras exigem autenticação e autorização no servidor, inclusive consultas, exportações e operações POST. A verificação das rotas existentes ocorre antes da execução de seus serviços. `financeiro_admin`, `financeiro` e `dev` têm acesso sem depender do campo operacional `trabalha_agro`. A central tem sua própria permissão; os perfis financeiros continuam sem acesso aos painéis operacionais. O `admin` mantém acesso aos painéis operacionais e recebe 403 nas rotas financeiras; o DEV mantém a regra operacional existente. Configurações e Categorias exigem `financeiro_admin` ou `dev` também por URL direta.

O DEV possui as permissões financeiras de consulta, edição e configuração para testes. Esse acesso não cria um banco ou ambiente separado: alterações feitas pelas telas usam o banco conectado à aplicação. Validar operações de escrita em homologação.

Empresa inexistente retorna 404; usuário sem permissão retorna 403. A identidade exibida usa o escape de HTML dos templates. As respostas do Financeiro usam `Cache-Control: private, no-store`. As operações de escrita continuam usando o mecanismo de CSRF existente, quando habilitado na aplicação.

A empresa é resolvida a cada requisição pela URL e pelo catálogo autorizado; não é gravada como seleção global na sessão. Isso evita que a escolha de empresa em uma aba troque o contexto de outra aba. A busca e o filtro funcionam no navegador, sem consultas adicionais ao servidor. A central pula os contadores dos menus operacionais e o carregamento do Google Maps, que não são usados nesse ambiente.

Não existe isolamento de lançamentos por CNPJ nesta etapa. As abas da IJA e suas consultas comerciais usam os dados e filtros já existentes do Agro; o CNPJ fictício é somente identificação visual. Nenhuma outra empresa recebe esses atalhos. As rotas de Clientes e Comercial de uma empresa diferente da IJA retornam 403 mesmo que um novo cartão seja acrescentado ao catálogo; empresa desconhecida retorna 404. Não se filtra pelo documento do cliente como se ele fosse o CNPJ da empresa proprietária dos registros.

Para a próxima etapa, a empresa deverá ter um identificador interno associado a um CNPJ válido e único. Clientes, orçamentos, contratos e lançamentos deverão ter um vínculo persistido com essa empresa. Cada consulta e alteração deverá conferir o vínculo do usuário e filtrar pelo identificador interno antes de liberar uma segunda empresa. O CNPJ identifica a empresa; conhecer um CNPJ ou alterar uma URL não concede autorização.

Cadastro de empresas, atribuição de acesso e migração dos dados financeiros exigem implementação e validação próprias; o botão desativado não substitui essas regras. Os perfis financeiros acessam arquivos comerciais e comprovantes compartilhados necessários para as funções existentes. Isso não libera o restante do Agro; mutações operacionais permanecem protegidas por sua autorização própria. O servidor também bloqueia o acesso desses perfis às telas de mapas da Prefeitura.

## Como verificar

```bash
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/test_financeiro_central.py
node --test tests/financeiro_central_browser.test.cjs
.venv/bin/python scripts/build_css_bundle.py --check
```

Os testes da central usam uma aplicação isolada sem conexão de banco. Verificam os perfis permitidos e negados em todas as rotas financeiras, inclusive POST, antes de qualquer gravação; a configuração do administrador financeiro e do DEV; o acesso do DEV sem vínculo operacional e a exigência de CSRF nas suas operações quando habilitado; a preservação de Prefeitura/Agro; a remoção dos atalhos financeiros de lá; a abertura de Contas e Bancos com o contexto da IJA; reutilização das telas originais de Clientes, Orçamentos, Mapeamentos e Contratos, com busca, paginação e bloqueio de outras empresas antes da consulta; a ausência de seleção global na sessão; múltiplas empresas simuladas e escape de HTML. Os testes JavaScript usam DOM simulado e verificam busca por nome/CNPJ, filtro e estado vazio.

No navegador, conferir tema claro/escuro, celular, entrada na IJA, abertura de Contas/Bancos e retorno ao catálogo. Entrar como `financeiro` e confirmar ausência de Configurações/Categorias; como `financeiro_admin` ou `dev`, confirmar sua presença; como `dev`, abrir a central pelo atalho do painel técnico; como `admin`, confirmar bloqueio do Financeiro (inclusive URLs diretas) e a preservação de Prefeitura e Clientes/Comercial no Agro; como `diretor`, confirmar que o Financeiro permanece negado. Expandir os dois grupos na sidebar financeira e confirmar as opções. Em Caixa Diário, testar o atalho **Abrir caixa** sem enviar o formulário; executar abertura/fechamento somente em homologação. Após publicação, repetir os fluxos com usuários de homologação. A validação local não equivale a testar integrações de produção.


## Identidade por empresa e configurações

As configurações agora se dividem em **Dados da empresa**, **Logo e aparência** e
**Competências**. Nome, razão social, CNPJ e logo são persistidos pelo slug autorizado
do catálogo na tabela `financeiro_empresa_perfis`. A logo aparece no catálogo, na
visão geral e no cabeçalho das telas financeiras; sem imagem, o cartão usa iniciais.
PNG, JPG e WebP são validados pelo conteúdo, limitados a 2 MB/16 megapixels e
normalizados para PNG de até 512 × 512, mantendo proporção e transparência.
As imagens são enviadas ao Skybox em `financeiro/empresas/<slug>/logos/<uuid>.png` e servidas por rota autenticada sem cache. No banco fica apenas o marcador `skybox://...` em `logo_path`, sem conteúdo binário. O envio exige Skybox configurado; não há fallback para o banco. Substituições e remoções limpam o arquivo anterior somente após confirmar a gravação no banco. Falhas de limpeza remota são registradas no log.
O CNPJ substituído deve ser válido e único; o documento demonstrativo pode ser
mantido até a atualização. Apenas os perfis com permissão de configuração podem
alterar a identidade, com a proteção CSRF existente.

Para instalações que já usaram logos no banco, com a aplicação parada:

```bash
flask --app run db upgrade e2b431cc9f70
python -m scripts.migrate_company_logos_to_skybox
flask --app run db upgrade
```

O script transfere uma empresa por transação e confere o SHA-256 da cópia baixada
antes de limpar o binário. Pode ser retomado após interrupção. Em falha, preserva
o original e pode deixar uma cópia remota sem referência para revisão, evitando
apagar dados em caso de resultado incerto de commit. A migração final
`f2c531cc9f71` impede a remoção da coluna binária enquanto houver logos pendentes.
Instalações sem logos antigas podem executar `flask --app run db upgrade` diretamente. Esta implementação não habilita cadastro de outras
empresas nem isolamento dos lançamentos: a IJA continua sendo a única empresa
no catálogo e a única com acesso às competências existentes. Adicionar uma linha
de perfil por si só não concede acesso a uma empresa.
