# Central de TI: telas e ações por usuário e por perfil

O modo por perfil foi validado em 09/10/2026. A preparação do modo individual, de 24/11/2026, está descrita a seguir; sua ativação depende da opção específica do ambiente.

## Consultas independentes de veículos — 25/11/2026

A primeira etapa de separação oferece **Frota e turnos**, **Rastreamento de veículos**, **Limpezas de veículos** e **Alertas de limpeza** como módulos independentes, tanto por usuário quanto nos modelos por perfil. Histórico de veículos e checklists conservam suas permissões próprias. É possível manter frota e rastreamento liberados e retirar limpezas e alertas sem alterar as outras contas.

Os cartões, a sidebar, os acessos por URL, as APIs e os materiais de treinamento acompanham as opções. A API de rastreamento não inclui dados de turnos e condutores provenientes dos logs quando o usuário não tem a consulta do histórico. Continuam valendo os limites de prefeitura e de equipe, inclusive ao solicitar o histórico de uma rota.

Esta etapa separa as **consultas**. A operação de turnos continua agrupando seus registros operacionais. A exportação geral de veículos conserva a compatibilidade anterior, que também permite a planilha de logs; a separação dessa ação é uma etapa posterior. Não foram criadas opções de exportação para telas que não possuem essa operação.

As seleções anteriores de `prefeitura.veiculos.consultar` continuam representando o conjunto antigo de consultas. A leitura apenas expande o conjunto efetivo em memória, sem modificar registros no banco. Ao salvar pelo editor atualizado, a escolha recebe o marcador interno `schema:vehicles-v1`, permitindo retirar cada consulta sem que o acesso geral de frota a reative. Esse marcador não aparece como uma função e não é aceito no payload de permissões do cliente. Clientes antigos continuam com a interpretação anterior; os editores atualizados informam `X-Central-TI-Permission-Schema: vehicles-v1`.

O armazenamento existente já comporta os novos códigos. Esta etapa não acrescenta campos em `models.py`, não exige outra migração e não regrava automaticamente seleções no Neon ou no Render. Os testes usam contas fictícias e SQLite descartável; código mantido localmente, sem merge ou publicação.

## Acessos individuais — preparação de 24/11/2026

A nova tela `/central-ti/usuarios` permite buscar uma conta por nome, login, região ou prefeitura, combinar filtros de perfil e prefeitura, escolher áreas e ações, dar um nome ao acesso e revisar as inclusões e remoções antes de salvar. A lista informa o total de resultados e a página atual, com 30 contas por página. Cada item separa nome, login, perfil e vínculo municipal. Contas Dev aparecem somente quando o operador também é Dev, que pode consultar, conceder e retirar suas funções de negócio. A edição abre em uma janela própria, mantendo a lista de usuários em toda a largura da tela. Para o Gestor de TI, ficam excluídas dos resultados, contagens e filtros, inclusive em buscas diretas pela API. O botão **Cadastrar usuário** abre o cadastro existente quando o administrador tem autorização; depois do cadastro, a conta pode ser localizada na central. O cadastro e seus vínculos continuam usando os fluxos existentes.

A precedência é: **configuração individual salva → configuração do perfil → regras anteriores**. A seleção individual é completa: não é somada às permissões do perfil. Uma seleção individual vazia bloqueia as funções de negócio. Alterar posteriormente o modelo de um perfil não reescreve os acessos individuais. **Usar acessos do perfil atual** apenas copia suas opções para revisão; é preciso salvar para aplicar a cópia à conta selecionada.

Na janela de edição, **Salvar alterações** permanece visível no topo e no rodapé e abre a revisão; **Confirmar e salvar** inicia a gravação. Durante o envio, há um indicador animado e a mensagem **Salvando…**, com os controles bloqueados para impedir envios duplicados. A requisição de gravação aguarda até 45 segundos. Em falha de rede, timeout ou resposta 5xx, a interface consulta a versão salva e compara a seleção completa antes de informar sucesso; nunca reenvia a gravação automaticamente. Se o resultado continuar incerto, preserva as alterações na tela e oferece **Conferir salvamento**. A ativação da aplicação das permissões continua dependendo das opções do ambiente.

As ações são verificadas no servidor por usuário, com cache restrito à requisição e identificado pela conta. Usuários com o mesmo tipo podem ter conjuntos distintos. O tipo, a senha, a prefeitura, a região e os vínculos de equipe não são alterados pela central. Restrições próprias de identidades especiais, como o acesso dedicado de Ortomosaicos, continuam valendo; personalizar ações não converte uma conta em outro tipo operacional.

Dev e Gestor de TI continuam administrando a central. Somente Dev pode editar os acessos individuais de contas Dev, inclusive retirar suas funções de negócio. A administração da própria Central de TI continua vinculada à identidade Dev, permitindo corrigir uma seleção vazia sem perder o acesso à central. As seleções recebem versão, autor, usuário afetado e auditoria de antes/depois. Edições concorrentes retornam conflito e exigem revisão; não há sobrescrita automática. A validação CSRF da central e a proteção global, quando habilitada, são verificadas separadamente.

Para ativar em um ambiente compatível, depois de instalar e validar a estrutura:

```dotenv
CENTRAL_TI_ENABLED=1
CENTRAL_TI_ENFORCE_PERMISSIONS=1
CENTRAL_TI_USER_PERMISSIONS_ENABLED=1
```

A última opção permanece desativada por padrão. Ao ativá-la, `/central-ti` abre o modo individual; `/central-ti?modo=perfis` mantém os modelos anteriores. Desativar apenas a última opção restaura o controle por perfil, preservando as configurações individuais para uma futura retomada. Isso pode restaurar acessos retirados individualmente; a troca deve ser deliberada.

Foram acrescentadas as tabelas `central_ti_usuarios_configuracoes`, `central_ti_usuarios_selecoes` e `central_ti_usuarios_auditoria`, na revisão `d92e7a4b6c81`, após `c81f0e2a4d67`. A revisão é aditiva, reutiliza uma estrutura preparada equivalente e recusa uma estrutura parcial. O downgrade remove os dados individuais e não é a forma recomendada de desativar o modo.

**Neon, 24/11/2026:** as três tabelas foram preparadas com autorização, sem criar seleções individuais. Os 31 usuários e as três tabelas da central anterior foram preservados, com comparação de contagens e resumos determinísticos antes/depois. O `alembic_version` foi mantido em `a3e5c7d901b2`; esta preparação não declara como executadas outras migrações pendentes. A conexão foi obtida da variável Neon comentada, sem usar a conexão Render ativa do checkout. Código e opção de ativação não foram publicados nesta etapa.

O preparador aceita somente destinos Neon diretos com SSL. Seu modo inicial é somente leitura:

```sh
.venv/bin/python scripts/prepare_central_ti_users_neon.py
.venv/bin/python scripts/prepare_central_ti_users_neon.py --apply --expected-target IDENTIFICADOR_DA_INSPECAO
```

Os testes usam SQLite descartável para cobrir isolamento entre contas do mesmo perfil, seleção vazia, herança inicial, auditoria, concorrência, CSRF, consultas, proteção de contas e preservação de vínculos. A tela foi exercitada no navegador com contas fictícias: seleção, personalização, revisão, salvamento e leitura após recarregar. A preparação e a validação do schema também foram executadas no PostgreSQL do Neon autorizado. Isso não representa uma auditoria de todas as combinações de telas e integrações do sistema.

## Como configurar os modelos por perfil

1. Entre como Dev ou Gestor de TI e abra a Central de TI.
2. Selecione o tipo de usuário. As regras existentes aparecem marcadas quando esse perfil ainda não possui uma configuração própria.
3. Habilite a área desejada e marque **Consultar** no módulo para liberar sua tela.
4. Marque separadamente **Cadastrar**, **Editar**, **Excluir**, **Exportar** ou as ações específicas, como **Concluir**, **Aprovar**, **Operar** e **Gerenciar mídias**.
5. Clique em **Salvar alterações** e confirme o alerta. A confirmação salva todos os perfis com alterações pendentes, em uma transação.
6. Recarregue a página do usuário para atualizar o menu e os botões. A próxima requisição já consulta as novas regras, inclusive em uma sessão que estava aberta.

Exemplo: `Sistema → Estoque → Consultar` permite ver os itens. Sem Editar e Excluir, seus controles ficam ocultos e chamadas diretas às rotas correspondentes recebem HTTP 403. Acrescentar Editar libera o formulário e sua gravação, mantendo Excluir bloqueado.

Ao marcar uma ação, a central também marca Consultar. Retirar Consultar remove as ações do módulo. Uma área desabilitada impede suas funções mesmo que restem seleções gravadas.

## Preservação das regras anteriores

- Perfis sem configuração própria mantêm as verificações anteriores. Os registros neutros criados na preparação do Neon não revogam acessos.
- Salvar um perfil passa a usar sua lista explícita; salvar uma lista vazia bloqueia suas funções de negócio.
- As permissões liberam funcionalidades. Não transformam o usuário em administrador nem trocam seu tipo.
- Permanecem os vínculos e filtros de prefeitura, região, equipe, propriedade do registro e empresa. Um perfil sem vínculo necessário pode abrir uma tela autorizada e não ter registros disponíveis.
- O Financeiro permanece na central financeira. O menu respeita a área em uso e a seleção de empresa existente.
- A sidebar conserva os ícones, nomes, ordem e menus expansíveis anteriores. Prefeitura, Agro e Financeiro mantêm seus próprios menus; a Central de TI determina a visibilidade das opções dentro de cada área. Não há uma tela ou opção "Seus acessos" para os usuários.
- Quando a tela inicial habitual não estiver autorizada, o login abre uma tela de negócio permitida. Perfis sem nenhuma função de negócio recebem somente uma página inicial neutra.
- A Central de TI continua reservada a Dev e Gestor de TI. O acesso administrativo à própria central é preservado mesmo ao limpar as demais permissões desses perfis.
- Administradores de usuários delegados não podem assumir ou criar contas de perfil mais privilegiado que o próprio. As proteções específicas das contas Dev, Diretor e Gestor de TI permanecem.

## Proteções implementadas

O servidor verifica uma política explícita por rota e método HTTP, antes de executar a função. Esconder controles é apenas a parte visual: requisições manuais continuam sujeitas à mesma autorização.

Consultar, gravar, excluir, exportar e gerenciar arquivos têm verificações separadas. Alterar o status de uma solicitação e atribuir uma equipe também exigem suas permissões específicas; Editar isoladamente não concede essas ações.

As configurações são carregadas uma vez por requisição, sem cache de autorização compartilhado entre processos. Isso evita manter uma permissão revogada até o usuário sair e entrar novamente. Uma falha na consulta de permissões retorna indisponibilidade (503), sem restaurar permissões amplas como alternativa.

Foram mantidos o CSRF, a auditoria de alterações e o controle de versões para evitar sobrescritas concorrentes. Rotas novas precisam de política explícita; a ativação verifica a cobertura e recusa rotas protegidas sem mapeamento.

## Ambiente e ativação

A aplicação exige as duas opções:

```dotenv
CENTRAL_TI_ENABLED=1
CENTRAL_TI_ENFORCE_PERMISSIONS=1
```

As opções são carregadas do ambiente de cada processo. Alterá-las exige reiniciar os processos correspondentes. O destino atualmente configurado em um checkout não comprova a configuração do serviço publicado.

O registro de preparação do Neon em `central-ti-neon-preparacao.json` é uma evidência histórica: as três tabelas foram instaladas separadamente, sem avançar o histórico geral do Alembic. Ele não representa o estado atual de produção nem autoriza aplicar todas as migrações pendentes nesse banco de homologação.

Para produção, as opções permanecem desativadas por padrão. A estrutura da central deve existir e ser validada antes de habilitar o controle.

Para voltar às verificações anteriores, defina `CENTRAL_TI_ENFORCE_PERMISSIONS=0` no ambiente correspondente e reinicie os processos. As configurações e a auditoria ficam preservadas. Essa reversão restaura as regras legadas, inclusive acessos que tenham sido retirados na central.

## Migração e implantação

A revisão existente `c1a0f8b6d2e4` foi promovida para `migrations/versions/c1a0f8b6d2e4_add_central_ti_configurations.py`, após `a71d9c4e203b` (documentos da prefeitura). O histórico passa a ter uma única ponta. Não há uma segunda migração da mesma estrutura.

O upgrade tem três resultados possíveis:

- As três tabelas ausentes: valida a tabela `usuarios` existente e acrescenta somente `central_ti_perfis_configuracoes`, `central_ti_selecoes`, `central_ti_auditoria` e seus índices. Não popula perfis, cria contas ou modifica registros operacionais.
- As três tabelas presentes: confere o contrato de colunas, tipos, tamanhos, nulabilidade, defaults, chaves, regras de exclusão, CHECKs e índices. Uma estrutura equivalente é reaproveitada sem recriação ou alteração de configurações e auditoria.
- Estrutura parcial ou incompatível: interrompe a migração; não tenta corrigir nem apagar tabelas automaticamente.

No PostgreSQL, a revisão usa a transação DDL do Alembic, limites locais de espera por lock (5 segundos) e de execução por instrução (60 segundos), além de advisory lock compartilhado com o preparador do Neon. Isso protege o passo de criação; o deploy deve continuar tendo **um único executor da migração**, pois o lock interno não abrange a leitura inicial e a gravação final da revisão pelo Alembic.

O Procfile atual já executa `db upgrade` antes de iniciar o servidor. Colocar a revisão no histórico ativo significa que uma publicação poderá aplicá-la automaticamente. Antes de publicar, confira o backup/restauração e a revisão real da produção, mantenha as duas opções da central desativadas e controle a execução única do upgrade. Confira schema, revisão e fluxos existentes antes de liberar a interface e, depois, o controle das permissões.

A revisão exige uma conexão online para inspecionar as tabelas existentes; `upgrade --sql` não é suportado por esse passo. Não use `stamp head` para alinhar o Neon: isso registraria como aplicadas outras migrações que podem não ter sido executadas.

O preparador `scripts/prepare_central_ti_neon.py` carrega a mesma revisão promovida. Seu destino continua restrito ao Neon, com conferência de fingerprint e execução de escrita somente com `--apply`. Ele não avança o `alembic_version` geral. Não deve ser usado para migrar produção.

Em caso de problema na ativação, desligue o controle e reverta o código conforme o procedimento de implantação, preservando as novas tabelas. **O downgrade explícito remove as três tabelas e seus dados**; ele não é o mecanismo recomendado para retorno operacional após começar a usar a central.

`tests/test_central_ti_migration_postgres.py` permite ensaios PostgreSQL em destino de testes explicitamente selecionado, com schemas temporários e rollback ao terminar. Não utiliza o `DATABASE_URL` padrão da aplicação nem avança a revisão do schema público. A validação deve cobrir criação, reaproveitamento com dados, rejeição de estrutura parcial e rollback de DDL em falha.

## Validação e limites

Foram testados bloqueio de todas as rotas de negócio com perfil vazio, liberação e remoção de funções, sessão já aberta, consulta sem edição/exclusão, CSRF, falha de banco, proteção de contas privilegiadas, exportação e isolamento de equipe/prefeitura em relatórios, mídias, denúncias e voos.

A validação visual usou dados fictícios e SQLite em memória: o piloto viu Estoque e Relatórios; Editar apareceu após salvar a permissão, enquanto Cadastrar e Excluir continuaram ocultos. O layout e os componentes globais foram preservados.

Três opções antigas do catálogo ainda não possuem operação implementada e ficam desabilitadas: exportar equipes, operar bancos e importar em ferramentas técnicas. A importação de voos existente é controlada no módulo Logs de voo DJI. Não foi criada uma função apenas por existir uma opção no catálogo.

Este trabalho não substitui uma auditoria de segurança nem comprova execução de todos os fluxos externos (armazenamento de vídeo, rastreamento, APIs de terceiros). Também não implementa cadastro de novas empresas ou isolamento novo por CNPJ; conserva o alcance da central financeira existente.

O Procfile e o mecanismo de timeout não foram alterados nesta etapa.
