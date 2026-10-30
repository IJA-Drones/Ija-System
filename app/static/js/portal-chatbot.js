(() => {
  const root = document.querySelector('[data-portal-chat]');
  if (!root) return;
  const toggle = root.querySelector('.portal-chat-toggle');
  const panel = root.querySelector('.portal-chat-panel');
  const log = root.querySelector('[role="log"]');
  const form = root.querySelector('form');
  const input = root.querySelector('textarea');
  const send = form.querySelector('button');
  const sendLabel = send.textContent;
  const clear = root.querySelector('[data-clear]');
  const status = root.querySelector('[data-status]');
  const about = root.querySelector('[data-about-oceano]');
  let history = [];
  let busy = false;
  function appendPortalText(entry, text) {
    const routes = {
      '/portal-cidadao#portal-relato': 'Registrar relato',
      '/portal-cidadao/contatos': 'Contatos das prefeituras',
      '/portal-cidadao/boletim-dengue': 'Consultar boletim',
      '/portal-cidadao#como-funciona': 'Como funciona o atendimento',
      'https://www.oceanoazuldrones.com.br/oceano': 'Site institucional da Oceano Azul'
    };
    const pattern = /https:\/\/www\.oceanoazuldrones\.com\.br\/oceano(?![\w/#?=-])|\/portal-cidadao(?:#portal-relato|\/boletim-dengue|\/contatos|#como-funciona)(?![\w/#?=-])/g;
    let cursor = 0;
    for (const match of text.matchAll(pattern)) {
      entry.append(document.createTextNode(text.slice(cursor, match.index)));
      const link = document.createElement('a');
      link.href = match[0];
      link.textContent = routes[match[0]];
      if (match[0].startsWith('https:')) {
        link.target = '_blank'; link.rel = 'noopener noreferrer';
      } else {
        link.addEventListener('click', () => show(false));
      }
      entry.append(link);
      cursor = match.index + match[0].length;
    }
    entry.append(document.createTextNode(text.slice(cursor)));
  }
  function append(text, role, parts = [], showName = true, highlightInstitutional = false) {
    const entry = document.createElement('p');
    entry.className = `portal-chat-message portal-chat-${role}`;
    entry.textContent = role === 'user' ? `Você: ${text}` : `Azul: ${text}`;
    entry.setAttribute('aria-label', role === 'user' ? 'Sua mensagem' : 'Resposta da Azul');
    if (role === 'assistant') {
      entry.textContent = showName ? 'Azul: ' : '';
      for (const part of (parts.length ? parts : [{text}])) {
        let url;
        try { url = new URL(part.url); } catch (_) { url = null; }
        if (url?.protocol === 'https:' && !url.username && !url.password) {
          const link = document.createElement('a');
          link.href = url.href;
          link.textContent = part.text || '[Fonte]';
          link.title = part.title || 'Fonte oficial';
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          entry.append(link);
        } else {
          if (highlightInstitutional) {
            const content = part.text || '';
            const keywords = /\b(drones?|mapeamento|combate à dengue|identificação de focos|registrar um relato)\b/gi;
            let cursor = 0;
            for (const match of content.matchAll(keywords)) {
              entry.append(document.createTextNode(content.slice(cursor, match.index)));
              const emphasis = document.createElement('strong');
              emphasis.textContent = match[0];
              entry.append(emphasis);
              cursor = match.index + match[0].length;
            }
            entry.append(document.createTextNode(content.slice(cursor)));
          } else {
            appendPortalText(entry, part.text || '');
          }
        }
      }
    }
    log.append(entry);
    log.scrollTop = log.scrollHeight;
  }
  const quickAnswers = [
    {question: 'Como registrar um foco?', answer: 'Clique em Registrar relato aqui no chat. O formulário guia você por cinco etapas: ocorrência, endereço, identificação, detalhes e revisão. Depois de conferir os dados e o consentimento, clique em Confirmar e enviar. Guarde o protocolo exibido após a confirmação.'},
    {question: 'Posso enviar fotos?', answer: 'Sim! Na etapa Detalhes do relato, você pode anexar até cinco fotos ou vídeos. Os anexos são opcionais e ajudam a equipe a entender o problema. Envie os arquivos pelo formulário de relato, não pela conversa.'},
    {question: 'Quais dados preciso informar?', answer: 'Informe o tipo de ocorrência, o foco, logradouro, número, bairro e cidade, além de nome completo, CPF e telefone com DDD. Para Aedes, selecione também o tipo de local. RG e CEP são opcionais. Preencha seus dados pessoais somente nos campos do formulário e confirme o consentimento antes de enviar.'},
    {question: 'O que acontece depois do envio?', answer: 'Após a confirmação, seu relato recebe um protocolo. A COVISA analisa as informações, encaminha à coordenadoria e esta define a UVIS responsável. A unidade avalia o atendimento. O envio não garante visita imediata nem prazo de execução. Ainda não há consulta pública do andamento pelo chatbot.'}
  ];
  function answerQuick(item) {
    if (busy) return;
    append(item.question, 'user');
    append(item.answer, 'assistant');
    history = [...history, {role: 'user', content: item.question},
      {role: 'assistant', content: item.answer}].slice(-6);
    input.focus();
  }
  function welcome() {
    append('Olá! Sou a Azul. Posso ajudar com saúde, prevenção, vigilância e uso do Portal do Cidadão, além dos contatos da Prefeitura e do canal institucional da Oceano Azul. Escolha uma dúvida abaixo ou escreva sua pergunta. Você também pode registrar um relato por aqui.', 'assistant', [], false);
    const suggestions = document.createElement('details');
    suggestions.open = true;
    suggestions.className = 'portal-chat-suggestions';
    suggestions.setAttribute('aria-label', 'Perguntas rápidas');
    const heading = document.createElement('summary');
    heading.textContent = 'Dúvidas frequentes';
    const hint = document.createElement('span');
    hint.textContent = 'Toque em uma pergunta para ver a orientação.';
    suggestions.append(heading); suggestions.append(hint);
    for (const item of quickAnswers) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item.question;
      button.addEventListener('click', () => answerQuick(item));
      suggestions.append(button);
    }
    log.append(suggestions);
    log.scrollTop = 0;
  }
  function show(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    const mobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 600px)').matches;
    (open ? (mobile ? root.querySelector('[data-close]') : input) : toggle).focus();
  }
  toggle.addEventListener('click', () => show(panel.hidden));
  root.querySelector('[data-close]').addEventListener('click', () => show(false));
  root.addEventListener('keydown', event => { if (event.key === 'Escape') show(false); });
  clear.addEventListener('click', () => { if (busy) return; history = []; log.replaceChildren(); welcome(); input.focus(); });
  about?.addEventListener('click', () => {
    if (busy || !about.dataset.summary) return;
    const question = 'Quem é a Oceano Azul?';
    const answer = about.dataset.summary;
    append(question, 'user');
    append(answer, 'assistant', [{text: answer + '\n\n'},
      {text: 'Conheça o site institucional da Oceano Azul', url: about.dataset.source, title: 'Site institucional da empresa'}], true, true);
    history = [...history, {role: 'user', content: question},
      {role: 'assistant', content: answer + '\nFonte: ' + about.dataset.source}].slice(-6);
    input.focus();
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (busy || !message) return;
    if (/^(?:quero|gostaria de|preciso|desejo|vamos)?\s*(?:fazer|criar|registrar|enviar|abrir)\s+(?:um[a]?\s+)?(?:relato|den[uú]ncia|ocorr[eê]ncia)[.!?]*$/i.test(message)) {
      input.value = '';
      root.dispatchEvent(new CustomEvent('portal:start-report'));
      return;
    }
    const normalized = message.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[?!.]+$/g, '').trim();
    const quick = quickAnswers.find(item => item.question.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[?!.]+$/g, '').trim() === normalized);
    if (quick) { input.value = ''; answerQuick(quick); return; }
    busy = true; send.disabled = true; clear.disabled = true; if (about) about.disabled = true;
    send.textContent = 'Aguarde…';
    form.setAttribute('aria-busy', 'true');
    append(message, 'user');
    input.value = '';
    status.textContent = 'Preparando resposta…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(root.dataset.url, {
        method: 'POST', signal: controller.signal, credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-Portal-Chat-Token': root.dataset.token,
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''},
        body: JSON.stringify({message, history})
      });
      const data = await response.json();
      if (!response.ok || !data.answer) throw new Error(data.error || 'Não foi possível responder agora.');
      append(data.answer, 'assistant', data.parts || []);
      history = [...history, {role: 'user', content: message}, {role: 'assistant', content: data.answer}].slice(-6);
    } catch (error) {
      append(error.name === 'AbortError' ? 'A resposta demorou. Tente novamente.' : (error.message === 'Failed to fetch' ? 'Falha de conexão. Tente novamente.' : error.message), 'assistant');
      input.value = message;
    } finally {
      clearTimeout(timeout); busy = false; send.disabled = false; clear.disabled = false; status.textContent = '';
      send.textContent = sendLabel;
      if (about) about.disabled = false;
      form.setAttribute('aria-busy', 'false');
      if (!panel.hidden) input.focus();
    }
  });
  welcome();
})();
