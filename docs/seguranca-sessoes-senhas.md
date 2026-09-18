# Inatividade, senhas e CSRF

Implementação dos itens 4.5.5 e 4.5.9 e de uma proteção CSRF opcional, sem novas tabelas, colunas ou migrações.
Os parâmetros ficam na configuração da aplicação. Esta etapa não inclui uma
tela para gravar configurações no banco.

## Ativação controlada

O recurso fica **desativado por padrão**. A instalação do código não altera a
política em uso. Nenhum valor do `.env` é modificado pelo código.
O `Procfile` deixa de executar `flask db upgrade` automaticamente: por padrão,
`IJA_AUTO_DB_MIGRATE=0`. Quando você decidir executar migrações futuras, faça
isso manualmente ou defina `IJA_AUTO_DB_MIGRATE=1` de forma explícita no ambiente
de implantação. Esta alteração não exige migração no Neon nem em produção.

Para ativar primeiro em homologação, definir no ambiente e reiniciar todos os
processos da aplicação:

```dotenv
SECURITY_CONTROLS_ENABLED=1
SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_MAX_LIFETIME_HOURS=8
PASSWORD_MIN_LENGTH=15
PASSWORD_REQUIRE_UPPERCASE=1
PASSWORD_REQUIRE_LOWERCASE=1
PASSWORD_REQUIRE_DIGIT=1
PASSWORD_REQUIRE_SYMBOL=1
```

O CSRF tem ativação independente. Depois de conferir os fluxos em homologação,
defina `CSRF_PROTECTION_ENABLED=1` e reinicie todos os processos. Tanto essa
opção quanto `SECURITY_CONTROLS_ENABLED` ficam em `0` por padrão. Não é preciso
ativar as duas juntas. Uma `SECRET_KEY` fixa de pelo menos 32 caracteres é
obrigatória quando qualquer uma delas estiver ativa.

- Timeout: inteiro entre 1 e 1440 minutos. Mínimo da senha: entre 8 e 128 caracteres.
- Duração máxima: inteiro entre 1 e 168 horas, mesmo que haja atividade.
- As quatro regras de composição são independentes; `0` desativa cada exigência.
- Máximo da senha: 128 caracteres. Espaços são preservados quando a política está ativa.
- Configurações inválidas impedem a inicialização com o recurso ativo, com uma
  mensagem que identifica o parâmetro. Validar em homologação antes de publicar.
- Usar a mesma `SECRET_KEY` estável e os mesmos parâmetros em todos os processos,
  como já é necessário para as sessões Flask existentes. A ativação recusa a
  chave aleatória de desenvolvimento gerada como substituta pelo projeto e
  chaves com menos de 32 caracteres.
- Na ativação, sessões antigas precisam entrar novamente, pois ainda não possuem
  o registro de atividade assinado. Não há troca obrigatória das senhas antigas.
- Reversão: definir `SECURITY_CONTROLS_ENABLED=0` e reiniciar todos os processos.
  As senhas já cadastradas continuam válidas; nenhuma reversão de banco é necessária.

## Funcionamento

O servidor verifica a última atividade e a duração total antes de permitir a execução das rotas.
A sessão expira ao alcançar o prazo, inclusive se o JavaScript estiver desativado.
Operações expiradas não são executadas. Páginas retornam ao login; chamadas de API
recebem HTTP 401 com `code=session_expired`.

Navegação HTML e interação com a página renovam o prazo. O navegador envia eventos
de atividade limitados em frequência e protegidos por um token da sessão. Consultas
de status, atualizações automáticas, uploads em segundo plano e arquivos estáticos
não renovam a sessão. O aviso aparece no último minuto. A opção “Continuar conectado”
só funciona enquanto a sessão ainda está válida. Ao voltar de uma aba suspensa, o
navegador verifica a validade no servidor.

As abas compartilham a sessão do navegador; dispositivos diferentes têm sessões
independentes. Antes de sair por um prazo calculado localmente, a página consulta o
servidor para reconhecer atividade de outra aba. Uma falha de conexão não estende
o prazo. Formulários longos continuam ativos enquanto houver interação, mas dados
não enviados não são salvos automaticamente após expiração.

A implementação usa o cookie assinado que o Flask já fornece. A assinatura impede
alterar a data de atividade sem a chave do servidor. O logoff remove o cookie do
navegador, mas não há um cadastro central para revogar cópias de cookies ainda
válidos: uma cópia anterior ao logoff permanece verificável até seu próprio prazo
de inatividade. Escritas concorrentes em cookies também podem fazer prevalecer
um horário de atividade anterior. Revogação central e sincronização transacional
exigem armazenamento de sessões no servidor e ficam fora desta etapa sem banco.

Este mecanismo reduz risco, mas não torna o site imune a ataques. O projeto ainda
precisa de limitação de tentativas de login compartilhada entre processos, MFA para contas
privilegiadas, revisão de XSS/CSP e consulta a senhas comprometidas. Essas medidas
abrangem rotas existentes fora dos dois requisitos desta entrega e exigem testes
de regressão específicos. `SameSite=Lax` ajuda contra CSRF, mas não o substitui.

## Proteção CSRF opcional

Quando `CSRF_PROTECTION_ENABLED=1`, o servidor exige um token da sessão Flask
assinada em requisições `POST`, `PUT`, `PATCH` e `DELETE` autenticadas, além
dos três formulários de login. Requisições sem token ou com token incorreto
recebem HTTP 403 antes de executar a rota. O token muda após login bem-sucedido.
O JavaScript central envia o token em formulários da mesma origem e no cabeçalho
de chamadas `fetch`/`XMLHttpRequest` da mesma origem. Os três formulários de
login também contêm o token no HTML e funcionam sem JavaScript. O token não é
colocado na URL nem enviado a domínios externos pelo código central. Páginas HTML
com o recurso ativo recebem `Cache-Control: private, no-store`.

Esta proteção ainda exige validação funcional em homologação antes de ligar em
produção: os demais formulários autenticados dependem de JavaScript para
adicionar o token. Navegação ou formulário já aberto antes da ativação precisa
ser recarregado. Requisições públicas sem autenticação, como o portal cidadão,
ficam fora dessa regra; devem ser avaliadas por fluxo. A rota legada de logout
usa GET e não é coberta pela verificação de métodos de escrita. A proteção CSRF
também não substitui correções de XSS, controle de permissões nem limites de
tentativas. A reversão é `CSRF_PROTECTION_ENABLED=0` seguida de reinício, sem
alterações de banco.

Encerramentos automáticos são registrados no log da aplicação com ID do usuário e
motivo, sem senha ou token. Não há novas gravações de auditoria no banco.

A validação de senha é compartilhada por administradores, UVIS, pilotos,
pilotos Agro, equipes UVIS e equipes Oceano, incluindo redefinições. Também há
validação no método `Usuario.set_senha`, evitando que novos fluxos a ignorem.
Campos vazios em edições mantêm a senha atual. O login continua verificando o hash
existente, sem aplicar retroativamente a política. Esta etapa cobre comprimento,
composição e uma lista local pequena de senhas óbvias. Não implementa consulta a
bases de senhas vazadas.
Após erro de cadastro, os campos de senha não são preenchidos novamente na
resposta HTML; o administrador precisa digitá-los de novo.

## Verificação sem dados reais

```sh
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q
node --test tests/session_security_browser.test.cjs
node --test tests/csrf_security_browser.test.cjs
```

Os testes novos de segurança usam usuários em memória e autenticação simulada,
sem consultas ao banco. Os testes existentes que precisam de SQL usam SQLite
temporário em memória. Não executar `flask db upgrade` para este recurso.

Para aceite em homologação: ativar timeout de 1 minuto, deixar uma aba parada e
confirmar o bloqueio; repetir com digitação, duas abas, limite total e os três logins. Conferir
também rejeição de senhas fracas e manutenção das senhas antigas. Com CSRF ligado,
testar login, cadastro, edição, upload, exclusão, ações por botão e chamadas de API:
as operações normais devem funcionar e tentativas sem token devem receber 403.
Restaurar o
timeout operacional antes da publicação.
