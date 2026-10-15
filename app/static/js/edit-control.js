(() => {
  'use strict';
  const controllers = [];
  const unsafe = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
  function localURL(input) {
    try { const u = new URL(input, location.href); return u.origin === location.origin ? u : null; }
    catch (_) { return null; }
  }
  function controllerFor(input) {
    const url = localURL(input);
    if (!url || url.pathname.startsWith('/api/edicao/')) return null;
    return controllers.find(c => c.token.value && (
      localURL(c.form.action)?.pathname === url.pathname ||
      (c.key.startsWith('solicitacao:') && (url.pathname.startsWith('/api/video-upload-sessions/') || url.pathname.startsWith('/api/video-upload-jobs/'))) ||
      (c.key.startsWith('solicitacao:') && new RegExp('^/api/os/' + c.key.split(':')[1] + '/').test(url.pathname))
    ));
  }
  function addHeaders(c, headers) {
    if (!c) return;
    headers.set('X-Edit-Token', c.token.value);
    headers.set('X-Edit-Ticket', c.ticket.value);
  }
  function responseHeaders(c, get, status) {
    if (!c) return;
    const ticket = get('X-Edit-Ticket');
    const versions = (get('X-Edit-Versions') || '').split(',').map(Number);
    // Concurrent media responses can arrive out of order.
    if (ticket && (!c.versions || versions.every((v, i) => v >= c.versions[i]))) {
      c.ticket.value = ticket; c.versions = versions;
    }
    if (get('X-Edit-Released') === '1') {
      c.token.value = ''; c.lock();
      c.show('Alterações salvas. A reserva foi liberada. Recarregue para consultar os dados atualizados.', true);
    } else if (status === 409) {
      c.lock(); c.show('A operação encontrou um conflito de edição. Seus campos foram mantidos nesta tela. Copie o que precisar e recarregue para revisar.', true);
    }
  }
  const originalFetch = window.fetch;
  window.fetch = async function(input, options = {}) {
    const url = input instanceof Request ? input.url : input;
    const method = String(options.method || input?.method || 'GET').toUpperCase();
    const c = (unsafe.has(method) || localURL(url)?.pathname.startsWith('/api/video-upload-jobs/')) ? controllerFor(url) : null;
    if (c) {
      const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
      addHeaders(c, headers); options = {...options, headers};
    }
    const result = await originalFetch.call(this, input, options);
    responseHeaders(c, name => result.headers.get(name), result.status);
    return result;
  };
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...args) {
    this._editController = unsafe.has(String(method).toUpperCase()) ? controllerFor(url) : null;
    return originalOpen.call(this, method, url, ...args);
  };
  XMLHttpRequest.prototype.send = function(...args) {
    const c = this._editController;
    if (c) {
      this.setRequestHeader('X-Edit-Token', c.token.value);
      this.setRequestHeader('X-Edit-Ticket', c.ticket.value);
      this.addEventListener('load', () => responseHeaders(c, name => this.getResponseHeader(name), this.status));
    }
    return originalSend.apply(this, args);
  };

  function init() {
    document.querySelectorAll('.edit-control').forEach(box => {
      const form = box.closest('form');
      if (!form || form.dataset.tiAllowed === 'false') return;
      const c = {box, form, key: box.dataset.editKey,
        ticket: box.querySelector('[name="_edit_ticket"]'), token: box.querySelector('[name="_edit_token"]'),
        expires: 0, lastActivity: Date.now(), editing: false};
      controllers.push(c);
      const start = box.querySelector('.edit-start'), cancel = box.querySelector('.edit-cancel');
      const reload = box.querySelector('.edit-reload'), dev = box.querySelector('.edit-dev');
      const controls = new Map();
      const editableControls = () => form.querySelectorAll('input:not([type="hidden"]), select, textarea, button:not([role="tab"])');
      c.lock = () => {
        c.editing = false;
        editableControls().forEach(el => {
          if (box.contains(el)) return;
          if (!controls.has(el)) controls.set(el, el.disabled);
          el.disabled = true;
        });
      };
      c.show = (message, attention = false) => {
        box.querySelector('.edit-message').textContent = message;
        box.classList.toggle('alert-warning', attention);
        box.classList.toggle('alert-info', !attention);
        if (attention) { reload.hidden = false; start.hidden = true; }
      };
      async function call(action, extra = {}, keepalive = false) {
        const response = await fetch(`${box.dataset.editApi}/${action}`, {
          method: 'POST', credentials: 'same-origin', keepalive,
          headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
          body: JSON.stringify({ticket: c.ticket.value, token: c.token.value, ...extra})
        });
        const data = await response.json();
        if (!response.ok) { const error = new Error(data.error || 'Não foi possível verificar sua reserva.'); error.data = data; throw error; }
        return data;
      }
      async function release() {
        if (c.token.value) await call('liberar');
        c.token.value = ''; c.lock(); cancel.hidden = true;
      }
      function fail(error) {
        c.lock(); c.show(error.message || 'Sem conexão. A edição foi pausada para proteger os dados.', true);
        if (dev && error.data?.code === 'busy') dev.hidden = false;
        if (error.data?.code === 'busy') { start.hidden = false; start.textContent = 'Tentar novamente'; }
      }
      c.lock();
      start.addEventListener('click', async () => {
        start.disabled = true;
        try {
          const data = await call('reservar');
          c.token.value = data.token; c.expires = Date.parse(data.expires); c.lastActivity = Date.now();
          controls.forEach((disabled, el) => { el.disabled = disabled; }); controls.clear();
          c.editing = true; start.hidden = true; cancel.hidden = false; reload.hidden = true;
          if (dev) dev.hidden = true;
          c.show('Você está editando. Outros usuários podem consultar, mas não alterar este registro. Salvar ou cancelar libera a reserva.');
        } catch (error) { fail(error); }
        finally { start.disabled = false; }
      });
      cancel.addEventListener('click', async () => {
        if (!window.confirm('Cancelar a edição e liberar o registro? Os dados ainda não salvos serão descartados ao recarregar.')) return;
        try { await release(); location.reload(); } catch (error) { fail(error); }
      });
      reload.addEventListener('click', async () => {
        if (!window.confirm('Recarregar os dados atuais? Copie antes qualquer informação ainda não salva.')) return;
        try { await release(); } catch (_) { /* expired/revoked leases are already safe */ }
        location.reload();
      });
      box.querySelector('.edit-force')?.addEventListener('click', async () => {
        try {
          await call('liberar-dev', {motivo: box.querySelector('.edit-reason').value});
          c.show('Reserva liberada e ação registrada. Recarregue antes de iniciar uma nova edição.', true);
          if (dev) dev.hidden = true;
        } catch (error) { fail(error); }
      });
      ['input','change','pointerdown','keydown'].forEach(type => form.addEventListener(type, () => { c.lastActivity = Date.now(); }));
      form.addEventListener('submit', event => {
        if (!c.editing || !c.token.value || Date.now() >= c.expires) {
          event.preventDefault(); event.stopImmediatePropagation();
          c.lock(); c.show('A edição não está reservada ou a reserva expirou. Copie o que precisar e recarregue antes de salvar.', true);
          box.scrollIntoView({block:'center', behavior:'smooth'});
        }
      }, true);
      // Renew only for active editing. An abandoned/background tab expires naturally.
      setInterval(async () => {
        if (!c.editing || !c.token.value) return;
        if (Date.now() >= c.expires) {
          c.lock(); c.show('Sua reserva expirou por falta de atividade. Os campos permanecem nesta tela; copie o que precisar e recarregue.', true); return;
        }
        if (document.hidden || Date.now() - c.lastActivity > 90000) return;
        try { const data = await call('renovar'); c.expires = Date.parse(data.expires); }
        catch (error) { fail(error); }
      }, 20000);
      // Do not release on pagehide: it races normal form submission. Timeout recovers closed tabs.
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
