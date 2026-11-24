# Administração da AZUL

Na página **AZUL**, o perfil **dev** encontra o botão **Configurações**, que abre `/azul/configuracoes`. Os endpoints de configuração e consumo exigem login e o perfil dev no servidor; permissões da Central TI não delegam esse controle a outros perfis.

## Controles disponíveis

- **Comportamento:** som global, ditado, conversa por voz, pausa da geração paga e pesquisa nas fontes oficiais existentes.
- **Contexto:** informações complementares internas e públicas, em campos separados, com até 6.000 caracteres cada. O contexto interno não é enviado ao atendimento público de saúde. Nome AZUL, escopo, fontes e autorização continuam obrigatórios no código.
- **Modelos:** modelos de resposta interna e pública, narração, transcrição e voz. O catálogo limita as escolhas às integrações compatíveis. A chave permanece no ambiente do servidor.
- **Limites:** tokens máximos de saída, tamanho da pergunta, operações diárias por canal, operações de áudio por usuário/sessão, tempo e número de falas por ligação e duração máxima de cada fala.
- **Gastos:** teto diário e mensal estimado em reais. Zero significa ausência de um teto monetário adicional. Para quotas de operações, zero bloqueia novas gerações daquele tipo.
- **Tarifas e câmbio:** valores editáveis por modelo e data de referência. Os valores iniciais foram consultados na [tabela oficial da OpenAI](https://developers.openai.com/api/docs/pricing), nos modelos de [transcrição](https://developers.openai.com/api/docs/models/gpt-transcribe) e [transcrição mini](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe), e na [PTAX do Banco Central](https://ptax.bcb.gov.br/ptax_internet/consultarUltimaCotacaoDolar.do). A referência inicial é 11/11/2026 para tarifas e R$ 5,5840 por dólar, PTAX de venda de 10/11/2026.

As alterações são versionadas. Salvar uma tela desatualizada retorna conflito, preservando o formulário. O histórico registra responsável, data, versão e nomes dos campos alterados, sem duplicar o conteúdo dos contextos.

## Som global

Desativar **Som do chatbot** bloqueia novas ofertas e pedidos de narração e desliga a saída de áudio da interface, incluindo gravações e guias. Chats abertos atualizam a política a cada dez segundos e também antes de iniciar ou reproduzir uma fala. A ligação ativa é interrompida; o ditado pode continuar disponível, conforme sua configuração própria. Áudio já baixado não pode ser removido de um dispositivo, mas a interface atualizada interrompe sua reprodução.

Os limites de tempo/falas chegam ao navegador pela política e também são validados nas etapas aplicáveis do servidor. As chaves `AZUL_VOICE_ENABLED=0` e `AZUL_CONVERSATION_ENABLED=0` do ambiente continuam como desligamentos de emergência, mesmo que o painel esteja habilitado.

Pausar a geração paga mantém os guias, as respostas locais e as gravações disponíveis, conforme os demais controles. Perguntas fora do escopo continuam bloqueadas antes da chamada ao modelo. Nenhuma configuração concede ferramentas, altera vínculos ou amplia o acesso do usuário a registros.

## Consumo e valores

O painel mede novas interações a partir da implantação. Não reconstrói custos antigos. Apresenta filtros por período/canal, totais e conversas recentes, com:

- Tokens informados pelo provedor, incluindo entrada em cache e tokens de saída não visíveis, quando reportados.
- Duração do áudio de transcrição, duração faturável da Bossa e tokens das vozes legadas.
- Chamadas à pesquisa web retornadas na resposta.
- Respostas locais, gravações e reutilizações de cache com custo de geração zero.
- Operações incompletas ou sem dados suficientes separadas das que têm medição.

Cada evento guarda as tarifas e o câmbio usados na operação. Editar preços depois não recalcula o histórico. Os valores em reais são **estimativas de custo da API**, sem impostos, spread do cartão ou reconciliação da fatura. A contagem de tokens pode incluir raciocínio e estrutura além das palavras exibidas; a referência é o consumo do provedor, conforme a [documentação de tokens](https://developers.openai.com/api/docs/guides/token-counting) e de [custos de voz](https://developers.openai.com/api/docs/guides/voice-latency-cost).

Não são armazenados neste registro mensagens, contextos enviados, transcrições, áudios, IPs ou chaves. A conversa é identificada por HMAC vinculado à conta/sessão e ao identificador da aba. **Nova conversa** troca o identificador. O histórico de configurações e os contextos de referência são dados administrativos separados do consumo.

Antes de uma chamada paga, o servidor reserva uma estimativa conservadora do máximo da operação. A verificação de tetos monetários e contagens diárias é serializada no banco compartilhado para evitar que workers gastem o mesmo saldo. A reserva é substituída pelo custo estimado da medição concluída. Se o provedor não informar consumo, ou houver falha sem medição, a reserva continua contabilizada no teto e aparece separadamente no painel. Isso não significa que o provedor faturou todo o valor reservado. Tarifas e câmbio incorretos afetam os limites estimados.

Os tetos consideram o dia/mês em `America/Sao_Paulo`. As proteções anteriores por minuto, usuário, sessão e origem continuam adicionais; suas quotas locais permanecem por host. O controle monetário não altera os limites de faturamento da organização OpenAI.

## Persistência e implantação

Em uma aplicação inicializada com Flask-SQLAlchemy, configurações, auditoria e consumo ficam no banco principal, nas tabelas `azul_configuracao`, `azul_configuracao_historico` e `azul_consumo`. A inicialização é idempotente e cria somente essas três tabelas e seus índices, sem alterar registros operacionais. Elas também estão registradas no metadata da aplicação. O usuário de implantação precisa ter permissão de criação dessas estruturas na primeira execução.

`AZUL_CONTROL_DATABASE_URI`, definido somente no servidor, permite selecionar outro banco SQLAlchemy compartilhado. Sem extensão SQLAlchemy — instalações Flask mínimas e testes isolados — é usado `instance/azul_controle.sqlite`. Em produção com múltiplos hosts, use o mesmo banco compartilhado; não distribua SQLite em discos independentes.

O serviço suporta PostgreSQL e SQLite, com serialização de operações de escrita. Se o controle não puder ser consultado, novas chamadas pagas falham antes de acessar o provedor. O widget opcional não derruba páginas públicas; a política de áudio também falha com som desativado. Uma medição que falhe após a resposta mantém a reserva para não liberar artificialmente o orçamento.

## Voz brasileira Bossa (24/11/2026)

O perfil padrão é **Bossa**, a voz feminina brasileira aprovada em escuta. Usa
`gpt-live-1.1` pela API Live, incluindo chat interno, IJA Fly, portal, guias práticos,
chamadas por voz e resumo do DEV. Transcrição do microfone e permissões continuam
separadas da narração. As vozes anteriores permanecem como opções explícitas no
painel; não são usadas como fallback quando a Bossa falha.

O fluxo é híbrido: falas genéricas revisadas ficam no catálogo público por perfil;
respostas variáveis usam geração sob demanda e cache temporário vinculado ao
acesso/sessão. As aberturas e o convite do DEV também usam a Bossa. Mudanças de
perfil/estilo invalidam o reaproveitamento da voz anterior. Respostas privadas não
são adicionadas à biblioteca pública. Falhas de geração mantêm a resposta em texto.

`live_voice.py` envia somente o texto aprovado, sem histórico, ferramentas ou
backend de raciocínio. O servidor retém o áudio até conferir a transcrição e o
encerramento da sessão. Palavras e números alterados são rejeitados. A duração
da conexão é limitada entre 45 e 170 segundos conforme o texto, além dos limites
de memória, concorrência e consumo. Uma resposta longa pode levar mais tempo
na primeira geração; o cache evita repetir esse trabalho dentro do mesmo escopo.

A tarifa inicial é **US$ 0,05 por minuto ativo**, revisada em 24/11/2026 na
[documentação do modelo](https://developers.openai.com/api/docs/models/gpt-live-1.1).
WebSockets usam duração ativa. Antes da conexão é reservado o teto da duração;
o recibo `session.closed.usage.seconds` determina a medição. Ausência de recibo
válido mantém a reserva, sem inventar tokens ou liberar orçamento como custo zero.
Tarifas personalizadas dos demais modelos e eventos históricos são preservados.

Para renovar apenas falas genéricas aprovadas:

```bash
.venv/bin/python scripts/build_azul_recordings.py --generate --profile bossa
```

O script usa o banco de controle configurado, executa em contexto de requisição
para registrar consumo e respeitar limites, e reutiliza arquivos cujo texto e hash
já foram conferidos. `--only abertura-chamada` limita a geração a uma entrada.
Salvar as configurações não regenera a biblioteca automaticamente. Alterações na
direção vocal devem atualizar o estilo em `voice_profiles.py` antes de renovar os
áudios, para que arquivos antigos não sejam confundidos com a voz revisada.


## Orientação financeira (18/11/2026)

A base revisada de ajuda está em `app/modules/chatbot/finance_help.py`. Ela reúne
caixa, retroativos, entradas, saídas, competências, bancos/conciliação, relatórios,
categorias, comprovantes, comercial e fornecedores. O chat, as sugestões por tela
e o guia prático usam essa mesma fonte. Perguntas exatas dos atalhos e “Como usar
esta tela?” recebem orientação local, inclusive sem o provedor de IA. Perguntas
livres recebem o manual e a tela autorizada como contexto; sem IA, o guia local
cobre os assuntos reconhecidos.

Os módulos autorizados determinam o material e os atalhos oferecidos. O perfil
`financeiro_admin` recebe configurações no acesso legado; `financeiro` não recebe
esse atalho. Configurações da Central de TI continuam prevalecendo. Links de
empresa usam o contexto IJA, único que atualmente contém os registros financeiros.

A sala de treinamento contém cinco exercícios financeiros adicionais com registros
fictícios: caixa, contas, bancos, competências e relatórios. Eles não escrevem no
banco nem fazem pagamentos. O guia explica que lançar retroativos exige o caixa
de hoje aberto e que o filtro de data do caixa não muda as datas do formulário.

“Aprender” aqui significa usar o contexto da conversa e receber atualizações da
base revisada. Não há aprendizado permanente automático, armazenamento adicional
de mensagens, consulta de extratos ou edição financeira pelo chat. Ao mudar uma
regra nas rotas financeiras, atualize o guia e seus testes; mensagens dos usuários
não substituem as regras do sistema.

### Ajuste do saldo inicial do caixa (18/11/2026)

No Caixa Diário, após selecionar um dia já aberto anteriormente, o financeiro admin
pode usar **Ajustes do saldo inicial → Corrigir saldo inicial deste dia**. Informe o
novo saldo em formato brasileiro e o motivo obrigatório. Perfis configurados pela
Central TI precisam de administração das configurações financeiras e operação do
caixa. O histórico permanente guarda data, usuário, motivo e valores anterior/novo
na mesma transação da correção. A tela rejeita um envio com saldo original desatualizado.

O ajuste recalcula o fechamento do dia, mantendo o status aberto/fechado e os
lançamentos. Não propaga alterações aos saldos iniciais de dias seguintes. A tarifa
ou despesa deve ser registrada como saída na data correta; corrigir o saldo não
substitui esse registro. A Azul explica o procedimento, mas não executa o ajuste.

## Primeiro pacote Agro (19/11/2026)

A Azul oferece **Consultar Agro**, **Pendências do Agro** e perguntas de ajuda nas
listas de clientes, orçamentos, contratos, mapeamentos e OS. A orientação também
reconhece os formulários conhecidos e autorizados dessas áreas, sem consultar o
registro indicado na URL. O guia descreve o procedimento; não confirma acesso ou
situação de um registro específico.

- `buscar_agro` consulta as fontes autorizadas, com texto de busca e status quando
  suportado, retornando contagem, até cinco IDs e o atalho da lista. Datas, valores,
  equipe e filtros adicionais não são suportados. A interpretação de pedidos
  livres depende do provedor de IA.
- `consultar_pendencias_agro` e o botão **Pendências do Agro** mostram a situação
  atual de todas as datas, com data de consulta em São Paulo: mapeamentos pendentes,
  contratos aprovados sem OS, OS planejadas e OS em execução. Não representam uma
  agenda exclusiva de hoje. Os links abrem as listas para conferência, sem afirmar
  que reproduzem o filtro de cada contagem.
- Administrativo: consultas reutilizam os mesmos builders e escopo de unidade
  das listas. Mapeamentos seguem a lista administrativa: orçamentos marcados para
  mapeamento e sem contrato; pendências incluem RD não criada ou não preenchida.
- Pilotos: exigem vínculo ativo com piloto e equipe. Consultam OS e RDs da equipe;
  contratos são os aprovados sem OS mostrados na lista operacional. Consulta de
  contratos exige também a permissão própria de contratos na Central TI. Não há
  consulta de clientes ou orçamentos pelo chat do piloto.
- Cada execução confere novamente as permissões de módulo. Módulos negados não
  entram no resumo. Nas páginas/canais Agro, o modelo recebe apenas ferramentas
  Agro para não substituir consultas por registros municipais.

Ajuda revisada e o botão de resumo funcionam sem geração paga. As consultas mantêm
as quotas existentes e as respostas não são armazenadas no servidor pelo pacote.
Resultados das ferramentas são devolvidos diretamente ao usuário, sem uma segunda
chamada ao modelo. Não há alteração de registros, exportação Agro, consulta
financeira ou envio de mensagens neste pacote. Não exige migração de banco.

Validação específica: `tests/test_azul_agro.py` cobre escopo por unidade/equipe,
vínculo ausente/inativo, permissões parciais da Central TI, filtros inválidos,
resumo local, ajuda contextual e despacho das ferramentas.

### Agro — segundo pacote

- Pendências explicam o motivo da atenção e mostram até cinco IDs por categoria. Não inferem atraso, prazo ou ordem de urgência sem dados que sustentem isso.
- `detalhar_agro` resume OS e RD e pode conferir seus dados **já salvos**. A autorização é refeita usando as consultas das telas; IDs inexistentes e fora do acesso têm a mesma resposta. Para mapeamentos, o ID solicitado é o da RD.
- A conferência reutiliza os validadores dos formulários (RD em modo de conclusão). Relatório PDF e mapa da OS são opcionais, portanto sua ausência é informativa. A conferência não altera status, não salva e não atesta segurança operacional.
- `buscar_agro_periodo` aceita intervalo inclusivo ISO: OS por data de aplicação; RD do piloto por data do relatório; demais fontes por criação. Datas ausentes são excluídas quando há período. O atalho leva à lista com busca/status, mas a resposta avisa que a tela não aplica o período.
- Ajuda local: “Como preencher a RD?”, “Como preencher a OS?” e “Passo a passo desta tela”. Em formulários reconhecidos, “Como usar esta tela?” também apresenta as etapas.
- Exemplos de consultas com IA: “Resuma a OS 6”, “Confira a RD 3”, “Busque minhas OS em execução entre 01/11/2026 e 19/11/2026”. Use IDs reais e mantenha somente filtros suportados.
- O piloto continua limitado à equipe ativa vinculada; administrativo mantém escopo municipal e permissões da Central TI. Resultados de registros são formatados no servidor e não enviados a uma segunda chamada do modelo.
