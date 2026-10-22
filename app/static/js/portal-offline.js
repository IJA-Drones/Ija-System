// Fila offline de relatos do cidadão (IndexedDB). Reenvia ao voltar a conexão.
(function () {
  'use strict';
  const DB = 'ija-portal', STORE = 'relatos', MAX_FILE = 4 * 1024 * 1024;
  const status = () => document.getElementById('portal-offline-status');
  function open() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
      req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
    });
  }
  function tx(mode, fn) {
    return open().then(db => new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode); const r = fn(t.objectStore(STORE));
      t.oncomplete = () => resolve(r && r.result !== undefined ? r.result : r); t.onerror = () => reject(t.error);
    }));
  }
  const all = () => tx('readonly', s => s.getAll());
  const remove = id => tx('readwrite', s => s.delete(id));
  async function save(form) {
    try {
      const fields = [], files = [];
      for (const [name, value] of new FormData(form).entries()) {
        if (value instanceof File) { if (value.size && value.size <= MAX_FILE) files.push({ name, filename: value.name, type: value.type, blob: value }); }
        else fields.push([name, value]);
      }
      await tx('readwrite', s => s.add({ fields, files, action: form.action, savedAt: Date.now() }));
      render();
      return true;
    } catch (e) { console.warn('Fila offline indisponível', e); return false; }
  }
  let sending = false;
  async function flush() {
    if (sending || !navigator.onLine) return;
    sending = true;
    try {
      for (const item of await all()) {
        const body = new FormData();
        item.fields.forEach(([k, v]) => body.append(k, v));
        item.files.forEach(f => body.append(f.name, f.blob, f.filename));
        body.set('offline_enviado_em', new Date(item.savedAt).toISOString());
        try {
          const response = await fetch(item.action, { method: 'POST', body, headers: { Accept: 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' } });
          const data = await response.json().catch(() => ({}));
          if (response.ok && data.success) { await remove(item.id); notify('Relato enviado: protocolo ' + data.protocolo); }
          else if (response.status >= 400 && response.status < 500) { await remove(item.id); notify('Um relato salvo offline foi recusado: ' + (Object.values(data.errors || {})[0] || 'dados inválidos')); }
        } catch (e) { break; }
      }
    } finally { sending = false; render(); }
  }
  function notify(text) { const el = status(); if (el) { el.textContent = text; el.hidden = false; } }
  async function render() {
    const el = status(); if (!el) return;
    try { const items = await all(); if (items.length) { el.hidden = false; el.textContent = items.length + ' relato(s) salvo(s) neste aparelho aguardando conexão.'; } else if (!el.dataset.keep) el.hidden = true; }
    catch (e) { /* sem IndexedDB */ }
  }
  window.PortalOffline = { save, flush, all };
  window.addEventListener('online', flush);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) flush(); });
  render(); flush();
})();
