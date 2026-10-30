(() => {
  document.querySelectorAll('[data-azul-help]').forEach(root => {
    if (root.dataset.initialized) return;
    root.dataset.initialized = '1';
    const panel = root.querySelector('.azul-panel');
    const toggle = root.querySelector('[data-toggle]');
    const messages = root.querySelector('[data-messages]');
    const form = root.querySelector('form');
    const input = root.querySelector('input');
    const send = form.querySelector('button');
    const status = root.querySelector('[data-status]');
    const idleStatus = root.dataset.export === '1' ? 'Orientações e relatórios. Downloads exigem confirmação.' : 'Orientações e atalhos. Nenhuma alteração pelo chat.';
    let history = [], pending = null, generation = 0;
    let transcript = [], restoring = false;
    const storageKey = root.dataset.chatKey ? 'azul-chat:' + root.dataset.chatKey : null;
    function save() {
      if (!storageKey || restoring) return;
      try { sessionStorage.setItem(storageKey, JSON.stringify({transcript: transcript.slice(-40), history,
        opened: !panel.hidden, interrupted: !!pending, savedAt: Date.now()})); } catch (_) { /* Storage may be disabled. */ }
    }
    function renderLinks(bubble, items) {
      const links = document.createElement('div');
      links.className = 'azul-links';
      for (const item of (Array.isArray(items) ? items.slice(0,12) : [])) {
        if (!item || typeof item.label !== 'string' || typeof item.url !== 'string' || !item.url.startsWith('/') || item.url.startsWith('//') || item.url.includes('\\')) continue;
        const url = new URL(item.url, window.location.origin);
        if (url.origin !== window.location.origin) continue;
        const link = document.createElement('a');
        link.href = url.pathname + url.search;
        link.textContent = item.label;
        links.append(link);
      }
      if (links.children.length) bubble.append(links);
    }
    function restore() {
      if (!storageKey) return false;
      try {
        const raw = sessionStorage.getItem(storageKey);
        if (!raw || raw.length > 400000) return false;
        const data = JSON.parse(raw);
        if (!Array.isArray(data.transcript) || !data.transcript.length || Date.now()-data.savedAt > 86400000) return false;
        const valid = item => item && ['user','assistant'].includes(item.role) && typeof item.content === 'string' && item.content.length <= 6000;
        if (!data.transcript.every(valid) || !Array.isArray(data.history) || !data.history.every(valid)) return false;
        restoring = true;
        for (const item of data.transcript.slice(-40)) {
          const bubble = append(item.content, item.role, item.mode);
          renderLinks(bubble, item.links);
        }
        transcript = data.transcript.slice(-40);
        history = data.history.slice(-6).map(item => ({role:item.role, content:item.content.slice(0,3000)}));
        panel.hidden = !data.opened;
        toggle.setAttribute('aria-expanded', String(!panel.hidden));
        restoring = false;
        if (data.interrupted) append('A navegação interrompeu a resposta anterior. Envie sua pergunta novamente.', 'assistant', 'faq');
        save();
        return true;
      } catch (_) { restoring = false; return false; }
    }
    function append(text, role, mode) {
      const bubble = document.createElement('div');
      bubble.className = `azul-message azul-${role}`;
      if (role === 'assistant') {
        const label = document.createElement('small');
        label.textContent = mode === 'faq' ? 'AZUL · GUIA LOCAL' : 'AZUL';
        bubble.append(label);
      }
      const content = document.createElement('div');
      content.textContent = text;
      bubble.append(content);
      messages.append(bubble);
      messages.scrollTop = messages.scrollHeight;
      if (!restoring) {
        transcript.push({content:text, role, mode});
        transcript = transcript.slice(-40);
        save();
      }
      return bubble;
    }
    function welcome() {
      append('Olá! Sou a Azul.\nPosso explicar como usar o sistema e ajudar você a encontrar os recursos disponíveis para seu acesso.\n\nPor onde começamos?', 'assistant');
    }
    function open(value) {
      panel.hidden = !value;
      toggle.setAttribute('aria-expanded', String(value));
      save();
      if (value) input.focus(); else toggle.focus();
    }
    function reset() {
      generation++;
      if (pending) pending.abort();
      pending = null;
      history = [];
      transcript = [];
      try { if (storageKey) sessionStorage.removeItem(storageKey); } catch (_) {}
      send.disabled = false;
      messages.replaceChildren();
      status.textContent = idleStatus;
      root.querySelector('[data-profile]').textContent = '';
      welcome();
      input.focus();
    }
    function renderExport(bubble, preview) {
      const card = document.createElement('section');
      card.className = 'azul-export';
      const title = document.createElement('strong');
      title.textContent = `${preview.title} · ${preview.format === 'excel' ? 'Excel' : 'PDF'}`;
      card.append(title);
      const summary = document.createElement('p');
      summary.textContent = `${preview.total} registros\n` + Object.entries(preview.filters).map(([label, value]) => `${label}: ${value}`).join('\n');
      card.append(summary);
      const columns = document.createElement('p');
      columns.textContent = 'Campos: ' + preview.columns.join(', ');
      card.append(columns);
      const notice = document.createElement('p');
      notice.textContent = preview.notice;
      card.append(notice);
      const confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.textContent = 'Confirmar e baixar';
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.textContent = 'Cancelar';
      const feedback = document.createElement('p');
      feedback.setAttribute('role', 'status');
      let downloadController = null;
      cancel.addEventListener('click', () => {
        if (downloadController) downloadController.abort();
        card.replaceChildren();
        card.textContent = 'Geração cancelada.';
      });
      confirm.addEventListener('click', async () => {
        if (downloadController) return;
        // Only the application-owned endpoint is accepted, never a model URL.
        if (preview.url !== '/api/azul/exportar') return;
        const version = generation;
        downloadController = new AbortController();
        confirm.disabled = true;
        feedback.textContent = 'Gerando arquivo…';
        const timer = setTimeout(() => downloadController.abort(), 90000);
        try {
          const response = await fetch(preview.url, {
            method: 'POST', signal: downloadController.signal,
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf},
            body: JSON.stringify({token: preview.token, confirm: true})
          });
          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.error || 'Não foi possível gerar o arquivo. Confira seu acesso e peça uma nova prévia.');
          }
          const expected = preview.format === 'excel' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'application/pdf';
          if (!(response.headers.get('Content-Type') || '').startsWith(expected)) throw new Error('Sessão expirada ou arquivo indisponível. Atualize a página.');
          const blob = await response.blob();
          if (version !== generation || downloadController.signal.aborted) return;
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = preview.format === 'excel' ? 'azul-relatorio.xlsx' : 'azul-relatorio.pdf';
          card.append(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
          feedback.textContent = 'Arquivo gerado. Download iniciado.';
        } catch (error) {
          if (version === generation) feedback.textContent = error.name === 'AbortError' ? 'Geração interrompida. Tente novamente.' : error.message;
        } finally {
          clearTimeout(timer);
          downloadController = null;
          confirm.disabled = false;
        }
      });
      card.append(confirm, cancel, feedback);
      bubble.append(card);
    }
    async function ask(text, intent) {
      text = text.trim();
      if (!text || pending || text.length > 1500) return;
      open(true);
      append(text, 'user');
      input.value = '';
      send.disabled = true;
      const controller = new AbortController();
      pending = controller;
      save();
      const version = generation;
      status.textContent = 'A Azul está preparando sua resposta…';
      const timer = setTimeout(() => controller.abort(), 40000);
      try {
        const response = await fetch(root.dataset.url, {
          method: 'POST', signal: controller.signal,
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf},
          body: JSON.stringify({message: text, history: intent === 'start_report' ? [] : history, page: root.dataset.page, intent})
        });
        const data = await response.json().catch(() => ({}));
        if (version !== generation) return;
        if (!response.ok || !data.answer) throw new Error(data.answer || data.error || 'Sua sessão pode ter expirado. Atualize a página e tente novamente.');
        const bubble = append(data.answer, 'assistant', data.mode);
        const entry = transcript[transcript.length - 1];
        if (data.export_preview) {
          renderExport(bubble, data.export_preview);
          // Confirmation tokens are deliberately not persisted or replayed.
          entry.content += '\n\nPrévia de relatório: para baixar após trocar de tela, peça uma nova prévia.';
        } else {
          entry.links = Array.isArray(data.links) ? data.links.slice(0,12) : [];
          renderLinks(bubble, entry.links);
        }
        root.querySelector('[data-profile]').textContent = data.profile ? `· ${data.profile}` : '';
        history = [...(intent === 'start_report' ? [] : history), {role:'user', content:text}, {role:'assistant', content:data.answer.slice(0,3000)}].slice(-6);
        messages.scrollTop = messages.scrollHeight;
      } catch (error) {
        if (version === generation) append(error.name === 'AbortError' ? 'A resposta demorou mais que o esperado. Tente novamente.' : error.message, 'assistant', 'faq');
      } finally {
        clearTimeout(timer);
        if (version === generation) {
          pending = null;
          send.disabled = false;
          status.textContent = idleStatus;
          save();
          if (!panel.hidden) input.focus();
        }
      }
    }
    toggle.addEventListener('click', () => open(panel.hidden));
    root.querySelector('[data-close]').addEventListener('click', () => open(false));
    root.querySelector('[data-clear]').addEventListener('click', reset);
    root.addEventListener('keydown', event => { if (event.key === 'Escape' && !panel.hidden) open(false); });
    form.addEventListener('submit', event => { event.preventDefault(); ask(input.value); });
    root.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => ask(button.dataset.question, button.dataset.intent)));
    if (!restore()) welcome();
  });
})();
