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

O controle foi habilitado **somente no `.env` local**, cujo destino foi conferido como o Neon de testes autorizado. O processo local já aberto precisa ser reiniciado para carregar código e configuração novos.

Nesta etapa não foram executadas migrações nem alterados registros do Neon ou de produção. A inspeção do Neon usou transação somente de leitura: três tabelas existentes, 20 perfis, uma configuração própria no perfil Dev e 19 perfis com regras anteriores. Após reiniciar, o Dev passa a respeitar sua configuração já salva, mantendo acesso à Central de TI.

Para produção, a opção nova permanece desativada por padrão. A publicação e a ativação nesse ambiente não foram feitas. A estrutura da central deve existir antes de habilitar o controle.

Para voltar às verificações anteriores, defina `CENTRAL_TI_ENFORCE_PERMISSIONS=0` no ambiente correspondente e reinicie os processos. As configurações e a auditoria ficam preservadas. Essa reversão restaura as regras legadas, inclusive acessos que tenham sido retirados na central.

## Validação e limites

Foram testados bloqueio de todas as rotas de negócio com perfil vazio, liberação e remoção de funções, sessão já aberta, consulta sem edição/exclusão, CSRF, falha de banco, proteção de contas privilegiadas, exportação e isolamento de equipe/prefeitura em relatórios, mídias, denúncias e voos.

A validação visual usou dados fictícios e SQLite em memória: o piloto viu Estoque e Relatórios; Editar apareceu após salvar a permissão, enquanto Cadastrar e Excluir continuaram ocultos. O layout e os componentes globais foram preservados.

Três opções antigas do catálogo ainda não possuem operação implementada e ficam desabilitadas: exportar equipes, operar bancos e importar em ferramentas técnicas. A importação de voos existente é controlada no módulo Logs de voo DJI. Não foi criada uma função apenas por existir uma opção no catálogo.

Este trabalho não substitui uma auditoria de segurança nem comprova execução de todos os fluxos externos (armazenamento de vídeo, rastreamento, APIs de terceiros). Também não implementa cadastro de novas empresas ou isolamento novo por CNPJ; conserva o alcance da central financeira existente.

O Procfile e o mecanismo de timeout não foram alterados nesta etapa.
