# OS de manutenção em uma única página

Implementação local em `codex/os-manutencao-unificada`, a partir de `489aa22`.

## Comportamento

A abertura continua em Manutenção → Abrir OS de manutenção. Após escolher o drone e informar o motivo, o atendimento reúne os dados cadastrados do equipamento, o relato de entrada com data e hora, as fotos, o diagnóstico, as avarias por peça, os componentes usados no reparo, os testes e a conclusão.

Os dados do drone e a responsabilidade atual são consultados no cadastro e na equipe vinculada. Informações ausentes não são inventadas. O cadastro de peças passa a ter Código DJI / Part Number, separado do número de série.

- **Salvar rascunho:** permite atendimento incompleto, conserva as peças selecionadas e não reserva nem desconta estoque.
- **Concluir:** exige recebimento, condição de chegada, relato, diagnóstico, tipo de manutenção, técnico, serviços, testes e condição final. Peças de reposição são opcionais, pois uma preventiva pode envolver apenas limpeza ou ajuste.
- **Apto / apto com ressalvas:** requer confirmação de testes e devolve o drone ao status Ativo.
- **Inapto:** permite concluir o registro sem liberar o equipamento, que fica Inativo.
- As peças avariadas descrevem o diagnóstico e não movimentam estoque. Também é possível descrever uma peça que ainda não esteja cadastrada.
- As peças novas do reparo exibem código DJI, quantidade, disponibilidade e observação individual. Saldo e compatibilidade são conferidos novamente na conclusão.
- Consumos já feitos por versões anteriores permanecem no histórico e não são descontados outra vez. Novos consumos guardam nome, código e série como eram no momento do reparo.
- Histórico, PDF e Excel incluem as novas informações. O formulário avisa sobre gravação em andamento e confirma quando o rascunho foi salvo.

## Compatibilidade de peças

O formulário do estoque usa somente modelos compatíveis. Não há mais a lista lateral de equipamentos específicos. Selecionar um modelo permite uso em todos os equipamentos desse modelo **da mesma prefeitura**, com um saldo compartilhado.

`T10`, `AGRAS T10` e `DJI Agras T10` são apresentados como `AGRAS T10` e comparados como o mesmo modelo. A regra também reconhece os demais códigos agrícolas T com os mesmos prefixos. O modelo isolado `TESTE`/`TEST` não aparece como opção. Os cadastros dos equipamentos não são renomeados nem excluídos.

Vínculos antigos continuam armazenados até uma edição deliberada pelo novo formulário. Seus modelos são considerados na compatibilidade. Ao salvar a edição, valem os modelos escolhidos, substituindo os vínculos específicos.

## Gravação e permissões

A conclusão usa uma transação: versão esperada da OS, bloqueio do equipamento, atualização condicional do saldo, registro dos consumos e encerramento. Uma versão antiga não sobrepõe outra aba; um envio repetido de uma OS encerrada apenas mostra o histórico. Saldo insuficiente desfaz toda a conclusão.

O antigo POST `/equipamentos/<id>/manutencao/encerrar` encaminha para a página de atendimento e não conclui a OS sozinho. Assim, um formulário antigo não pode encerrar uma nova OS do mesmo drone.

As permissões e os limites de prefeitura existentes são reutilizados. Esta implementação não cria usuários, não concede acessos e não altera configurações da Central de TI. A gravação e os anexos continuam protegidos por autenticação, autorização e CSRF.

Fotos continuam no armazenamento de anexos existente, com acesso pela OS autorizada. Falha na validação ou na transação preserva o estoque; novos uploads conhecidos são removidos em compensação. Após um erro, o formulário pede a seleção dos arquivos novamente, pois o navegador não repõe campos de upload.

## Migração e ativação

Revisão: `f2b6a9c4e830`, posterior a `d4a92e5b7c18`.

A migração adiciona campos em `estoque_pecas`, `manutencoes_equipamentos` e `manutencao_pecas_usadas`. Não altera saldos, relatos antigos, nomes de modelos, usuários ou permissões. Registros anteriores recebem versão 0; novos campos históricos ficam vazios.

A mudança exige aplicar a migração no banco de destino antes de executar o novo código. O código anterior aceita essas colunas adicionais, permitindo atualizar o esquema antes da publicação. Não executar o novo código contra um banco sem a revisão.

**Nenhuma migração foi executada em Neon ou produção nesta entrega. Nenhum merge ou publicação foi feito.** Antes da ativação, confirmar o destino, obter backup e aplicar a revisão no ambiente autorizado. O downgrade remove os novos campos e deve ser evitado após existirem atendimentos preenchidos; para reverter apenas a aplicação, as colunas adicionais podem permanecer.

## Validação

Resultado final: **110 testes e 32 subtestes aprovados**. O grafo Alembic tem um único head (`f2b6a9c4e830`); o DDL da revisão foi gerado para PostgreSQL e contém apenas 14 adições de colunas.

Os testes usam SQLite descartável. Foram exercitados rascunho, conclusão, histórico, campos obrigatórios, quantidade inválida, saldo alterado após carregamento, compatibilidade, isolamento entre prefeituras, envio repetido, duas abas, estoque legado, falha em anexos e falha no commit. Não houve teste de concorrência com um servidor PostgreSQL real.

O navegador foi conferido com os templates e rotas reais, banco SQLite e dados fictícios: abertura da OS, inclusão/remoção de peças, preenchimento automático de código/saldo, rascunho, duas abas, conclusão e histórico. Os saldos observados após concluir foram 3 → 2 para uma bomba e 6 → 4 para duas juntas; uma nova OS confirmou esses saldos.

A interface foi conferida em 1280 px e 390 px. No celular, a barra de ações permanece no fluxo da página, sem cobrir os campos. Exportações em PDF com relato normal e extenso foram renderizadas e revisadas visualmente; uploads reais no armazenamento externo não foram realizados na conferência, que usa mocks nos testes de anexos.

Comando de regressão do escopo:

```sh
python -m pytest tests/test_manutencao_os.py tests/test_manutencao_unificada.py tests/test_estoque_compatibilidade.py tests/test_estoque_importacao.py tests/test_preventivas.py tests/test_manutencao_veiculos_access.py tests/test_baterias_gestao.py tests/test_controles_remotos.py -q
```

## Refinamento da interface e sidebar

A tela foi reorganizada de acordo com a referência: resumo do drone, relato de entrada, diagnóstico com avarias e compatibilidade por peça, fotos/evidências, itens do reparo e conclusão. Os campos se redistribuem pela largura disponível do conteúdo, levando em conta a sidebar. Código DJI e identificação da peça aceitam textos longos sem expandir as colunas.

As ações ficam no fim do formulário, sem cobrir campos. Foram adicionados controles de quantidade, prévia das fotos e remoção de fotos ainda não enviadas. Os nomes enviados ao servidor e as regras de estoque/rascunho/conclusão foram preservados.

A sidebar passou a exibir **Manutenção → Ordens de serviço / Histórico de OS / Preventivas**. Cada link usa as permissões da sua rota; usuários personalizados também podem vê-los quando autorizados. Nenhuma permissão é concedida pela navegação. As sidebars Agro e Financeiro continuam separadas.

Conferência visual com dados fictícios longos em 320, 390, 768, 1024 e 1440 px: nenhum controle saiu do conteúdo e não houve transbordamento horizontal nas medições finais. Foram exercitados os controles de quantidade, adição/remoção de fotos antes do envio, salvamento de rascunho e abertura do histórico pela sidebar. As validações são de navegador, sem teste em aparelho físico.

Regressão específica do refinamento e da navegação: **76 testes e 555 subtestes aprovados**, incluindo retirada de acesso, consulta sem edição, usuário personalizado e separação das áreas. A prévia anterior foi reiniciada para remover o HTML antigo mantido em memória; o ambiente temporário passou a recarregar templates ao editar. O JavaScript também tolera a ausência dos novos controles em um formulário anterior.
