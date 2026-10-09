# Mapa de funções por tipo de usuário

O acesso atual combina o campo `Usuario.tipo_usuario`, os vínculos de prefeitura, região, piloto ou equipe e quatro habilitações adicionais. Esta lista organiza as funções existentes para definir a futura central de permissões do Gestor de TI. O perfil Gestor de TI ainda não existe no código.

Referência: código local de 8 de outubro de 2026, commit `744c72c`. As regras abaixo descrevem os controladores, serviços e templates dessa versão. Não são uma confirmação dos usuários cadastrados, da configuração ou do comportamento do ambiente de produção.

O [inventário técnico de rotas](inventario-permissoes-rotas.md) relaciona as 361 declarações de rotas encontradas, com método, endpoint, arquivo, verificações locais e templates explícitos. Uma permissão de consulta não implica permissão para cadastrar, editar, excluir, exportar ou operar um registro.

## Regras comuns

| Regra | Comportamento atual |
| --- | --- |
| Perfil | Cada conta possui um valor em `tipo_usuario`. Não há associação dinâmica entre uma conta e vários perfis de permissões. |
| Prefeitura | Administradores globais `dev`, `diretor` e `admin` não recebem o filtro do helper `apply_prefeitura_scope`. Os demais recebem o filtro quando possuem prefeitura. Sem prefeitura, o helper bloqueia `prefeitura_admin` e os aliases de supervisor; para outros tipos, devolve a consulta sem esse filtro. Outros serviços podem acrescentar restrições. |
| Região | `regional` recebe filtro pela região nas consultas que usam os helpers correspondentes. UVIS possui filtros próprios de região em pilotos e equipes. |
| Piloto e equipe | O piloto OA precisa de vínculo com piloto e equipe; Equipe OA usa `codigo_setor` como identificador da equipe. Piloto Agro precisa de cadastro ativo e equipe Agro. Equipe UVIS usa o vínculo com a UVIS proprietária. |
| Agro | `admin` pode entrar sem `trabalha_agro`. Os demais perfis do painel administrativo precisam dessa habilitação. Perfis financeiros não entram no painel operacional Agro. Piloto Agro tem seu próprio fluxo. |
| Oceano Azul | `trabalha_oceano_azul` habilita, entre outros comportamentos, caixa de entrada e alertas de limpeza. Não substitui o perfil exigido pela rota. |
| Suporte | `suporte_operacional` e `suporte_tecnico` existem nos helpers de atendimento, mas as rotas atuais de tratamento de bugs exigem `dev`. As flags, sozinhas, não liberam essa tela. |
| Administração das flags | Somente `dev` e `diretor` podem alterar as quatro habilitações de trabalho e suporte no cadastro administrativo. |
| Menu e autorização | A sidebar oculta links por perfil e contexto. A autorização efetiva também depende da rota e do serviço chamado. Um link oculto não equivale, por si só, a acesso bloqueado. |

Fontes: [modelo de usuário](../app/models.py), [regras compartilhadas](../app/shared/access.py), [acesso Agro](../app/modules/agro/service.py), [autenticação](../app/modules/auth/service.py) e [sidebar](../app/templates/base.html).

## Desenvolvedor

Código: `dev`. Entrada após login: Painel Dev.

- Consultar e alterar solicitações, aprovações, agendamentos, cancelamentos e formulários administrativos de OS; excluir solicitações; consultar histórico, relatórios e exportações.
- Gerenciar prefeituras, clientes, UVIS, usuários administrativos, pilotos, equipes OA, credenciais operacionais, drones, baterias, veículos e manutenções.
- Administrar perfis `dev` e `diretor`, redefinir senhas e alterar as flags de trabalho e suporte. O editor preserva o próprio tipo de usuário ao editar a própria conta.
- Acessar estoque, painel operacional, importações de drones e logs DJI; consultar e corrigir checklists administrativos.
- Acessar a Central Financeiro, operar caixa, bancos e lançamentos e configurar empresa, identidade visual, competências e categorias, respeitando as regras do registro.
- Acessar o Agro quando `trabalha_agro` estiver habilitado; executar funções administrativas específicas de templates, contratos e OS que usam o guard global.
- Consultar presença, erros, saúde da aplicação e verificações manuais no Painel Dev; consultar auditoria de usuários, gerar e listar backups e consultar logs de veículos excluídos.
- Tratar bugs: assumir, comentar, alterar status, editar ou apagar comentários e registrar a correção. Consultar e encaminhar denúncias nas rotas existentes.

**Exceções:** não é um acesso universal a todas as rotas. Telas exclusivas de UVIS e piloto têm verificações próprias. A exclusão de logs de veículos é permitida somente a `admin`, inclusive quando o ator é Dev.

Fontes: [usuários](../app/modules/usuarios/routes.py), [Painel Dev](../app/modules/dev_dashboard/routes.py), [auditoria](../app/modules/auditoria/routes.py), [backups](../app/modules/backup/routes.py), [bugs](../app/modules/feedback/routes.py) e [frota](../app/modules/veiculos/service.py).

## Diretor

Código: `diretor`. Entrada: painel administrativo da Prefeitura.

- Administrar solicitações, aprovações, agendamentos, OS, histórico, relatórios, anexos e exclusão de solicitações.
- Gerenciar prefeituras, clientes, UVIS, usuários administrativos comuns, pilotos, equipes OA, credenciais operacionais, equipamentos, veículos e manutenções.
- Alterar as flags de trabalho e suporte dos usuários que pode administrar.
- Acessar estoque, painel operacional, importação de drones, logs DJI e consulta ou correção de checklists administrativos.
- Consultar e editar o Agro quando `trabalha_agro` estiver habilitado. Possui também guards globais para templates operacionais e exclusões específicas de contratos e OS.
- Consultar denúncias e executar as ações gerais de encaminhamento e arquivamento que as rotas disponibilizam.

**Limites:** não acessa a Central Financeiro na regra atual; não administra contas Dev ou Diretor; não cria Diretor; não acessa Painel Dev, auditoria, backups, tratamento de bugs ou logs de veículos excluídos; não exclui logs de veículos.

## Administrador

Código: `admin`. Entrada: painel administrativo da Prefeitura.

- Administrar solicitações, aprovações, agendamentos, OS, histórico, relatórios, anexos e exclusão de solicitações.
- Gerenciar prefeituras, clientes, UVIS, usuários administrativos comuns, pilotos, equipes OA, credenciais operacionais, equipamentos, veículos e manutenções.
- Acessar o Agro sem depender de `trabalha_agro`; gerenciar clientes, fornecedores, comercial, pilotos, equipes, equipamentos, banco de talentos e funções administrativas de templates, contratos e OS.
- Importar drones e logs DJI; consultar e corrigir checklists administrativos.
- Corrigir e excluir logs de veículos. A exclusão registra um histórico de auditoria.
- Consultar denúncias e executar as ações gerais de encaminhamento e arquivamento que as rotas disponibilizam.

**Limites:** não acessa a Central Financeiro, estoque ou painel operacional na regra atual; não altera as flags de trabalho e suporte; não cria Diretor nem administra contas Dev ou Diretor. Pode criar o primeiro Dev apenas enquanto nenhuma conta desse tipo existir, conforme `can_assign_dev_role`. Auditoria, backups e tratamento de bugs ficam com Dev.

## Operário

Código: `operario`. Entrada: painel administrativo da Prefeitura.

- Consultar e atualizar solicitações, aprovação, agendamento, equipe responsável, anexação de arquivo e cancelamento pelo painel administrativo.
- Consultar histórico e relatórios, exportar relatórios, consultar e editar formulários administrativos de OS não canceladas e suas mídias.
- Cadastrar, editar e excluir pilotos, equipes OA, drones, baterias e veículos; operar manutenções e corrigir KM de logs de veículos.
- Consultar UVIS. Consultar acessos e membros de equipes UVIS e atualizar o acesso operacional da UVIS nas rotas administrativas.
- Importar planilha de drones, com prefeitura obrigatória para o ator não global.
- Com `trabalha_agro`, consultar e editar clientes, fornecedores, orçamentos, contratos, RD de mapeamento, equipes, pilotos, equipamentos e banco de talentos Agro; editar OS Agro e importar logs de voo Agro.

**Limites:** não gerencia prefeituras ou usuários administrativos; não cria solicitação pela rota `novo`; não exclui solicitações permanentemente; não acessa Central Financeiro, estoque, painel operacional, logs DJI, checklists administrativos ou tratamento de bugs. Templates operacionais e exclusões específicas de contratos e OS Agro exigem administrador global.

## Administrador da Prefeitura

Código: `prefeitura_admin`. Entrada: painel administrativo da Prefeitura vinculada.

- Consultar e atualizar solicitações, aprovações, agendamentos, cancelamentos, histórico e formulários administrativos de OS da prefeitura.
- Criar solicitações e consultar ou exportar relatórios.
- Cadastrar, editar e excluir clientes e UVIS da própria prefeitura.
- Gerenciar pilotos, equipes OA, drones, baterias, veículos e manutenções; corrigir KM de logs de veículos.
- Importar planilha de drones da prefeitura. Com `trabalha_agro`, consultar e editar a operação e o comercial Agro nos mesmos grupos gerais do Operário.

**Limites:** não gerencia usuários administrativos ou prefeituras; não exclui solicitações permanentemente; não acessa Central Financeiro, estoque, painel operacional, checklists administrativos ou tratamento de bugs. O módulo de anexos não inclui esse perfil nas listas de leitura e remoção, apesar de o painel permitir anexar arquivos. Exportação da lista de pilotos e administração de acessos de equipes UVIS possuem listas próprias que não incluem esse perfil.

## Regional

Código: `regional`. Entrada: painel administrativo, com região vinculada.

- Consultar solicitações, histórico, OS e mídias, UVIS, relatórios e exportações administrativas dentro dos filtros regionais aplicados.
- Consultar mapas, geolocalização, agenda, exportação de agenda, pilotos e equipes conforme os filtros de região dos serviços.
- Ler anexos de solicitações da região.
- Abrir e acompanhar bugs da coordenadoria, conforme os filtros desse fluxo.
- Nas rotas de denúncias, consultar os registros encaminhados à sua coordenadoria e designar uma UVIS da mesma região.
- Com `trabalha_agro`, consultar o painel Agro, clientes, fornecedores, comercial, OS, equipes, pilotos, equipamentos e logs de voo, sem os guards de edição.

**Limites:** não aprova solicitações, não edita formulários administrativos de OS e não gerencia usuários, clientes ou equipamentos. Não acessa a Central Financeiro. Frota possui uma lista específica que não inclui `regional`; o acesso ao painel administrativo não implica acesso a esse módulo.

## COVISA

Código selecionado no cadastro: `covisa`. O serviço grava esse perfil como `tipo_usuario="visualizar"` e `regiao="COVISA"`; os helpers também reconhecem o valor literal `covisa`.

- Consultar painel administrativo, solicitações, histórico, relatórios, exportações, UVIS, formulários de OS e mídias.
- Na representação gravada `visualizar`, consultar agenda e exportá-la, pilotos, equipes OA e registros de veículos nas listas que incluem esse valor.
- Criar solicitações, pois a rota `novo` inclui explicitamente `visualizar`.
- Abrir e acompanhar bugs do fluxo COVISA.
- Consultar denúncias e realizar triagem, encaminhamento para coordenadoria e arquivamento nas rotas existentes.
- Com `trabalha_agro`, consultar o Agro, comercial e operação sem os guards gerais de edição.

**Limites:** não aprova ou edita OS administrativas, não gerencia usuários ou cadastros operacionais e não acessa a Central Financeiro. O valor literal `covisa` não recebe automaticamente todas as permissões das rotas que aceitam somente `visualizar`. A visão de COVISA não usa o filtro regional de `regional`; o alcance ainda depende dos filtros de prefeitura e dos serviços de cada tela.

## Administrador Financeiro

Código: `financeiro_admin`. Entrada: Central Financeiro.

- Abrir a central e o espaço da empresa disponível, atualmente IJA.
- Consultar clientes, fornecedores, orçamentos, mapeamentos e contratos pelo espaço da empresa; consultar PDFs e anexos comerciais compartilhados.
- Cadastrar, editar e excluir fornecedores. A edição de clientes, orçamentos, contratos e RD de mapeamento permanece vinculada aos guards operacionais Agro, que não incluem o perfil financeiro.
- Operar contas a receber e a pagar, recebíveis, entradas e saídas manuais, lançamentos vinculados a OS, recebimentos e comprovantes.
- Abrir e fechar caixa diário; cadastrar, editar e excluir bancos; consultar conciliação bancária, painel financeiro, relatório geral e exportações financeiras autorizadas.
- Configurar dados da empresa, razão social, CNPJ e logo; configurar liberação de competências e categorias financeiras.

**Limites:** não acessa o painel administrativo da Prefeitura nem o painel operacional Agro. Categorias globais têm restrições próprias de edição. Caixa aberto, competência liberada e validações dos lançamentos continuam obrigatórios. A lista de empresas ainda contém apenas IJA; o perfil persistido de identidade e logo não implementa isolamento geral de todos os registros por CNPJ.

## Financeiro

Código: `financeiro`. Entrada: Central Financeiro.

- Consultar a empresa IJA, clientes, fornecedores e comercial pelo espaço financeiro.
- Operar os mesmos grupos de contas, lançamentos, recebimentos, comprovantes, fornecedores, bancos e caixa diário do Administrador Financeiro.
- Consultar painel financeiro, relatório geral, conciliação e exportações financeiras autorizadas.

**Limites:** não configura empresa, logo, competências ou categorias; não acessa o painel administrativo da Prefeitura nem o painel operacional Agro. As regras de caixa e competência também se aplicam. A distinção atual entre os dois perfis financeiros está concentrada em configurações, e não em tornar `financeiro` somente leitura.

Fontes dos dois perfis: [Central Financeiro](../app/modules/financeiro/routes.py), [catálogo de empresas e menus](../app/modules/financeiro/service.py), [guards Agro e Financeiro](../app/modules/agro/service.py), [operações financeiras](../app/modules/agro/routes.py) e [classificação de endpoints](../app/shared/financeiro_navigation.py).

## Supervisor de veículos

Código principal: `sup_veiculos`. Alias reconhecido em parte do código: `sup_veiculo`. Entrada: painel administrativo.

- Consultar e atualizar solicitações, agendamentos, cancelamentos, histórico, relatórios e formulários administrativos de OS dentro dos filtros aplicados.
- Criar solicitações. Cadastrar, editar e excluir pilotos, equipes, drones, baterias e veículos pelas rotas que incluem o supervisor.
- Consultar frota, logs, limpezas, rastreamento e exportações; atribuir equipe e supervisor a veículos; corrigir KM de logs.
- Consultar e corrigir checklists administrativos de veículos e drones. Preencher seu checklist semanal operacional.
- Abrir e encerrar turno, registrar KM, abastecimento e limpeza; confirmar alertas quando `trabalha_oceano_azul` estiver habilitado.
- Acessar a rotina operacional de OS e dosagem usando a equipe do veículo atribuído como contexto.
- Com `trabalha_agro`, consultar e editar os grupos Agro liberados pelo guard geral de edição.

**Limites e diferenças:** não gerencia usuários administrativos, não acessa Central Financeiro, estoque ou painel operacional e não exclui logs de veículos. A consulta `supervisor_equipment_query` alcança a frota da prefeitura, incluindo veículos sem prefeitura própria cuja equipe tem esse vínculo; não se limita aos veículos com `responsavel` igual ao supervisor. A lista de pilotos não inclui `sup_veiculos`, embora o menu e as rotas de alteração o incluam. O alias singular e a exportação de agenda também variam entre módulos.

## UVIS

Código: `uvis`. Entrada: dashboard de suas solicitações.

- Criar solicitações; editar as próprias enquanto pendentes ou negadas; consultar canceladas e cancelar as próprias conforme o fluxo.
- Consultar histórico de OS, formulários e mídias vinculados às próprias solicitações.
- Preencher o complemento UVIS e informações de retorno automático nos formulários que permitem edição ao solicitante.
- Consultar coleta de imagens, exportações desse relatório e registrar o OK UVIS de visualização nas OS autorizadas.
- Consultar mapas das suas solicitações e agenda, incluindo exportação de agenda.
- Cadastrar ou atualizar seu acesso operacional e credenciais; criar equipes UVIS e cadastrar, editar ou excluir seus membros; atribuir equipe UVIS à própria solicitação.
- Consultar pilotos e equipes OA da região, com filtros próprios; ler anexos das próprias solicitações.
- Nas rotas de denúncias, consultar os registros destinados à UVIS e gerar a solicitação a partir deles.

**Limites:** não acessa o painel administrativo, Agro ou Central Financeiro, não aprova solicitações e não gerencia cadastros de outras UVIS. A sidebar mantém Denúncias como link desabilitado, embora as rotas existam. Alguns cadastros de equipes UVIS ficam disponíveis pelas rotas próprias e pelo Acesso Operacional, com diferenças de exibição na sidebar.

## Equipe UVIS

Código: `equipe_uvis`. Entrada: painel Equipe UVIS; também pode usar o login UVIS operacional se possuir vínculo com a UVIS.

- Consultar solicitações aprovadas ou concluídas, histórico operacional, formulários e mídias da UVIS proprietária.
- Consultar a agenda dessa UVIS e exportá-la.
- Acessar o endpoint de conclusão de OS da equipe, que exige um registro operacional previamente preenchido e ainda não concluído.

**Limites:** o formulário atualmente aberto pela rota `/equipe-uvis/os/<id>/formulario` usa o template unificado em modo de leitura para `equipe_uvis`. Seu POST de retorno automático exige `uvis`. Portanto, não se deve listar o preenchimento desse formulário como função disponível à Equipe UVIS apenas porque há serviços legados de gravação. O escopo operacional atual é a UVIS proprietária, sem filtro por nome de equipe em `_load_solicitacao_para_equipe_uvis`. Não cria solicitações pela rota `novo`, não administra equipes e não acessa Agro ou Central Financeiro.

Fontes dos dois perfis UVIS: [dashboard UVIS](../app/modules/dashboard/service.py), [acessos operacionais](../app/modules/uvis_equipes/routes.py), [painel Equipe UVIS](../app/modules/equipe_uvis_dashboard/routes.py), [regras da Equipe UVIS](../app/modules/equipe_uvis_dashboard/service.py) e [agenda](../app/modules/agenda_notificacoes/service.py).

## Piloto da Oceano Azul

Código: `piloto`. Entrada: painel de OS do piloto.

- Consultar OS aprovadas da equipe ativa, histórico e formulário operacional; preencher o formulário e concluir a OS conforme o estado permitido.
- Calcular e registrar dosagem; consultar dados de drone da equipe.
- Enviar, consultar e remover imagens e vídeos da OS autorizada, inclusive pelos endpoints de upload em partes e acompanhamento do processamento.
- Preencher checklist semanal de veículos e drones vinculados à operação.
- Consultar veículos operacionais, abrir e encerrar turnos, registrar KM, abastecimento e limpeza.
- Consultar agenda da equipe e rotas KML vinculadas às OS; receber e confirmar alertas de limpeza quando `trabalha_oceano_azul` estiver habilitado.

**Limites:** precisa de vínculo de piloto e equipe; não gerencia usuários ou cadastros administrativos, não importa logs DJI e não acessa a Central Financeiro ou o painel administrativo Agro. A exportação de agenda não inclui `piloto` na lista atual.

## Equipe da Oceano Azul

Código: `equipe_oceano`. Entrada: painel operacional de OS, compartilhado com o piloto.

- Consultar, preencher e concluir OS da equipe identificada em `codigo_setor`, com histórico e dosagem.
- Consultar dados dos drones e mídias e operar os uploads de imagens e vídeos das OS autorizadas.
- Preencher checklist semanal operacional, consultar veículos da equipe e operar turnos, KM, abastecimento e limpeza.
- Consultar agenda da equipe, logs de veículos permitidos, mídias desses logs e suas exportações; consultar rotas KML vinculadas à operação.
- Receber e confirmar alertas de limpeza quando `trabalha_oceano_azul` estiver habilitado.

**Limites:** não é usuário administrativo e não altera cadastros gerais; não acessa Central Financeiro, painel administrativo Agro ou importação DJI. A exportação de agenda não inclui esse tipo. O alcance de veículos e logs depende do filtro operacional da equipe e da prefeitura.

## Piloto Agro

Código: `piloto_agro`. Entrada: login exclusivo Agro e painel do piloto Agro.

- Consultar dashboard, equipamentos da equipe, suas OS e mapeamentos vinculados à equipe Agro.
- Criar OS a partir de contrato aprovado e destinado à sua equipe. O controller atual orienta usuários administrativos a deixar a criação da OS com o piloto.
- Editar a OS autorizada, com equipe fixada pelo servidor no fluxo do piloto, e registrar os dados operacionais e a situação da execução.
- Preencher e concluir RD de mapeamento da equipe.
- Consultar rotas KML Agro vinculadas às OS da equipe e utilizar o chatbot do piloto Agro.

**Limites:** precisa de cadastro de piloto Agro ativo e vínculo de equipe. Não gerencia clientes, fornecedores, orçamentos, contratos, pilotos ou equipamentos; não acessa o painel administrativo da Prefeitura nem a Central Financeiro. O login geral encaminha esse tipo para o login exclusivo Agro.

Fontes operacionais: [rotas de OS OA](../app/modules/piloto_os/routes.py), [regras de OS OA](../app/modules/piloto_os/service.py), [checklists](../app/modules/piloto_checklists/routes.py), [turnos e frota](../app/modules/veiculos/service.py), [rotas Agro](../app/modules/agro/routes.py) e [logs Agro](../app/modules/agro/flight_logs_service.py).

## Tipos legados e aliases

| Valor | Tratamento observado |
| --- | --- |
| `visualizar` fora de COVISA | Consulta administrativa, histórico, relatórios, agenda e exportações das listas que incluem o valor; consulta de pilotos, equipes e logs de veículos. Também cria solicitação na rota `novo`, portanto não é somente leitura em todo o sistema. Não recebe os privilégios COVISA de bugs e denúncias sem a região COVISA. Agro de consulta depende de `trabalha_agro`. |
| `visualizador` | Consta no modelo e no conjunto compartilhado de visualização administrativa. Libera painel, histórico, relatórios e consulta Agro com flag, mas não está em várias listas literais de agenda, pilotos, frota, anexos e sidebar. Não é equivalente completo a `visualizar`. |
| `operador` | Aceito por vários guards de cadastro de pilotos, equipes, equipamentos, veículos, importação de drones e acessos UVIS. Não está nos conjuntos compartilhados de acesso ao painel administrativo e Agro. Não é equivalente completo a `operario`. |
| `sup_veiculo` | Reconhecido pelo helper de supervisor, pelos guards de OS e checklist e normalizado para `sup_veiculos` no cadastro administrativo. Algumas rotas de frota, listas e links verificam somente o plural. |
| `covisa` literal | Reconhecido pelos helpers compartilhados, denúncias e bugs. O cadastro normal grava `visualizar` com região COVISA; listas literais que aceitam apenas `visualizar` não abrangem automaticamente uma conta que contenha `covisa`. |

O comentário do modelo cita `supervisor_veiculos`, mas esse texto não aparece como um perfil aceito nos guards mapeados. Comentários e rótulos não substituem os valores utilizados nas verificações.

## Funções por área

| Área ou telas | Consulta e operação | Regras de maior impacto |
| --- | --- | --- |
| Solicitações e dashboard administrativo | Listar, filtrar, aprovar, agendar, atribuir equipe, anexar, cancelar e exportar | Consulta usa `ADMIN_PANEL_VIEW_TYPES`; atualização usa `ADMIN_PANEL_EDIT_TYPES`; criação usa lista própria; exclusão permanente exige administrador global. |
| OS administrativas e mídias | Histórico, formulário, fotos, vídeo, upload, remoção e exportações | Leitura administrativa e edição administrativa são separadas; edição bloqueia OS cancelada; operação do piloto exige vínculo de equipe. |
| Clientes Prefeitura e UVIS | Cadastro, edição, exclusão, listagem e exportação UVIS | Administradores globais e `prefeitura_admin` gerenciam; consulta UVIS aceita o conjunto de visualização administrativa. |
| Usuários administrativos e prefeituras | Cadastro, alteração de tipo, senha, exclusão e flags | Administradores globais; contas Dev e Diretor protegidas; flags apenas Dev e Diretor. |
| Pilotos e equipes OA | Cadastro, credenciais, consulta, alteração, exclusão e exportação | Gestão operacional tem lista própria; exportação de pilotos difere da exportação de equipes. |
| Acessos UVIS | Conta operacional, credenciais, membros e atribuição de equipe | UVIS gerencia seus registros; Dev, Diretor, Admin, Operário e Operador consultam e atualizam acesso operacional nas rotas administrativas. |
| Equipamentos e manutenção | Drones, baterias, ciclos, envio ou encerramento de manutenção, peças, histórico, PDF e Excel | Mutações usam guard operacional; algumas consultas possuem somente login e filtros de consulta. |
| Estoque | Peças, quantidades, status, cadastro, edição, exclusão e Excel | Exclusivo Dev e Diretor. |
| Veículos | Cadastro, atribuição, rastreamento, logs, correção de KM, limpeza e exportações | Listas específicas de consulta e edição; excluir log somente Admin; consultar logs excluídos somente Dev. |
| Turnos operacionais | Abertura, encerramento, KM, abastecimento, limpeza e ciência de alertas | Piloto, Equipe OA e Supervisor plural; regras adicionais de vínculo e flag OA. |
| Checklists | Preenchimento semanal, consulta e correção administrativa | Operacional: Piloto, Equipe OA e Supervisor; administrativo: globais e Supervisor. |
| Agenda e notificações | Agenda, rotas, exportação, ler, limpar ou excluir notificações autorizadas | Agenda aplica filtro por proprietário, equipe, prefeitura ou região; exportação tem lista própria. |
| Relatórios Prefeitura | Solicitações, OS, coleta de imagens, retornos automáticos, PDFs e Excel | Conjunto de visualização administrativa; coleta também aceita UVIS, com filtro de proprietário e ação de OK exclusiva UVIS. |
| Mapas e geolocalização | Mapa, pontos, consulta de endereço e geocodificação | Filtros do serviço; três endpoints de mapa Prefeitura explicitamente bloqueados para perfis financeiros. |
| Agro comercial | Clientes, fornecedores, orçamentos, anexos, PDFs, contratos e RD de mapeamento | Consulta ou edição Agro; fornecedores e comprovantes também compartilham acesso financeiro. |
| Agro operacional | OS, pilotos, equipes, equipamentos, templates e RD | Gestão geral usa guard Agro; templates e exclusões específicas usam guard global; criação de OS ocorre no fluxo do piloto. |
| Banco de talentos | Currículos, PDF, cadastro, análise, reprocessamento, edição e exclusão | Consulta usa conjunto administrativo, sem exigir flag Agro nessa rota; edição exige acesso Agro com edição. |
| Logs de voo DJI | Importar Excel ou KML, vincular OS, desvincular, exportar e baixar arquivos | Gestão DJI apenas Dev, Diretor e Admin; consulta de rota vinculada possui regras adicionais para operação e visualização administrativa. |
| Logs de voo Agro | Importar, vincular, exportar e baixar KML | Consulta ou edição Agro; piloto Agro consulta rotas vinculadas à equipe. |
| Importação de drones | Prévia e importação de planilha Prefeitura ou Agro | Globais, Operário, Operador e Admin Prefeitura; prefeitura obrigatória para não globais. |
| Denúncias | Triagem, encaminhamento, atribuição UVIS, acompanhamento, arquivamento e anexos | COVISA, globais, Regional e UVIS com diferenças por rota; links da sidebar permanecem desabilitados. |
| Bugs | Envio, acompanhamento, anexo, comentário, responsável, status e correção | Regional e COVISA enviam; Dev trata. Flags de suporte não substituem esses guards. |
| Painel operacional | Situação da operação e informações de clima | Dev e Diretor. |
| Central Financeiro | Empresas, consultas comerciais, contas, caixa, bancos, recebimentos e relatórios | Financeiro Admin, Financeiro e Dev; configurações somente Financeiro Admin e Dev. |
| Ferramentas técnicas | Presença, erros, saúde, verificações, auditoria e backups | Dev; webhook de watchdog usa token próprio, não perfil de usuário. |
| Vigilância | Modelo CSV e prévia de validação sem carga no banco | Globais e Admin Prefeitura; depende de `VIGILANCIA_PREVIEW_ENABLED`. |
| Chatbots | Ajuda UVIS, administrativa, Agro e piloto Agro | Listas próprias; chatbot UVIS exige login sem restringir tipo na rota; ajuda não equivale a poder operar os cadastros. |
| Portal do Cidadão | Informações, boletim, denúncia pública, CEP e geocodificação | Fluxo público sem perfil de usuário autenticado. |

## Diferenças que precisam de definição na central de permissões

1. **Admin e Financeiro:** a regra atual não permite `admin` nem `diretor` na Central Financeiro, embora a demanda anterior previsse Admin nos três painéis. Essa diferença foi registrada, sem mudar a regra.
2. **Consulta e alteração:** `visualizar` cria solicitação; Operário aprova pelo painel, mas não cria na rota `novo`; Admin Prefeitura anexa arquivo, mas não está na lista de leitura do módulo de anexos. Cada ação precisa de permissão própria.
3. **Menu e rota:** a lista de pilotos bloqueia Supervisor, apesar do menu e dos endpoints de cadastro e edição incluírem esse perfil. Denúncias estão desabilitadas na sidebar, mas possuem rotas. Há também consultas como `/equipamentos` sem um guard de perfil na rota ou no serviço de listagem, usando login e filtros de prefeitura.
4. **Perfis financeiros:** o bloqueio central protege endpoints Agro operacionais e três endpoints de mapas; isso não constitui um bloqueio geral de toda rota da Prefeitura. Consultas autenticadas de outros módulos precisam entrar no catálogo de permissões.
5. **Isolamento de dados:** empresa ou CNPJ, prefeitura, região, UVIS proprietária e equipe são escopos diferentes. O catálogo financeiro atual ainda contém apenas IJA e reutiliza registros Agro; um CNPJ na configuração visual não cria isolamento de dados multiempresa.
6. **Equipe UVIS:** consulta abrange a UVIS proprietária, e o formulário unificado é somente leitura para a conta de equipe. O endpoint de conclusão e os serviços legados de preenchimento precisam ser tratados como ações separadas.
7. **Denúncias:** encaminhamento e arquivamento verificam acesso ao módulo, mas buscam o registro sem usar o helper de escopo por denúncia nessas duas ações. A matriz futura precisa combinar a ação autorizada com o registro autorizado.
8. **Compatibilidade:** `operario` e `operador`, `visualizar` e `visualizador`, `sup_veiculos` e `sup_veiculo`, e as duas representações de COVISA não possuem comportamento idêntico em todos os módulos.

Para a central de TI, a unidade prática de configuração será a função e sua ação, por exemplo **Solicitações → consultar, criar, aprovar, cancelar, excluir e exportar**, associadas às rotas e às telas que executam essas ações. O perfil define as ações disponíveis; o vínculo define sobre quais registros elas podem ser executadas. Esta lista serve como base para validar essa matriz antes de alterar models ou migrar o banco.
