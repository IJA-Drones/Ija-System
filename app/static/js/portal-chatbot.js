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
  let history = [];
  let busy = false;
  function appendPortalText(entry, text) {
    const routes = {
      '/portal-cidadao#portal-relato': 'Registrar relato',
      '/portal-cidadao/boletim-dengue': 'Consultar boletim',
      '/portal-cidadao#como-funciona': 'Como funciona o atendimento'
    };
    const pattern = /\/portal-cidadao(?:#portal-relato|\/boletim-dengue|#como-funciona)(?![\w/#?=-])/g;
    let cursor = 0;
    for (const match of text.matchAll(pattern)) {
      entry.append(document.createTextNode(text.slice(cursor, match.index)));
      const link = document.createElement('a');
      link.href = match[0];
      link.textContent = routes[match[0]];
      link.addEventListener('click', () => show(false));
      entry.append(link);
      cursor = match.index + match[0].length;
    }
    entry.append(document.createTextNode(text.slice(cursor)));
  }
  function append(text, role, parts = []) {
    const entry = document.createElement('p');
    entry.className = `portal-chat-message portal-chat-${role}`;
    entry.textContent = `${role === 'user' ? 'Você' : 'Assistente'}: ${text}`;
    if (role === 'assistant') {
      entry.textContent = 'Assistente: ';
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
          appendPortalText(entry, part.text || '');
        }
      }
    }
    log.append(entry);
    log.scrollTop = log.scrollHeight;
  }
  function welcome() { append('Olá! Posso orientar sobre o portal e consultar fontes oficiais sobre vigilância e prevenção. Para registrar uma ocorrência, use o botão Registrar relato aqui no chat.', 'assistant'); }
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
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (busy || !message) return;
    if (/^(?:quero|gostaria de|preciso|desejo|vamos)?\s*(?:fazer|criar|registrar|enviar|abrir)\s+(?:um[a]?\s+)?(?:relato|den[uú]ncia|ocorr[eê]ncia)[.!?]*$/i.test(message)) {
      input.value = '';
      root.dispatchEvent(new CustomEvent('portal:start-report'));
      return;
    }
    busy = true; send.disabled = true; clear.disabled = true;
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
      form.setAttribute('aria-busy', 'false');
      if (!panel.hidden) input.focus();
    }
  });
  welcome();
})();
