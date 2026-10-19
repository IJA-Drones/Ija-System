# Acompanhamento CONDOMAR - 17/10/2026

Registro das decisões após o PDF de pendências de 17/10 (atualização 2).

| Item | Situação de acompanhamento | Evidência e limite |
| --- | --- | --- |
| 4.5.1 | Correção implementada; homologar após publicação | Novas equipes UVIS herdam a prefeitura validada da UVIS. Testes isolados verificam o próprio acesso e a negativa entre municípios. Não foi aplicado novo ajuste de dados em produção. |
| 4.5.3 | **ATENDE**, conforme aceite operacional do responsável | Reserva, versão, expiração, liberação e interface implementadas no escopo de solicitações/OS/denúncias. Mantidas, por decisão expressa, as exceções dos quatro perfis operacionais. Isto não declara reserva universal nos cadastros de estoque, financeiro e Agro. |
| 4.5.5 | **ATENDE**, conforme confirmação do responsável | Controle de inatividade existente e configuração considerada correta pelo usuário. |
| 4.5.4 | **ATENDE POR ACEITE INTERNO — arquivamento no Skybox**, conforme decisão do responsável | O responsável considera a trilha e o arquivamento no Skybox suficientes para o acompanhamento interno. Ressalva técnica: o Skybox atual usa WebDAV; o envio syslog TCP/TLS continua desativado, sem coletor configurado. A exigência específica de syslog do edital permanece sem comprovação de atendimento. O emissor foi preparado e depende de migração, configuração e validação de recepção. |
| 4.5.6 | **ATENDE no código e nos testes**, com publicação em produção pendente | Rollback SQL e compensação durável dos arquivos nos fluxos instrumentados; bloqueio de limpeza durante gravação, preservação por vínculo, repetição de falhas e recuperação após interrupção. Migração `f2a91d0c6b38` aplicada ao banco de testes em 17/10/2026. Evidências, implantação e limites em [recuperação de transações](recuperacao-transacoes.md). |

Detalhes: [controle de edição](controle-edicao.md), [acesso municipal](controle-acesso-prefeituras.md) e [syslog](auditoria-syslog.md). Esta classificação é de acompanhamento interno, não aceite emitido pelo contratante.
