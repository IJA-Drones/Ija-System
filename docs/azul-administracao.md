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
- Duração do áudio de transcrição e tokens de texto/áudio da narração.
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

As 14 gravações existentes e o cache temporário de áudio continuam funcionando. A escolha de outra voz/modelo pode exigir geração de respostas que não correspondam à biblioteca gravada; o cache é separado por voz e modelo. Não há geração automática de novas gravações ao salvar as configurações.

As duas falas fixas de abertura e de retorno ao escopo mantêm a voz original Marin. A seleção do painel se aplica às novas gerações. O painel cobre as chamadas dos canais AZUL integrados; scripts administrativos de geração de arquivos, executados fora de uma requisição, devem ser acompanhados no provedor.
