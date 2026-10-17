# Consultas personalizadas e e-mail por prefeitura

## Acesso e consulta

Em **Relatórios → Consultas personalizadas**, selecione a base (solicitações ou ordens de serviço), campos, formatos, filtros, condições, exceções e quebra. O catálogo salvo é pessoal. Tabela, gráfico e mapa usam a mesma execução; PDF e Excel consultam os dados novamente com os mesmos critérios.

O filtro Prefeitura somente restringe o alcance do usuário; não concede acesso a outra prefeitura. Os vínculos municipais, regionais e operacionais existentes continuam sendo aplicados. Sem vínculo municipal, um usuário sem acesso global não recebe registros de outras prefeituras.

A Central de TI controla `prefeitura.relatorios.consultar` e `prefeitura.relatorios.exportar`. Perfis sem configuração explícita mantêm as regras existentes de Relatórios, incluindo COVISA. O envio e a leitura do destinatário exigem a permissão de exportação quando o perfil tem configuração explícita.

## Destinatário municipal

Em **Configurações**, escolha a prefeitura (DEV) e abra **Configurar e-mail dos relatórios**. Cadastre um único destinatário, sem senha. O endereço é compartilhado entre as contas da prefeitura. Deixar vazio desabilita o destino.

A COVISA administra somente a prefeitura vinculada ao seu cadastro; o DEV pode administrar todas. O Diretor tem acesso de consulta às configurações de todas as prefeituras, incluindo marca-d’água, destinatário e histórico de envio. No acesso padrão, o Diretor não salva alterações. Perfis explicitamente configurados na Central de TI seguem as permissões concedidas. As permissões `prefeitura.documentos.consultar` e `prefeitura.documentos.configurar` continuam sendo exigidas para perfis configurados. Há proteção CSRF e verificação de versão para evitar sobrescrever uma alteração feita em outra aba.

O formulário de marca-d’água permanece separado. Nenhum upload de imagem ou vídeo foi alterado por esta funcionalidade.

## Modo simples, sem SMTP

Sem serviço de envio direto, a tela apresenta **Preparar e-mail**. O usuário seleciona a prefeitura, confirma o destinatário e baixa o PDF. Em seguida, clica em **Abrir aplicativo de e-mail**, anexa manualmente o arquivo `consulta.pdf` e envia. O atalho `mailto:` preenche destinatário, assunto e mensagem no aplicativo configurado no computador. Não anexa o arquivo automaticamente e não confirma envio nem entrega; esses e-mails manuais não entram no histórico de envios diretos.

## Confirmação e envio direto

1. Selecione uma prefeitura nos filtros da consulta.
2. Clique em **Enviar por e-mail**.
3. Confira o nome da prefeitura e o destinatário cadastrado.
4. Confirme para gerar e enviar o PDF.

O servidor verifica novamente o acesso, o destinatário e sua versão. Não aceita um endereço arbitrário enviado pelo navegador. O PDF deve conter somente registros da prefeitura selecionada. Um identificador único evita repetir o mesmo pedido de envio.

O histórico nas configurações registra usuário, prefeitura, destinatário, data UTC e situação: preparando, enviando, aceito, incerto ou falha. “Aceito” significa aceitação pelo SMTP, não confirmação na caixa de entrada. Não há repetição automática após falha ou resultado incerto; confira o recebimento antes de iniciar outro envio. Uma interrupção do processo pode deixar o estado em preparando ou enviando.

## Serviço SMTP

O remetente é centralizado no ambiente do sistema. As prefeituras cadastram apenas o destino. Configurar no `.env` local e nas variáveis de produção:

```dotenv
REPORT_SMTP_HOST=smtp.exemplo.org
REPORT_SMTP_PORT=587
REPORT_SMTP_FROM=relatorios@exemplo.org
REPORT_SMTP_USERNAME=usuario-do-servico
REPORT_SMTP_PASSWORD=credencial-do-servico
```

O provedor precisa aceitar SMTP com STARTTLS. A conexão usa validação de certificado. Não versionar credenciais. Sem host e remetente configurados, o botão utiliza o modo simples descrito acima; o envio direto pelo servidor fica indisponível. Nenhum envio real foi feito durante a implementação; os testes de entrega usam SMTP simulado.

## Limites e migração

Consulta e Excel: até 10.000 registros. PDF: até 2.000 registros. Anexo de e-mail: até 10 MB. Exceder os limites solicita restringir os filtros; não trunca o relatório silenciosamente.

Migrações: `a12f07c98e43` cria `consultas_salvas`; `b72c931ae804` cria `prefeitura_email_config` e `consulta_email_envios`. São aditivas e não preenchem destinatários automaticamente. Aplicadas no banco de testes em 17/10/2026. Produção ainda precisa do upgrade ao publicar esta versão.
