# Central de TI: telas e ações por tipo de usuário

Implementação validada em 09/10/2026. A configuração pertence ao tipo de usuário (por exemplo, Piloto OA, Financeiro ou Admin Prefeitura) e vale para todas as pessoas daquele tipo.

## Como configurar

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
