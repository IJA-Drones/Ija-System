# Auditoria remota por syslog - 4.5.4

## Situação

Em 17/10/2026, o responsável decidiu classificar o item 4.5.4 como **atende por aceite interno**, considerando a trilha e o arquivamento no Skybox. Essa decisão está registrada no [acompanhamento CONDOMAR](acompanhamento-condomar.md). A classificação não comprova o transporte syslog exigido no edital: a integração atual do Skybox usa WebDAV, e a situação técnica abaixo permanece inalterada.

O envio está implementado, mas desativado por padrão. O responsável informou que ainda não existe um coletor. Para concluir a implantação, é necessário disponibilizar esse destino, configurar o servidor e conferir eventos recebidos nele. O arquivamento no Skybox permanece independente.

## Formato e transporte

São enviadas mensagens [RFC 5424](https://www.rfc-editor.org/rfc/rfc5424), com dados JSON no corpo, identificação da instalação e `evento_id`. O remetente usa enquadramento por contagem de bytes (octet counting), sem depender de quebra de linha. O coletor deve aceitar esse enquadramento.

O transporte padrão é [TLS, RFC 5425](https://www.rfc-editor.org/rfc/rfc5425), com verificação obrigatória da cadeia de confiança e do nome do servidor. CA privada e certificado de cliente são opcionais. TCP sem TLS, descrito na [RFC 6587](https://www.rfc-editor.org/rfc/rfc6587), exige configuração explícita; não há UDP nem fallback automático para conexão sem TLS.

São reaproveitados os campos permitidos pelo arquivador: ator, município, evento, resultado, data, objeto, diferenças autorizadas, rota lógica, método e IP. Não são enviados corpo da requisição, cookies, senha, query string, referrer ou URL de arquivo. Mensagens de falha guardadas na fila são genéricas para não copiar segredos do provedor.

## Fila e retenção

Os eventos confirmados no banco formam a fila. A tabela `auditoria_syslog_entregas` guarda tentativas, próxima tentativa, reserva do trabalhador e data de transmissão. Não há uma gravação separada de fila que possa perder o evento após o commit de negócio. Uma transação revertida não produz envio das alterações revertidas.

Cada evento é reservado antes do acesso à rede. A rede é acessada fora da transação de banco, com timeout de conexão/I/O de cinco segundos. Falhas provocam espera progressiva, até uma hora. Reservas de trabalhadores interrompidos expiram em dois minutos. A tentativa seguinte usa os mesmos identificadores de evento/instalação. A resolução DNS depende também do sistema operacional.

Com o syslog habilitado, a limpeza só remove eventos que já tenham cópia verificada no Skybox **e** transmissão syslog registrada. Falha de configuração ou indisponibilidade do coletor mantém o acúmulo pendente. Monitorar seu volume e a capacidade do banco.

Com o syslog desabilitado, a política anterior de retenção/Skybox continua valendo. Ao ativar, são enviados todos os eventos ainda presentes no banco; arquivos históricos que já foram removidos do banco não são reimportados do Skybox automaticamente.

TCP/TLS não fornecem confirmação de armazenamento pela aplicação receptora. `enviado_em` registra a conclusão de `sendall`, não um aceite do coletor. Uma interrupção ambígua pode causar perda no destino ou repetição após tentativa; o coletor deve deduplicar por `(instalacao_id, evento_id)` e seu recebimento deve ser monitorado. Não há promessa de entrega exatamente uma vez. O arquivo verificado no Skybox permanece como cópia independente.

## Migração e configuração

A revisão `e4b8c0d129fa`, após `d9e4f81b203a`, cria somente a tabela de controle syslog, com exclusão em cascata quando o evento for removido. Não altera eventos anteriores nem credenciais. Foi ensaiada em SQLite descartável; não foi aplicada ao banco configurado de produção nesta etapa.

1. Manter `AUDIT_SYSLOG_ENABLED=0` enquanto não houver coletor.
2. Aplicar a migração pelo procedimento normal de publicação, antes de ativar o envio. O projeto executa migrações na inicialização de produção pelo Procfile; controlar uma única execução e conferir o destino.
3. Provisionar o coletor e configurar os valores abaixo no ambiente do servidor. Não colocar chaves privadas no repositório.
4. Reiniciar todos os processos com configuração consistente. Um processo antigo/desabilitado conserva a política de retenção anterior.
5. Confirmar a recepção no coletor e manter o acompanhamento do status.

```dotenv
AUDIT_SYSLOG_ENABLED=0
AUDIT_SYSLOG_HOST=
AUDIT_SYSLOG_PORT=6514
AUDIT_SYSLOG_TRANSPORT=tls
AUDIT_SYSLOG_INTERVAL_SECONDS=5
AUDIT_SYSLOG_CA_FILE=
AUDIT_SYSLOG_CERT_FILE=
AUDIT_SYSLOG_KEY_FILE=
```

Quando o destino estiver pronto, preencher o host e mudar `AUDIT_SYSLOG_ENABLED` para `1`. Para TCP, selecionar `tcp` e a porta real do coletor. O emissor não configura nem abre portas do receptor.

O trabalhador inicia na primeira requisição de cada processo, verifica pendências a cada cinco segundos por padrão e processa até 100 eventos por rodada. O intervalo é a frequência de busca, não uma garantia de latência em caso de fila/rede lenta. Para processos sem tráfego ou grande volume, executar o comando em um trabalhador/agendador externo:

```bash
flask --app app:create_app auditoria-syslog-status
flask --app app:create_app auditoria-syslog-enviar --max-eventos 100
```

O comando de envio respeita a ativação; não habilita o serviço automaticamente. O painel Logs de Usuários, reservado ao DEV, exibe estado, pendências, falhas e última transmissão, separado do Skybox.

## Aceite

Demonstrar login bem-sucedido e falho, logout, consulta, exportação, acesso negado e alteração de negócio. Conferir ator, município, resultado, objeto e identificadores no destino. Interromper o coletor, confirmar retenção e tentativas, restaurar e conferir recepção. Os testes usam coletores TCP/TLS locais, certificados temporários, rollback, concorrência, expiração de reserva, retenção, sanitização e migração reversível.

O downgrade apaga o controle de entrega e pode provocar retransmissão se o serviço for reativado após recriar a tabela. Não usar downgrade como procedimento de pausa. Para pausar preservando a fila, manter o serviço habilitado e parar o trabalhador em uma implantação coordenada; desabilitar a flag restaura a política de retenção anterior.
