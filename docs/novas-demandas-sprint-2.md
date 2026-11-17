# Novas demandas — Sprint 2

## R04 — Contadores de anexos no painel do piloto

Em **Ordens de Serviço**, cada OS do dia mostra a quantidade de imagens e vídeos salvos, abaixo da situação e do protocolo. A contagem de imagens soma a foto principal e as imagens complementares vinculadas à OS. Sem anexos, o painel mostra zero.

O contador usa os vínculos dos arquivos salvos, independentemente das quantidades preenchidas manualmente no formulário. Selecionar um arquivo no computador ou ter um envio recusado não aumenta o contador. Após salvar ou remover um anexo, a contagem aparece atualizada na próxima abertura ou atualização do painel.

O recorte continua respeitando equipe, prefeitura, dia, busca e paginação do piloto. As referências das mídias são carregadas junto das OS da página, sem consultar o armazenamento remoto para cada linha.

### Verificação

[Fluxos HTTP em banco SQLite isolado](../tests/test_os_media_dashboard.py) cobrem upload e remoção simulados, erro no envio, divergência de quantidades manuais, paginação, isolamento municipal e por equipe e ausência de equipe ativa. Os testes de mídia da UVIS e da Sprint 1 verificam os contextos e formulários relacionados.

Esta entrega é local, sem migração de banco, alteração de dados existentes ou comprovação de publicação.

## Correções de cadastro e triagem

Falhas reproduzidas com dados fictícios em testes SQLite isolados:

- **Seleção de UVIS e listagem regional:** a atribuição aceitava a região com espaços extras, mas os filtros SQL não aplicavam a mesma limpeza. Agora a seleção, a listagem e o contador de denúncias desconsideram espaços no início e no final da região. O município, a coordenadoria e as permissões continuam sendo verificados; não há alteração dos cadastros salvos.
- **Bloqueio de endereço antigo:** a busca textual considerava somente os 300 bloqueios mais recentes, permitindo cadastrar um endereço já bloqueado que estivesse fora desse recorte. A busca passa a ler os campos do endereço em lotes de 300, sem descartar o histórico anterior. As condições existentes permanecem: o endereço só bloqueia novas solicitações quando estiver marcado para bloqueio, com OS concluída, na mesma prefeitura.

Os testes de [encaminhamento de denúncias](../tests/test_denuncias_workflow.py) e [bloqueio de endereços](../tests/test_solicitacao_place_id_block.py) cobrem os cenários reproduzidos, a preservação do DA informado na conversão e casos em que um novo cadastro deve continuar permitido. A comparação textual ainda pode ser custosa em bases extensas; criar uma chave indexada dependeria de mudança de banco, fora desta entrega.

Não foi confirmado um defeito específico das contas de Jaçanã/Santana ou uma nova regra para preenchimento do DA. Esses pontos permanecem em aberto, sem ajustes presumidos. Nenhuma consulta ou atualização do banco configurado foi feita nesta etapa; os testes utilizam somente SQLite em memória.

## R03 — Vários vídeos por OS

Adiado a pedido do usuário, para tratar separadamente os problemas de desempenho dos vídeos. O contador desta etapa reflete o único vídeo que a OS suporta atualmente. Não houve ampliação do envio de vídeos nesta entrega.

## Autopreenchimento de veículo e drone

Escopo confirmado: **Checklist Semanal** e **campos de drone da OS**. A OS continua sem campo de veículo; não foram criadas colunas ou migrações.

- **Checklist Semanal:** a seleção única já existia. Agora a sugestão prioriza o veículo ativo vinculado à equipe do piloto, mesmo quando ele tem acesso a outros veículos por responsável. A prioridade do veículo atribuído diretamente ao supervisor foi preservada. Sem uma opção única, a escolha permanece manual; uma escolha válida recebida pelo formulário continua sendo respeitada. Equipamentos de outro município não entram nas opções autorizadas.
- **OS do piloto e formulário administrativo:** seleciona o único drone ativo da equipe em cada categoria, pulverização e monitoramento. Preenche a identificação do equipamento e o prefixo, mantendo a possibilidade de troca manual. Havendo vários drones da mesma categoria, o sistema não escolhe um arbitrariamente.
- **Preservação do registro:** abrir o formulário não cria nem atualiza a OS. IDs, identificação técnica e prefixos já registrados são mantidos quando o equipamento permanece o mesmo, inclusive se o cadastro do drone mudou posteriormente. Equipamento antigo indisponível para nova seleção aparece com a identificação já registrada na OS. Ao escolher outro drone, a validação de município, equipe, situação ativa e categoria continua obrigatória.
- **Situação da execução:** uma OS sem voo não recebe sugestões de drones; uma OS somente monitorada recebe apenas a sugestão de monitoramento. Durante a edição, mudar para uma situação sem voo retira apenas as sugestões automáticas, preservando escolhas manuais e registros anteriores. Formulários de consulta e OS concluídas não recebem novos equipamentos por inferência.

### Verificação

Os [testes de equipamentos](../tests/test_equipment_autofill.py) usam exclusivamente SQLite em memória e verificam seleção, gravação somente no envio, opções ambíguas, identificação histórica e isolamento por equipe e prefeitura. Os [testes da interface](../tests/piloto_os_equipamentos.test.cjs) verificam o preenchimento da identificação, troca manual, preservação de valores e interação com a situação da execução.

Em 17/11/2026, a bateria delimitada passou com **63 testes Python, 102 subtestes e 11 testes JavaScript**. Incluiu os fluxos da Sprint 1, a consulta de OS pela UVIS, o Checklist Semanal, o isolamento municipal de drones e a prioridade do equipamento do supervisor. A prévia em navegador, identificada como dados fictícios em memória, confirmou o preenchimento dos dois drones na OS, a retirada da sugestão de pulverização em “Apenas monitorado” e a seleção do veículo no Checklist. Log: `/private/tmp/ija-equipment-autofill-regression-20261117.log`.

Não houve acesso ao banco configurado, publicação ou alteração de integrações externas nesta etapa.
