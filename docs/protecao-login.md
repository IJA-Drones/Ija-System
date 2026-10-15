# Proteção dos três acessos

Implementação do item 4.5.7 da auditoria CONDOMAR, iniciada em 15/10/2026. Cobre login principal (`/login`), UVIS operacional (`/uvis-operacional/login`) e piloto Agro (`/agro/login`). A expiração de senha do item 4.5.8 e a trilha geral/syslog do item 4.5.4 continuam sendo etapas separadas.

## Comportamento

O sistema conta falhas por login informado e por endereço IP. Os contadores são compartilhados entre os três acessos, sessões, navegadores e processos do servidor. Nomes desconhecidos recebem a mesma proteção; variações de caixa/espaços compartilham o contador, sem alterar a comparação das credenciais existentes. Senha correta em um portal incompatível não autentica nem limpa as falhas.

Ao atingir o limite, a tentativa recebe HTTP 429 e mostra um aviso permanente junto ao formulário, com motivo, orientação de suporte e contagem regressiva para tentar novamente nos três portais. Sem JavaScript, o aviso continua visível com o tempo aproximado. O contador é informativo; a liberação é sempre validada pelo servidor e não há envio automático do formulário. Tentativas durante o bloqueio não verificam a senha, não prolongam o prazo e ficam registradas. O prazo vencido libera automaticamente uma nova janela. Login válido limpa as falhas da conta, mas não as de outros usuários da mesma origem. Bloqueios de conta e origem são independentes.

As tabelas `login_bloqueios` e `login_eventos` persistem os contadores e os resultados. A transação de autenticação grava contador e evento antes de iniciar a sessão de acesso; falha de armazenamento impede o login com HTTP 503. PostgreSQL usa inserção com conflito e bloqueio de linha; a ordem é sempre origem e depois conta. A atualização não depende de memória local do worker. Nenhuma senha, hash de senha, cookie ou token é gravado nesses eventos.

## Configuração

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `LOGIN_PROTECTION_ENABLED` | `1` | Ativa a proteção, independentemente do pacote de sessão/senha. |
| `LOGIN_MAX_FAILURES` | `5` | Máximo de falhas da mesma conta por janela. |
| `LOGIN_IP_MAX_FAILURES` | `50` | Máximo de falhas da mesma origem, somando contas. |
| `LOGIN_FAILURE_WINDOW_MINUTES` | `15` | Janela de contagem de falhas. |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Duração do bloqueio após atingir um limite. |
| `LOGIN_TRUSTED_PROXY_CIDRS` | vazio | Redes dos proxies autorizados a informar `X-Forwarded-For`, separadas por vírgulas. |

Limites e prazos devem ser inteiros positivos. Por padrão, o IP é `REMOTE_ADDR`; cabeçalhos enviados por clientes não são confiáveis. Com proxies configurados, a cadeia é examinada da direita para a esquerda até encontrar o primeiro endereço não confiável. Cadastre somente as redes efetivas da infraestrutura, sem aceitar indiscriminadamente a internet. Sem essa configuração, vários usuários atrás do mesmo proxy compartilham o limite de origem. Dimensione esse limite também para redes municipais compartilhadas.

## Consulta e desbloqueio

No painel DEV, o botão **Proteção de login** abre `/dev/seguranca-login`. A tela mostra até 100 bloqueios ativos e os últimos 100 eventos, com horários de Brasília. A consulta exige identidade `dev`; quando a Central de TI possui configuração ativa para o perfil, também exige `sistema.tecnico.consultar`. A liberação exige `sistema.tecnico.operar`, token CSRF válido e justificativa entre 5 e 300 caracteres. O perfil gestor de TI continua sujeito às restrições introduzidas pela Central de TI.

A liberação zera somente o contador selecionado e registra responsável, horário, origem e motivo. Não remove os eventos anteriores. Se conta e origem estiverem bloqueadas, avalie ambos os registros. A tela limita a apresentação, mas não apaga os demais eventos. Esta entrega não implementa expurgo automático nem transmissão syslog; retenção e arquivamento devem ser definidos na etapa de auditoria geral.

## Implantação e aceite

Aplicar `flask --app app:create_app db upgrade` antes de disponibilizar a versão. A migração `b82e0d5f314c` sucede a Central de TI (`c1a0f8b6d2e4`) e apenas cria duas tabelas e seus índices. Não altera usuários, senhas ou permissões existentes. O `Procfile` já prevê upgrade antes do servidor. Reinicie o processo após atualizar código/configuração. Nenhum banco real é utilizado nos testes unitários ou atualizado automaticamente por esta implementação.

Em homologação, usar contas fictícias nos três portais: provocar falhas até o limite, repetir com senha correta durante o bloqueio, alternar portal/IP, aguardar o prazo e conferir o acesso. Verificar sucesso, recusa, limite, tentativa bloqueada e liberação manual no histórico. Exercitar permissão negada para COVISA, administrador e gestor de TI, além de CSRF ausente/inválido. Validar o IP real na infraestrutura e concorrência com PostgreSQL antes de concluir o aceite da implantação.

`tests/test_login_protection.py` cobre as rotas com banco SQLite isolado, concorrência com conexões distintas, janelas/prazos, IP/proxy, transação, autorização, CSRF, histórico e upgrade/downgrade. A existência desses testes não comprova a ativação no servidor de produção nem substitui o aceite do edital.
