(() => {
  'use strict';
  const controllers = [];
  let decisionOpen = false;
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
    if (!c || c.direct) return;
    const ticket = get('X-Edit-Ticket');
    const versions = (get('X-Edit-Versions') || '').split(',').map(Number);
    // Concurrent media responses can arrive out of order.
    if (ticket && (!c.versions || versions.every((v, i) => v >= c.versions[i]))) {
      c.ticket.value = ticket; c.versions = versions;
    }
    if (get('X-Edit-Released') === '1') {
      c.token.value = ''; c.lock();
      c.show('Alterações salvas. A reserva foi liberada. Recarregue para consultar os dados atualizados.', true, 'Alterações salvas');
    } else if (status === 409) {
      c.lock(); c.show('A operação encontrou um conflito de edição. Seus campos foram mantidos nesta tela. Copie o que precisar e recarregue para revisar.', true, 'Conflito de edição');
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
        if (c.direct) return;
        c.editing = false;
        editableControls().forEach(el => {
          if (box.contains(el)) return;
          if (!controls.has(el)) controls.set(el, el.disabled);
          el.disabled = true;
        });
      };
      c.show = (message, attention = false, title = '') => {
        box.querySelector('.edit-message').textContent = message;
        const heading = box.querySelector('.edit-title');
        if (heading) heading.textContent = title || (attention ? 'A edição precisa da sua atenção' : 'Edição em andamento');
        box.classList.toggle('alert-warning', attention);
        box.classList.toggle('alert-info', !attention);
        if (attention) { reload.hidden = false; start.hidden = true; }
        if (!c.token.value) cancel.hidden = true;
      };
      function allowDirectEditing() {
        c.direct = true; c.editing = true;
        c.token.value = ''; c.ticket.value = '';
        controls.forEach((disabled, el) => { el.disabled = disabled; }); controls.clear();
        start.hidden = true; cancel.hidden = true; reload.hidden = true;
        if (dev) dev.hidden = true;
        box.hidden = true;
      }
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
        c.lock(); c.show(error.message || 'Sem conexão. A edição foi pausada para proteger os dados. Seus campos continuam nesta tela.', true,
          error.data?.code === 'busy' ? 'Este registro já está sendo editado' : 'Edição pausada');
        if (dev && error.data?.code === 'busy') dev.hidden = false;
        if (error.data?.code === 'busy') { start.hidden = false; start.textContent = 'Tentar novamente'; }
      }
      async function confirmDiscard(reloading) {
        if (decisionOpen) return;
        if (!window.Swal) {
          c.show('Não foi possível abrir a confirmação. Nenhuma alteração foi descartada. Aguarde e tente novamente.', true);
          return;
        }
        decisionOpen = true;
        const swal = window.Swal;
        try {
          const result = await swal.fire({
            title: reloading ? 'Recarregar este registro?' : 'Descartar alterações e liberar?',
            text: `Registro #${c.key.split(':')[1]}. Os campos ainda não salvos serão descartados e a página será recarregada. Arquivos e alterações já salvos não serão desfeitos.`,
            footer: reloading ? 'Se precisar preservar algum texto, volte e copie antes de continuar.' : 'Ao liberar, outro usuário poderá iniciar uma edição protegida deste registro.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: reloading ? 'Descartar e recarregar' : 'Descartar alterações e liberar',
            cancelButtonText: reloading || !c.editing ? 'Voltar ao registro' : 'Continuar editando',
            reverseButtons: true, focusCancel: true, returnFocus: true,
            buttonsStyling: false,
            customClass: {popup: 'edit-confirm-popup', confirmButton: 'btn btn-danger', cancelButton: 'btn btn-outline-secondary'},
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !swal.isLoading(),
            allowEscapeKey: () => !swal.isLoading(),
            preConfirm: async () => {
              c.releasing = true;
              try {
                await release();
                return true;
              } catch (error) {
                // An already ended lease needs no release; never ignore network/auth failures.
                if (error.data?.code === 'expired') {
                  c.token.value = ''; c.lock(); cancel.hidden = true;
                  return true;
                }
                fail(error);
                swal.showValidationMessage('Não foi possível liberar o registro. Seus campos foram mantidos. Verifique a conexão ou volte ao registro e tente novamente.');
                return false;
              } finally { c.releasing = false; }
            }
          });
          if (result.isConfirmed) location.reload();
        } finally { decisionOpen = false; }
      }
      c.lock();
      start.addEventListener('click', async () => {
        start.disabled = true;
        try {
          const data = await call('reservar');
          if (data.required === false) { allowDirectEditing(); return; }
          c.token.value = data.token; c.expires = Date.parse(data.expires); c.lastActivity = Date.now();
          controls.forEach((disabled, el) => { el.disabled = disabled; }); controls.clear();
          c.editing = true; start.hidden = true; cancel.hidden = false; reload.hidden = true;
          if (dev) dev.hidden = true;
          c.show('Você está editando. Outros usuários podem consultar, mas não alterar este registro. Salvar ou cancelar libera a reserva.');
        } catch (error) { fail(error); }
        finally { start.disabled = false; }
      });
      cancel.addEventListener('click', () => confirmDiscard(false));
      reload.addEventListener('click', () => confirmDiscard(true));
      box.querySelector('.edit-force')?.addEventListener('click', async () => {
        try {
          await call('liberar-dev', {motivo: box.querySelector('.edit-reason').value});
          c.show('Reserva liberada e ação registrada. Recarregue antes de iniciar uma nova edição.', true);
          if (dev) dev.hidden = true;
        } catch (error) { fail(error); }
      });
      ['input','change','pointerdown','keydown'].forEach(type => form.addEventListener(type, () => { c.lastActivity = Date.now(); }));
      form.addEventListener('submit', event => {
        if (c.direct) return;
        if (c.releasing || !c.editing || !c.token.value || Date.now() >= c.expires) {
          event.preventDefault(); event.stopImmediatePropagation();
          c.lock(); c.show('A edição não está reservada ou a reserva expirou. Copie o que precisar e recarregue antes de salvar.', true);
          box.scrollIntoView({block:'center', behavior:'smooth'});
        }
      }, true);
      // Renew only for active editing. An abandoned/background tab expires naturally.
      setInterval(async () => {
        if (c.direct || c.releasing || !c.editing || !c.token.value) return;
        if (Date.now() >= c.expires) {
          c.lock(); c.show('Sua reserva expirou por falta de atividade. Os campos permanecem nesta tela; copie o que precisar e recarregue.', true); return;
        }
        if (document.hidden || Date.now() - c.lastActivity > 90000) return;
        try {
          const data = await call('renovar');
          if (data.required === false) { allowDirectEditing(); return; }
          c.expires = Date.parse(data.expires);
        }
        catch (error) { fail(error); }
      }, 20000);
      // Do not release on pagehide: it races normal form submission. Timeout recovers closed tabs.
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
