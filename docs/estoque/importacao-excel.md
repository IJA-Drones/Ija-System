# Importação de peças por Excel

A migração `e64b1d9f203a` cria o registro de prévias e permite arquivar peças sem apagar o histórico das OS. A migração não limpa nem arquiva registros automaticamente; a retirada de itens do estoque é uma operação separada.

## Uso

1. Em **Estoque → Importar Excel**, baixe o modelo padrão.
2. Preencha a aba **Peças**, a partir da linha 6. As abas Instruções e Exemplos não são importadas.
3. Escolha a prefeitura e envie o `.xlsx` para gerar a prévia.
4. Confira os dados e os vínculos encontrados. Ajuste as quantidades na própria prévia e clique em **Validar quantidades**. Para erros em outros campos, ajuste o Excel e envie novamente.
5. Confirme o lote válido. O servidor valida novamente e cadastra todas as linhas em uma única transação.

O envio registra apenas uma prévia de 30 minutos, vinculada ao usuário e à prefeitura; nenhuma peça é cadastrada antes da confirmação. O acesso usa a permissão existente `sistema.estoque.criar`.

## Regras do modelo

- Peça e quantidade são obrigatórios. Quantidade deve ser inteira, de 0 a 2.147.483.647.
- Número de série é opcional e deve ser texto, preservando zeros à esquerda. Não pode repetir uma série do estoque ativo.
- Localização física, status e observações são opcionais. Status vazio significa Disponível para manutenção.
- Vários modelos ou números de série dos equipamentos são separados por ponto e vírgula. Os nomes e séries devem existir na prefeitura escolhida.
- Um único saldo serve aos modelos **ou** aos equipamentos indicados. A importação mantém os vínculos compartilhados; o uso posterior continua registrado na OS de manutenção.
- São aceitos até 1.000 itens em um `.xlsx` de até 5 MB. Linhas vazias são ignoradas; fórmulas e colunas desconhecidas são rejeitadas.
- Qualquer linha inválida bloqueia o lote inteiro. A prévia identifica duplicidades dentro da planilha e conflitos com o estoque.
- Reenviar o mesmo conteúdo já concluído para a mesma prefeitura é bloqueado, inclusive sem números de série e com linhas reordenadas. Não é um fluxo para somar saldo a peças existentes.

## Validação local

Os testes de `test_estoque_importacao.py` usam apenas SQLite em memória. Cobrem upload, modelo, prévia, confirmação, compatibilidade, isolamento, CSRF, expiração, duplicidades e rollback do lote. O teste da migração também utiliza um banco descartável, sem conexão ao banco da aplicação.

O arquivo entregue ao usuário fica em `app/resources/estoque/modelo_importacao_pecas.xlsx`.

## Inventário por modelo do Fernando

Também são aceitos `.xlsx` e `.xlsm` com abas T10, T20, T30 e T40 e as colunas ITEM, MODELO, CÓDIGO INTERNO, LOCALIZAÇÃO FÍSICA, DESCRIÇÃO DA PEÇA, QUANTIDADE e OBSERVAÇÕES. Macros não são executadas nem preservadas. A aba RESUMO GERAL não gera estoque.

- A prévia identifica a aba e a linha original. Linhas com apenas ITEM/MODELO preenchidos são espaços reservados e são ignoradas.
- Descrição vira o nome da peça; localização física e observações são preservadas. O código interno aparece na prévia e é preservado nas observações com o prefixo `Código interno:`. Ele não é número de série; não é preenchido como tal.
- Abreviações T10, T20, T30 e T40 correspondem aos modelos AGRAS dessas famílias. As compatibilidades do inventário podem ser cadastradas mesmo sem um drone daquele modelo na prefeitura; nenhum equipamento é criado ou vinculado por isso. Outros modelos continuam sujeitos à validação do catálogo existente.
- Conforme esclarecimento do usuário em 26/11/2026, cada linha do inventário representa uma peça separada, mesmo com código, descrição e quantidade repetidos. Cada registro e seu saldo são mantidos individualmente, inclusive quando há a observação “JUNTO COM T10”. Não são somadas quantidades nem unificados registros automaticamente. A proteção contra reimportar o arquivo inteiro permanece ativa.
- Quantidades vazias e expressões como `13+5` permanecem pendentes. Não são convertidas em zero nem calculadas automaticamente. O usuário pode substituí-las por uma quantidade inteira na própria prévia, mantendo o valor original visível. Zero deve ser informado explicitamente.
- **Validar quantidades** atualiza somente a prévia e refaz a validação. A entrada no estoque continua dependendo de **Confirmar importação**, com o lote inteiro válido. Valores negativos, fracionados ou acima do limite continuam bloqueados. As revisões não ampliam a validade de 30 minutos da prévia.
- Uma revisão antiga não pode sobrescrever quantidades atualizadas em outra aba. Se houver alterações ainda não validadas ao tentar confirmar, elas são revisadas primeiro e o usuário precisa confirmar novamente. A edição exige a mesma permissão de criar peças, o mesmo proprietário da prévia e CSRF quando habilitado.

A análise do arquivo recebido em 26/11/2026 identificou 313 linhas de peças, 50 códigos repetidos em 108 linhas, 15 quantidades vazias, 13 quantidades escritas como expressões e 204 localizações não preenchidas. A análise não consultou nem modificou o banco atual. Localização continua opcional; as quantidades pendentes bloqueiam a confirmação do lote. Os códigos repetidos são permitidos nesse formato de inventário.
