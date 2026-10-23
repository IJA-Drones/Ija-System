# Complementos do módulo de vigilância — 22/10/2026

Itens da ficha de verificação marcados como **N** ou **P** na sessão de 22/10 e o que foi
feito no código para cada um. Tudo abaixo roda com o mesmo deploy (Render, `Procfile`
aplica as migrações automaticamente); o que depende de configuração está marcado.

| Ficha | Exigência | O que existe agora | Depende de |
|---|---|---|---|
| 1.2 / 1.3 | Denúncia e caso suspeito no celular, carga offline | App Android/iOS (`~/projetos/ija-app`, Capacitor) sobre o site; fila offline de relatos em IndexedDB (`portal-offline.js`) que reenvia sozinha ao voltar a conexão | APK instalado no celular |
| 1.5 | Alerta parametrizado disparando | Menu **Alertas** (`/alertas`): regras por fonte, bairro, janela, limite e raio; disparo automático ao registrar denúncia/relato; avisa gestores no sistema, e-mail e push; botão **Testar** | SMTP para e-mail; VAPID/FCM para push |
| 1.7 | Chatbot IA em rede social | Azul no WhatsApp via Kapso (`POST /webhooks/whatsapp/kapso`) | `KAPSO_*` no Render + webhook cadastrado na Kapso |
| 2.1 / 2.3 | Importação ao vivo do SINAN | Nova origem **DATASUS — arquivo oficial (DBC)** em Vigilância > SINAN; a API do MS ganhou 3 tentativas com espera | Internet de saída (FTP) no servidor |
| 2.2 / 4.1–4.3 / 7.1 | LIRAa/focal, IIP, depósitos, pendentes, migração | Já existia e funciona com a carga inicial. Roteiro abaixo | Carregar o CSV antes |
| 5.5 | Exportação e envio por e-mail | SMTP já existia; faltavam as variáveis. Helper único em `app/shared/mail.py` (587 STARTTLS ou 465 SSL) | `REPORT_SMTP_*` no Render |
| Pedido do TI (Diego) | Notificação a cidadãos em zona de risco | Botão **Receber alertas no celular** no Portal do Cidadão guarda a localização; o disparo de alerta só avisa aparelhos dentro do raio da regra | VAPID (web) / Firebase (app) |
| Pedido do TI (Diego) | Monitorar o agente de endemias | Rastro GPS do agente enquanto o app está aberto; menu **Agentes em campo** com percurso, horários e km por agente/dia | Agente logado no app |

## Variáveis novas no Render

```
VAPID_PUBLIC_KEY=BFmMevShNnRQK3dTaPV1Bb79Ghk3NpWFPwAxvptiHjy4JxIwh4lVHafB8piPFSaV5RfrWGwCRRMBKluiZp6vroM
VAPID_PRIVATE_KEY=<chave privada — entregue separadamente, nunca no repositório>
VAPID_CLAIMS_EMAIL=mailto:ti@grupoagroazul.com.br
REPORT_SMTP_HOST=...            REPORT_SMTP_PORT=587 (ou 465)
REPORT_SMTP_FROM=...            REPORT_SMTP_USERNAME=...   REPORT_SMTP_PASSWORD=...
KAPSO_API_KEY=...               KAPSO_PHONE_NUMBER_ID=...  KAPSO_WEBHOOK_SECRET=...
FCM_SERVICE_ACCOUNT_JSON={"type":"service_account",...}   (só para push dentro do app)
```

A chave pública acima foi gerada em 22/10/2026 para esta POC (a privada fica fora do git); o par pode ser trocado por outro
(`python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); v.save_key('vapid.pem')"`).

## API do aplicativo nativo

`GET /api/mobile/config`, `POST /api/mobile/login` (token Bearer, 30 dias), `GET /api/mobile/me`,
`POST /api/mobile/relato-saude`, `GET /api/mobile/alertas?prefeitura_id=`, `POST /api/mobile/chat`,
`POST /api/push/inscrever` e `POST /api/agente/posicao` (aceita Bearer). A denúncia de foco usa o
`POST /portal-cidadao/denuncias` existente (multipart). Tudo sem sessão/cookie.

## Aplicativo: download e PWA

- Página pública `/app`: APK Android (servido em `/app/ija-vigilancia.apk`, arquivo em `app/static/downloads/`) com QR
  code, e passo a passo do iPhone (PWA pelo Safari → Adicionar à Tela de Início). Link no login e no portal.
- O Portal do Cidadão tem manifesto próprio (`manifest-portal.json`, nome "IJA Vigilância"), botão "Instalar
  aplicativo" (Android/Chrome), dica para iPhone, estado da inscrição push e opção de desativar; o service worker
  reinscreve sozinho quando o navegador troca a inscrição.
- Base de demonstração: `python scripts/poc_seed.py --prefeitura-id 14 --usuario-demo <login> --agente-login agente.pesqueira --agente-senha '<senha>' --email-alertas <email>`
  (Shell do Render). Cria plano LIRAa com quarteirões do agente, carga de campo, regras de alerta, relatos, rastro e SINAN DATASUS.

## Telegram (Azul 24/7 em rede social, sem aprovação)

1. No Telegram, @BotFather → `/newbot` → nome "IJA Vigilância" → usuário `ija_vigilancia_bot` → copiar o token.
2. No Render: `TELEGRAM_BOT_TOKEN=<token>` e `TELEGRAM_WEBHOOK_SECRET=<texto longo aleatório>`.
3. Registrar o webhook (uma vez): `curl "https://api.telegram.org/bot<token>/setWebhook?url=https://www.system.oceanoazuldrones.com.br/webhooks/telegram/<segredo>&secret_token=<segredo>"`.
O bot responde com a mesma Azul do portal (histórico curto por chat, 40 mensagens/hora por chat).

## Kapso (WhatsApp)

1. No painel da Kapso, número conectado → Webhooks → novo webhook:
   URL `https://www.system.oceanoazuldrones.com.br/webhooks/whatsapp/kapso`, evento
   `whatsapp.message.received`, defina um segredo e copie para `KAPSO_WEBHOOK_SECRET`.
2. `KAPSO_API_KEY` = chave do projeto; `KAPSO_PHONE_NUMBER_ID` = id do número.
3. A resposta usa a mesma Azul do portal (OpenAI) com histórico curto por telefone
   (memória do processo; some em reinício) e limite de 40 mensagens/hora por número.

## Firebase (push dentro do app Android/iOS)

1. Console Firebase → projeto → Adicionar app Android, pacote `br.com.oceanoazuldrones.ija`
   → baixar `google-services.json` para `~/projetos/ija-app/android/app/` → `npx cap sync android`
   → `cd android && ./gradlew assembleRelease` (README do app).
2. Configurações do projeto → Contas de serviço → Gerar chave → colar o JSON numa linha em
   `FCM_SERVICE_ACCOUNT_JSON`.
3. iOS: habilitar Push Notifications no Xcode e subir a chave APNs no Firebase.
Sem isso, o botão do portal funciona no navegador (Chrome Android; iPhone via "Adicionar à
Tela de Início"), e dentro do app mostra a mensagem de que o Firebase não está configurado.

## Roteiro de demonstração (ordem sugerida)

1. **Carga inicial:** Vigilância > Importação e validação > prefeitura
   Pesqueira > baixar a amostra geolocalizada > preparar > confirmar. Isso preenche
   resultados (IIP, IB, depósitos, pendentes com fotos) e o mapa de risco.
2. **SINAN:** Vigilância > SINAN > Pesqueira / dengue / 2026 > aba Importações >
   origem DATASUS > Importar. Leva 1–3 min; mostra 31 notificações (dado real de 22/10).
   Se a API do MS estiver no ar, a origem API também funciona.
3. **Alertas:** menu Alertas > criar regra "Focos no Centro", fonte relatos de foco, bairro
   Centro, limite 2, janela 7 d. No celular: Portal do Cidadão > Receber alertas no celular.
   Registrar 2 relatos no bairro Centro pelo app → notificação chega ao celular e ao sino
   dos gestores; o disparo aparece na tela de Alertas. Botão **Testar** repete sem novos relatos.
4. **E-mail:** Relatórios > Consultas personalizadas > enviar por e-mail (com SMTP configurado).
5. **WhatsApp:** mandar "quais os sintomas de dengue?" para o número Kapso.
6. **Offline:** no app, modo avião → enviar relato → mensagem "salvo neste aparelho" →
   desligar modo avião → protocolo aparece sozinho.
7. **Agente em campo:** logar como agente de endemias no app, andar alguns metros, e abrir
   Agentes em campo no computador com a data de hoje.
