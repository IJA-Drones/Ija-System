# Recuperação de transações e arquivos — item 4.5.6

Implementação de 17/10/2026. Classificação técnica: **ATENDE no escopo implementado e validado em testes**. O banco de testes foi atualizado para `f2a91d0c6b38` em 17/10/2026; a verificação dos campos usados na recuperação passou. A aplicação em produção depende da publicação deste código e das migrações. A classificação não substitui o aceite do contratante.

## Comportamento

As alterações de negócio continuam usando as transações do PostgreSQL: uma falha antes do commit desfaz as alterações dessa transação. No cadastro de denúncias, a falha em qualquer anexo também provoca rollback explícito do cadastro e dos anexos da tentativa.

Arquivos externos não participam do rollback SQL. Para eles, a aplicação mantém um registro durável de compensação em `arquivo_operacoes`, gravado **antes** do arquivo. Esse registro usa uma transação independente e sobrevive ao rollback ou à interrupção do processo. Ele contém destino, backend, referências possíveis, estado e tentativas; não contém bytes do arquivo nem credenciais.

O trabalhador de recuperação consulta os vínculos efetivamente confirmados no banco:

- Arquivo novo sem vínculo confirmado: remove o arquivo órfão.
- Arquivo com vínculo confirmado: preserva, inclusive quando o cliente perdeu a resposta de um commit que realmente aconteceu.
- Exclusão/substituição: a remoção física é adiada. Se a alteração do banco falhar, o vínculo anterior continua protegendo o arquivo antigo.
- Falha no armazenamento ou na verificação: mantém o trabalho pendente e tenta novamente, com espera progressiva de até uma hora. HTTP 202 não é tratado como remoção confirmada.
- Operação ainda gravando: o trabalhador não remove o arquivo; bloqueios transacionais do PostgreSQL coordenam escritores e recuperadores de diferentes processos.
- Sessão reutilizada depois de uma interrupção: a confirmação é impedida se a recuperação já removeu um arquivo dessa tentativa; o usuário precisa reenviá-lo.

Há uma espera inicial de cinco minutos e verificação automática a cada minuto, em lotes de até dez operações. Esses tempos não são garantia de prazo: uploads em andamento, indisponibilidade de armazenamento e fila acumulada podem prolongar a recuperação. Para uploads remotos abandonados, os destinos removidos são reconciliados novamente de hora em hora por sete dias, cobrindo uma conclusão tardia do PUT no servidor remoto.

## Cobertura

| Fluxo | Armazenamento e proteção |
| --- | --- |
| Denúncias | Anexos locais/Skybox; rollback do cadastro e recuperação de todos os anexos da tentativa |
| Imagens e vídeos de OS | Arquivo local, Skybox e WebDAV legado; escrita direta e gravação final do vídeo em segundo plano; substituição e exclusão |
| Cópia da imagem principal de OS | Preserva também a cópia Skybox quando o banco aponta para o arquivo local |
| Configurações de prefeitura e logos financeiras | Novos arquivos e limpeza de imagens substituídas |
| Ortomosaicos e DEM | Originais e produtos enviados pelo armazenamento compartilhado: COG, curvas e JPEG |
| Comentários/feedback e anexos de solicitações | Gravação persistente e remoções instrumentadas |
| Veículos | Fotos persistidas de painel, abastecimento e comprovantes |
| Agro | Anexos, mapas, comprovantes, importações de voo e rotas |
| DJI | Arquivos importados de voo/rotas e exclusão de KML |
| Banco de Talentos | PDFs enviados ao Dropbox e exclusão após confirmação no banco |

O transporte existente foi preservado: partes dos vídeos, retomada, montagem, conversão, progresso e contratos HTTP continuam iguais. Os pontos de persistência final receberam o registro de recuperação. Temporários de vídeo e arquivos de exportação em memória continuam sob seus mecanismos existentes.

O arquivamento da auditoria já tem sua própria fila durável, checksum, reserva e reenvio. Ele fica fora desta fila para evitar que registros de auditoria sejam confundidos com anexos órfãos.

## Operação e implantação

1. Aplicar `flask --app app:create_app db upgrade` no ambiente escolhido, antes de usar o novo código. A revisão desta funcionalidade é `f2a91d0c6b38`, posterior a `e4b8c0d129fa` (fila syslog). O `Procfile` atual também executa as migrações antes de iniciar o servidor.
2. Reiniciar o servidor. A primeira requisição inicia o trabalhador; os registros pendentes continuam no PostgreSQL durante reinícios.
3. Consultar `flask --app app:create_app arquivos-recuperacao-status` para os estados e a quantidade de pendências com falha.
4. Para execução por agendador ou recuperação manual, usar `flask --app app:create_app arquivos-recuperar --limite 10`.
5. Em falhas persistentes, verificar banco, destino e credenciais. A fila guarda a classe do erro, sem URL autenticada ou resposta sensível. Não apagar a fila para silenciar pendências.

A recuperação exige PostgreSQL e ao menos duas conexões disponíveis durante o registro da intenção. O banco local SQLite das suítes antigas não simula essa garantia; os testes específicos usam PostgreSQL real e descartável.

Arquivos locais só são removidos no nó de armazenamento correspondente, dentro das pastas permitidas, sem seguir links simbólicos. `FILE_RECOVERY_LOCAL_NODE_ID` pode identificar um volume persistente compartilhado, **somente se os processos realmente acessarem o mesmo volume e caminhos**. Mudanças de nó, credenciais/conta do Dropbox ou endereço/conta do WebDAV podem exigir revisão das pendências. Não se tenta apagar um arquivo em um destino diferente daquele registrado.

O downgrade bloqueia a remoção da tabela enquanto existem operações pendentes. Antes de reverter a implantação, interromper escritores/trabalhadores e preservar o histórico de recuperação. Não usar downgrade como limpeza da fila.

## Evidências e limites

`tests/test_file_recovery_postgres.py` valida PostgreSQL real, usando schemas e arquivos descartáveis. Cobre rollback SQL, falha no segundo anexo, falha de constraint no commit, operação longa, abandono de sessão, recuperação concorrente, reenvio após falha, destino alterado, rejeição de caminhos inseguros, escrita WebDAV preservada, cópia local/Skybox, Dropbox, PUT tardio, HTTP 202, migração e bloqueio de downgrade. Serviços de armazenamento são simulados para não excluir mídias reais.

Validação executada: 30 testes específicos em PostgreSQL, 248 testes dos fluxos existentes (mais 147 subtestes) e 10 testes JavaScript, todos aprovados. As suítes existentes verificam vídeos, recuperação de sessões de upload no navegador, imagens, ortomosaicos, DEM, edição, auditoria, veículos, DJI e Banco de Talentos. A validação não é uma certificação de disponibilidade dos provedores externos.

A compensação é eventual; não constitui uma transação distribuída instantânea entre PostgreSQL e armazenamento. Não há varredura destrutiva de arquivos históricos sem registro de intenção. Etapas deliberadamente confirmadas antes de trabalhos assíncronos, como reservas de processamento e criação de rascunho da OS, continuam sendo etapas persistentes; não se desfaz automaticamente uma etapa já confirmada. Novos destinos ou campos de arquivo devem passar pelas mesmas funções de registro e pela verificação de referências antes de serem considerados cobertos.
