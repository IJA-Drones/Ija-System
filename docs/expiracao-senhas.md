# Validade de senhas administrada pelo DEV

O DEV configura a validade em **Painel Dev → Proteção de login → Validade das senhas**. O prazo inicial é de 90 dias e pode ser alterado para um inteiro de 1 a 365 dias. A configuração é compartilhada entre os acessos principal, UVIS operacional e piloto Agro, independentemente das flags de timeout de sessão e bloqueio de tentativas.

## Entrada gradual na política

A migração adiciona `usuarios.senha_alterada_em` como campo opcional, sem valor padrão e sem preencher registros existentes. Senhas antigas continuam isentas até a próxima troca ou redefinição. `Usuario.set_senha` registra o instante UTC a cada criação ou alteração válida de senha; todos os fluxos de cadastro e redefinição da aplicação usam esse método. Inserções administrativas por SQL devem respeitar o mesmo contrato.

A validade é calculada a partir dessa data usando o prazo atual de `politica_senha`. Salvar uma configuração não altera senhas nem suas datas. Reduzir o prazo pode vencer imediatamente credenciais já acompanhadas; aumentá-lo pode tornar uma credencial novamente válida. A tela informa esse efeito antes de salvar. Contas antigas sem data permanecem isentas nos dois casos.

Essa implantação gradual foi escolhida pelo responsável pelo sistema. Contas que nunca trocarem a senha permanecem fora da expiração; portanto, esta etapa não representa aplicação universal da política nem, isoladamente, aceite integral do item 4.5.8 da auditoria.

## Senha vencida

A pessoa informa as credenciais no portal apropriado. Limites de tentativa e bloqueios continuam sendo verificados. Se a senha estiver correta, mas vencida, o sistema encaminha para `/renovar-senha` sem iniciar uma sessão autenticada de acesso às funcionalidades.

A autorização para renovar dura 10 minutos e fica vinculada ao usuário, ao portal e à credencial que foi verificada. O cookie assinado contém uma prova HMAC, nunca a senha ou seu hash de autenticação. Uma redefinição administrativa, mudança de perfil, expiração da prova ou renovação anterior invalida a prova. Piloto Agro inativo não pode concluir a troca.

A nova senha deve ser confirmada, respeitar as regras de composição configuradas e diferir da atual. A renovação valida a composição mesmo quando o pacote geral de segurança estiver desativado. A gravação da senha, sua data e o evento de renovação é transacional. O formulário exige CSRF mesmo se o controle global estiver desligado. Após a troca, é necessário entrar novamente com a nova senha no mesmo portal.

Sessões autenticadas também são verificadas antes de executar as rotas: senha vencida ou alterada encerra o acesso e exige novo login. Requisições de API recebem 401, sem executar a operação solicitada. As sessões registram a versão da senha na entrada; sessões antigas de credenciais isentas continuam funcionando até uma troca. O prazo de validade não equivale à expiração por inatividade da sessão.

## Configuração e histórico

Somente o perfil DEV altera o prazo. Quando a Central de TI estiver aplicada ao perfil, a consulta também exige `sistema.tecnico.consultar`, e salvar exige `sistema.tecnico.operar`. COVISA, administrador e gestor de TI não ganham autorização para configurar apenas por terem outras permissões.

O histórico de proteção registra senha vencida, senha renovada e alteração da política. A alteração da política inclui responsável, data, IP e prazo anterior/novo. Senhas e tokens não são armazenados nos eventos. A configuração de duração não altera os limites de tentativas de login já existentes.

## Migração e validação

A revisão `d94f2a7610be` sucede `b82e0d5f314c`: adiciona somente a data opcional e a tabela da política, inicializada com 90 dias. A atualização precisa preceder a execução do código novo. Reinicie a aplicação após a implantação. O downgrade remove os dados de validade, mas não desfaz senhas já renovadas.

`tests/test_password_expiration.py` usa banco SQLite isolado e verifica os três portais, contas antigas, datas e limites, renovação, repetição de senha, CSRF, prova expirada/reutilizada, redefinição concorrente, piloto inativo, sessão em andamento, falhas transacionais, configuração DEV, Central de TI e migração reversível. Use uma conta fictícia com data envelhecida apenas em ambiente de testes para o aceite manual; não altere datas das contas reais para demonstrar o recurso.
