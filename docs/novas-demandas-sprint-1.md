# Novas demandas — Sprint 1

Implementação local de R01 (retorno à listagem) e R02 (execução sem aplicação), em 12/11/2026. A entrega não comprova publicação ou validação em produção.

## R01 — Preservar o contexto após editar uma solicitação

Os links de edição das listagens administrativa e da UVIS transportam a URL da lista. O formulário conserva esse destino ao salvar, cancelar ou apresentar erro de validação. Página, filtros repetidos, busca e quantidade de itens da listagem administrativa são preservados.

O retorno aceita somente a listagem correspondente ao perfil, na própria aplicação. URLs externas, ações e a própria tela de edição não são destinos de retorno. O acesso direto ao formulário utiliza a listagem como destino padrão; uma referência de origem válida também pode fornecer o contexto.

Se uma alteração remover a última página do resultado filtrado, a listagem abre a última página ainda disponível. Uma busca sem resultados permanece com os mesmos filtros na página 1.

## R02 — Formulário conforme a execução

| Informação | Com aplicação | Apenas monitorado | Nenhum voo realizado |
| --- | --- | --- | --- |
| Situação, DA, responsável ACE, data e horários do atendimento | Obrigatórios para concluir | Obrigatórios para concluir | Obrigatórios para concluir |
| Larva visualizada, criadouro e tratamento adicional | Obrigatórios | Obrigatórios | Opcionais; sem preencher uma observação automaticamente |
| Detalhamento do tratamento adicional | Obrigatório quando informado SIM | Obrigatório quando informado SIM | Obrigatório quando informado SIM |
| Produto, formulação, dosagem, tipo de aplicação, quantidade administrada, taxa de área e ponta | Obrigatórios | Não aplicáveis | Não aplicáveis |
| Motivo da não realização | Opcional | Opcional | Obrigatório para concluir |

O formulário oculta e desabilita o bloco de dosagem nos dois cenários sem aplicação. Trocar temporariamente de situação conserva os valores digitados no navegador. Ao salvar uma situação sem aplicação, o servidor limpa os campos exclusivos da aplicação, inclusive valores padrão ou antigos enviados por um navegador desatualizado. A mesma limpeza ocorre ao concluir uma OS sem aplicação já salva anteriormente.

O planejamento de dosagem é preservado separadamente como histórico. Não são inventados horários, respostas de observação, dosagens ou quantidades executadas. O formulário continua permitindo salvar um preenchimento parcial; os campos obrigatórios são verificados ao concluir. A consulta pela UVIS e o controle de edição mantêm suas permissões.

Não há alteração de schema nem migração de dados em lote. Registros antigos são normalizados somente quando salvos ou concluídos nesses cenários.

## Verificação

- [Fluxos HTTP em SQLite isolado](../tests/test_sprint1_workflows.py): página 10, filtros repetidos, salvamento, cancelamento, validação, destinos de retorno, páginas removidas, conclusão com e sem aplicação e consulta por perfil.
- [Regras da interface](../tests/piloto_os_situacao.test.cjs): mudança de situação, obrigatoriedade, ausência de respostas inventadas e preservação de bloqueios de edição.
- Regressões relacionadas: `test_redirects.py`, `test_uvis_os_media_access.py`, `test_solicitacao_place_id_block.py`, `test_edit_control.py` e `edit_control_browser.test.cjs`.

O aceite no ambiente de homologação deve repetir edição e conclusão com dados fictícios, utilizando os perfis administrativo, UVIS e piloto.
