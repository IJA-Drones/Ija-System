// IJA Vigilância — aplicativo instalado pela web. Mesmas telas, textos e fluxos do app Android.
(function () {
  'use strict';
  const $app = document.getElementById('app');
  const $toast = document.getElementById('toast');
  const $dialog = document.getElementById('dialog');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

  // ------------------------------------------------------------------ ícones (Material, 24x24)
  const I = {
    bug: 'M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5c-.49 0-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z',
    sick: 'M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 3c-2.33 0-4.31 1.46-5.11 3.5h10.22c-.8-2.04-2.78-3.5-5.11-3.5z',
    campaign: 'M18 11v2h4v-2h-4zm-2 6.61c.96.71 2.21 1.65 3.2 2.39.4-.53.8-1.07 1.2-1.6-.99-.74-2.24-1.68-3.2-2.4-.4.54-.8 1.08-1.2 1.61zM20.4 5.6c-.4-.53-.8-1.07-1.2-1.6-.99.74-2.24 1.68-3.2 2.4.4.53.8 1.07 1.2 1.6.96-.72 2.21-1.65 3.2-2.4zM4 9c-1.1 0-2 .9-2 2v2c0 1.1.9 2 2 2h1v4h2v-4h1l5 3V6L8 9H4zm11.5 3c0-1.33-.58-2.53-1.5-3.35v6.69c.92-.81 1.5-2.01 1.5-3.34z',
    chat: 'M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z',
    badge: 'M20 7h-5V4c0-1.1-.9-2-2-2h-2c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM9 12c.83 0 1.5.67 1.5 1.5S9.83 15 9 15s-1.5-.67-1.5-1.5S8.17 12 9 12zm3 6H6v-.75c0-1 2-1.5 3-1.5s3 .5 3 1.5V18zm1-9h-2V4h2v5zm5 7.5h-4V15h4v1.5zm0-3h-4V12h4v1.5z',
    chevron: 'M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z',
    back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
    history: 'M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z',
    camera: 'M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z',
    gallery: 'M22 16V4c0-1.1-.9-2-2-2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2zm-11-4l2.03 2.71L16 11l4 5H8l3-4zM2 6v14c0 1.1.9 2 2 2h14v-2H4V6H2z',
    gps: 'M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z',
    gpsOff: 'M20.94 11c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z',
    send: 'M2.01 21L23 12 2.01 3 2 10l15 2-15 2z',
    map: 'M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z',
    refresh: 'M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z',
    logout: 'M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z',
    warning: 'M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z',
    check: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
    cloudOff: 'M19.35 10.04C18.67 6.59 15.64 4 12 4c-1.48 0-2.85.43-4.01 1.17l1.46 1.46C10.21 6.23 11.08 6 12 6c3.04 0 5.5 2.46 5.5 5.5v.5H19c1.66 0 3 1.34 3 3 0 1.13-.64 2.11-1.56 2.62l1.45 1.45C23.16 18.16 24 16.68 24 15c0-2.64-2.05-4.78-4.65-4.96zM3 5.27l2.75 2.74C2.56 8.15 0 10.77 0 14c0 3.31 2.69 6 6 6h11.73l2 2L21 20.73 4.27 4 3 5.27zM7.73 10l8 8H6c-2.21 0-4-1.79-4-4s1.79-4 4-4h1.73z',
    schedule: 'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z',
    error: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z',
    close: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
    city: 'M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5V9h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V9h2v2zm0-4h-2V5h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z',
    person: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
    lock: 'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z',
    home: 'M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z',
    route: 'M19 15.18V7c0-2.21-1.79-4-4-4s-4 1.79-4 4v10c0 1.1-.9 2-2 2s-2-.9-2-2V8.82C8.16 8.4 9 7.3 9 6c0-1.66-1.34-3-3-3S3 4.34 3 6c0 1.3.84 2.4 2 2.82V17c0 2.21 1.79 4 4 4s4-1.79 4-4V7c0-1.1.9-2 2-2s2 .9 2 2v8.18c-1.16.41-2 1.51-2 2.82 0 1.66 1.34 3 3 3s3-1.34 3-3c0-1.3-.84-2.4-2-2.82z',
    walk: 'M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.8 8.9L7 23h2.1l1.8-8 2.1 2v6h2v-7.5l-2.1-2 .6-3C14.8 12 16.8 13 19 13v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1L6 8.3V13h2V9.6l1.8-.7',
    play: 'M8 5v14l11-7z',
    stop: 'M6 6h12v12H6z',
    nav: 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    grid: 'M3 3v8h8V3H3zm6 6H5V5h4v4zm-6 4v8h8v-8H3zm6 6H5v-4h4v4zm4-16v8h8V3h-8zm6 6h-4V5h4v4zm-6 4v8h8v-8h-8zm6 6h-4v-4h4v4z',
    event: 'M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V3h-2zm3 18H5V8h14v11z',
    sync: 'M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z',
    bell: 'M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z',
    save: 'M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z',
    search: 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
    wifiOff: 'M22.99 9C19.15 5.16 13.8 3.76 8.84 4.78l2.52 2.52c3.47-.17 6.99 1.05 9.63 3.7l2-2zm-4 4c-1.29-1.29-2.84-2.13-4.49-2.56l3.53 3.53.96-.97zM2 3.05L5.07 6.1C3.6 6.82 2.22 7.78 1 9l1.99 2c1.24-1.24 2.67-2.16 4.2-2.77l2.24 2.24C7.81 10.89 6.27 11.73 5 13v.01L6.99 15c1.36-1.36 3.14-2.04 4.92-2.06L18.98 20l1.27-1.26L3.29 1.79 2 3.05zM9 17l3 3 3-3c-1.65-1.66-4.34-1.66-6 0z',
  };
  const svg = (name, cls) => `<svg class="${cls || ''}" viewBox="0 0 24 24" aria-hidden="true"><path d="${I[name]}"/></svg>`;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------------ armazenamento local
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* privado */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* privado */ } },
  };
  const state = {
    config: store.get('config', null),
    prefeituraId: store.get('prefeitura_id', null),
    configError: null,
    token: store.get('agente_token', null),
    agente: store.get('agente_usuario', null),
    painel: store.get('agente_painel', null),
    me: store.get('agente_me', null),
    deviceId: store.get('device_id', null) || (() => { const id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()); store.set('device_id', id); return id; })(),
  };
  const prefeituras = () => (state.config && state.config.prefeituras) || [];
  const catalogo = () => (state.config && state.config.catalogo) || {};
  const nomePrefeitura = (id) => (prefeituras().find((p) => p.id === id) || {}).nome || '';
  const setPrefeitura = (id) => { state.prefeituraId = id; store.set('prefeitura_id', id); };
  const setAgente = (token, usuario) => {
    state.token = token; state.agente = usuario;
    if (token) { store.set('agente_token', token); store.set('agente_usuario', usuario); }
    else { store.del('agente_token'); store.del('agente_usuario'); store.del('agente_painel'); store.del('agente_me'); state.painel = null; state.me = null; }
  };

  // ------------------------------------------------------------------ API
  class ApiError extends Error {
    constructor(status, message, errors) { super(message); this.status = status; this.errors = errors || {}; }
    get display() { const v = Object.values(this.errors); return v.length ? v.map((e) => '• ' + e).join('\n') : this.message; }
  }
  class OfflineError extends Error { constructor() { super('Sem conexão com a internet.'); } }
  async function request(path, { method = 'GET', body, json = true, token, timeout = 30000 } = {}) {
    if (window.__forceOffline || navigator.onLine === false) throw new OfflineError();
    const headers = { Accept: 'application/json' };
    if (json && body !== undefined) headers['Content-Type'] = 'application/json';
    if (csrf) headers['X-CSRFToken'] = csrf;
    if (token) headers.Authorization = 'Bearer ' + token;
    let response;
    try {
      response = await fetch(path, { method, headers, body: json && body !== undefined ? JSON.stringify(body) : body,
        signal: AbortSignal.timeout ? AbortSignal.timeout(timeout) : undefined, cache: 'no-store' });
    } catch (e) { throw new OfflineError(); }
    let data = {};
    try { data = await response.json(); } catch (e) { data = {}; }
    if (response.ok) return data;
    const errors = data && typeof data.errors === 'object' ? data.errors : {};
    throw new ApiError(response.status, String(data.error || data.message || data.mensagem || ('Erro ' + response.status + ' no servidor.')), errors);
  }
  const api = {
    get: (path, token) => request(path, { token, timeout: 20000 }),
    post: (path, body, token, timeout) => request(path, { method: 'POST', body, token, timeout }),
    multipart(path, fields, files) {
      const fd = new FormData();
      Object.entries(fields).forEach(([k, v]) => fd.append(k, v == null ? '' : String(v)));
      (files || []).forEach((f) => fd.append('midias', f, f.name || 'foto.jpg'));
      return request(path, { method: 'POST', body: fd, json: false, timeout: 90000 });
    },
  };

  // ------------------------------------------------------------------ fila offline (IndexedDB)
  const idb = {
    open() {
      return new Promise((resolve, reject) => {
        if (!window.indexedDB) return reject(new Error('sem IndexedDB'));
        const r = indexedDB.open('ija-movel', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('outbox', { keyPath: 'id' });
        r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error);
      });
    },
    async tx(mode, fn) {
      const db = await this.open();
      return new Promise((resolve, reject) => {
        const t = db.transaction('outbox', mode); const req = fn(t.objectStore('outbox'));
        t.oncomplete = () => { db.close(); resolve(req && req.result); }; t.onerror = () => { db.close(); reject(t.error); };
      });
    },
    all() { return this.tx('readonly', (s) => s.getAll()); },
    put(item) { return this.tx('readwrite', (s) => s.put(item)); },
  };
  const outbox = {
    items: [], flushing: false,
    pendingCount() { return this.items.filter((i) => !i.protocolo && !i.erro).length; },
    titulo(it) {
      if (it.kind === 'foco') return 'Foco: ' + (it.fields.foco || '');
      if (it.kind === 'visita') return 'Visita: imóvel ' + (it.fields.imovel_codigo || '') + ' (' + (it.fields.quarteirao || '') + ')';
      return 'Caso suspeito: ' + (it.fields.nome || '');
    },
    async init() {
      try { this.items = (await idb.all()).sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1)); } catch (e) { this.items = []; }
    },
    async save(item) {
      try { await idb.put(item); } catch (e) { /* fica só em memória */ }
      document.dispatchEvent(new CustomEvent('outbox'));
    },
    async post(item) {
      if (item.kind === 'foco') return String((await api.multipart('/portal-cidadao/denuncias', item.fields, item.files)).protocolo || '');
      if (item.kind === 'visita') return String((await api.post('/api/mobile/agente/visitas', item.fields, state.token)).inspecao_codigo || '');
      return String((await api.post('/api/mobile/relato-saude', item.fields)).protocolo || '');
    },
    // Tenta enviar agora. Devolve o protocolo, ou null se ficou na fila (sem rede). 400 sobe como ApiError.
    async send(kind, fields, files) {
      const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
      if (kind === 'caso') fields.envio_id = id;
      const item = { id, kind, fields, files: files || [], createdAt: new Date().toISOString(), protocolo: null, erro: null };
      try {
        item.protocolo = await this.post(item);
        this.items.unshift(item); await this.save(item);
        return item.protocolo;
      } catch (e) {
        if (!(e instanceof OfflineError)) throw e;
        this.items.unshift(item); await this.save(item);
        return null;
      }
    },
    async flush() {
      if (this.flushing) return;
      this.flushing = true;
      try {
        for (const item of this.items.filter((i) => !i.protocolo && !i.erro)) {
          try {
            item.protocolo = await this.post(item); await this.save(item);
            toast((item.kind === 'visita' ? 'Visita pendente enviada. Inspeção: ' : 'Relato pendente enviado. Protocolo: ') + item.protocolo);
          } catch (e) {
            if (e instanceof OfflineError) break;
            if (e instanceof ApiError) { item.erro = e.display; await this.save(item); } else break;
          }
        }
      } finally { this.flushing = false; }
    },
  };

  // ------------------------------------------------------------------ utilidades
  let toastTimer = null;
  function toast(text) {
    $toast.textContent = text; $toast.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { $toast.hidden = true; }, 6000);
  }
  function dialog({ icon, iconClass, title, text, ok = 'OK', share }) {
    return new Promise((resolve) => {
      $dialog.innerHTML = `${icon ? svg(icon, iconClass) : ''}<h2>${esc(title)}</h2><p>${esc(text)}</p>${share ? `<button class="btn outline" type="button" id="dlgShare" style="margin-bottom:8px">${svg('send')} Compartilhar</button>` : ''}<button class="btn primary" type="button" id="dlgOk">${esc(ok)}</button>`;
      $dialog.querySelector('#dlgOk').onclick = () => { $dialog.close(); resolve(); };
      if (share) $dialog.querySelector('#dlgShare').onclick = () => window.ijaShare && window.ijaShare({ text: share });
      $dialog.showModal();
    });
  }
  const digits = (s) => String(s || '').replace(/\D/g, '');
  const MASKS = { cpf: ['000.000.000-00'], telefone: ['(00) 0000-0000', '(00) 00000-0000'], cep: ['00000-000'] };
  function applyMask(value, masks) {
    const slots = (m) => (m.match(/0/g) || []).length;
    let d = digits(value); const max = slots(masks[masks.length - 1]);
    if (d.length > max) d = d.slice(0, max);
    const mask = masks.find((m) => slots(m) >= d.length) || masks[masks.length - 1];
    let out = '', i = 0;
    for (const c of mask) { if (i >= d.length) break; out += c === '0' ? d[i++] : c; }
    return out;
  }
  function cpfValido(s) {
    const d = digits(s);
    if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
    const dv = (n) => { let soma = 0; for (let i = 0; i < n; i++) soma += Number(d[i]) * (n + 1 - i); const r = (soma * 10) % 11; return r === 10 ? 0 : r; };
    return dv(9) === Number(d[9]) && dv(10) === Number(d[10]);
  }
  const pad = (n) => String(n).padStart(2, '0');
  const fmtData = (iso) => { if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso.split('-').reverse().join('/'); const d = new Date(iso); return isNaN(d) ? '' : `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`; };
  const fmtDataHora = (iso) => { const d = new Date(iso); return isNaN(d) ? '' : `${fmtData(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const fmtCurta = (iso) => { const d = new Date(iso); return isNaN(d) ? '' : `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const hoje = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const addDias = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  function haversine(a, b) {
    const R = 6371000, rad = Math.PI / 180;
    const dLat = (b[0] - a[0]) * rad, dLng = (b[1] - a[1]) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  const fmtDist = (m) => (m == null ? '—' : m < 1000 ? Math.round(m) + ' m' : (m / 1000).toFixed(1) + ' km');

  // Geolocalização (posição atual; mensagens iguais ao app)
  function currentPosition() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error('Localização não disponível neste aparelho.'));
      navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(
        e.code === 1 ? 'Permissão de localização negada.' : 'Não foi possível obter a localização. Tente novamente ao ar livre.')),
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    });
  }
  const UFS = { acre: 'AC', alagoas: 'AL', 'amapá': 'AP', amazonas: 'AM', bahia: 'BA', 'ceará': 'CE', 'distrito federal': 'DF', 'espírito santo': 'ES', 'goiás': 'GO', 'maranhão': 'MA', 'mato grosso': 'MT', 'mato grosso do sul': 'MS', 'minas gerais': 'MG', 'pará': 'PA', 'paraíba': 'PB', 'paraná': 'PR', pernambuco: 'PE', 'piauí': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN', 'rio grande do sul': 'RS', 'rondônia': 'RO', roraima: 'RR', 'santa catarina': 'SC', 'são paulo': 'SP', sergipe: 'SE', tocantins: 'TO' };
  // Endereço a partir da coordenada: primeiro o servidor do IJA, depois Nominatim. null se nada der certo.
  async function reverseGeocode(lat, lng) {
    const keys = ['cep', 'logradouro', 'numero', 'bairro', 'cidade', 'uf', 'place_id'];
    try {
      const r = await api.post('/portal-cidadao/reverse-geocode', { latitude: String(lat), longitude: String(lng) }, null, 8000);
      if (r.ok) return Object.fromEntries(keys.map((k) => [k, String(r[k] || '')]));
    } catch (e) { /* tenta o Nominatim */ }
    try {
      const resp = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1`,
        { signal: AbortSignal.timeout ? AbortSignal.timeout(8000) : undefined });
      const a = (await resp.json()).address || {};
      const pick = (ks) => ks.map((k) => String(a[k] || '')).find((v) => v) || '';
      const iso = String(a['ISO3166-2-lvl4'] || '');
      return { cep: pick(['postcode']), logradouro: pick(['road']), numero: pick(['house_number']),
        bairro: pick(['suburb', 'neighbourhood', 'district']), cidade: pick(['city', 'town', 'village']),
        uf: iso.startsWith('BR-') ? iso.slice(3) : (UFS[pick(['state']).toLowerCase()] || ''), place_id: '' };
    } catch (e) { return null; }
  }
  // Consulta o ViaCEP; null sem rede, em erro ou após 6 s.
  async function consultaCep(cep8) {
    if (navigator.onLine === false || window.__forceOffline) return null;
    try {
      const r = await fetch(`https://viacep.com.br/ws/${cep8}/json/`, { signal: AbortSignal.timeout ? AbortSignal.timeout(6000) : undefined });
      const j = await r.json();
      return r.ok && j && !j.erro ? j : null;
    } catch (e) { return null; }
  }

  // ------------------------------------------------------------------ componentes de formulário
  function field(o) {
    const req = o.required !== false;
    const label = `<span class="fld-label">${esc(o.label)}${req ? ' <b class="req">*</b>' : ''}</span>`;
    const attrs = `name="${o.name}" ${req ? 'data-required' : ''} ${o.validate ? `data-validate="${o.validate}"` : ''} ${o.mask ? `data-mask="${o.mask}"` : ''} ` +
      `${o.inputmode ? `inputmode="${o.inputmode}"` : ''} ${o.hint ? `placeholder="${esc(o.hint)}"` : ''} ${o.min ? `min="${o.min}"` : ''} ${o.max ? `max="${o.max}"` : ''} ${o.autocomplete ? `autocomplete="${o.autocomplete}"` : 'autocomplete="off"'} ${o.disabled ? 'disabled' : ''}`;
    let control;
    if (o.rows) control = `<textarea ${attrs} rows="${o.rows}">${esc(o.value || '')}</textarea>`;
    else if (o.options) control = `<select ${attrs}><option value="">${esc(o.placeholder || 'Selecione uma opção')}</option>${o.options.map((v) => `<option value="${esc(v)}" ${v === o.value ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>`;
    else control = `<input type="${o.type || 'text'}" ${attrs} value="${esc(o.value || '')}">`;
    return `<label class="fld ${o.lead ? 'has-icon' : ''} ${o.cls || ''}" data-field="${o.name}">${label}${o.lead ? svg(o.lead, 'lead') : ''}${control}${o.trail ? svg(o.trail, 'trail') : ''}<span class="fld-err"></span></label>`;
  }
  const checkbox = (name, text) => `<label class="check" data-field="${name}"><input type="checkbox" name="${name}" data-required><span>${esc(text)} <b class="req">*</b><span class="fld-err">Obrigatório</span></span></label>`;
  const noteReq = '<p class="note-req">* campos obrigatórios</p>';
  function wire(root) {
    root.querySelectorAll('[data-mask]').forEach((el) => el.addEventListener('input', () => { el.value = applyMask(el.value, MASKS[el.dataset.mask]); }));
    root.addEventListener('input', (e) => { const w = e.target.closest && e.target.closest('.fld, .check'); if (w) w.classList.remove('invalid'); });
    root.addEventListener('change', (e) => { const w = e.target.closest && e.target.closest('.fld, .check'); if (w) w.classList.remove('invalid'); });
  }
  // Marca vazios/inválidos com "Obrigatório" e rola até o primeiro. true se tudo ok.
  function validate(root) {
    let first = null;
    root.querySelectorAll('[data-required], [data-validate]').forEach((el) => {
      const wrap = el.closest('.fld, .check'); if (!wrap || !wrap.offsetParent) return; // ignora campos ocultos
      const value = el.type === 'checkbox' ? (el.checked ? 'x' : '') : el.value.trim();
      let msg = '';
      if (el.hasAttribute('data-required') && !value) msg = 'Obrigatório';
      else if (value && el.dataset.validate === 'cpf' && !cpfValido(value)) msg = 'CPF inválido. Confira os 11 dígitos.';
      else if (value && el.dataset.validate === 'telefone' && ![10, 11].includes(digits(value).length)) msg = 'Telefone com DDD (10 ou 11 dígitos).';
      else if (el.dataset.validate === 'int' && !/^-?\d+$/.test(value)) msg = 'Informe um número inteiro';
      wrap.classList.toggle('invalid', !!msg);
      const err = wrap.querySelector('.fld-err'); if (err && el.type !== 'checkbox') err.textContent = msg;
      if (msg && !first) first = wrap;
    });
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return !first;
  }
  const val = (root, name) => { const el = root.querySelector(`[name="${name}"]`); return el ? el.value.trim() : ''; };
  const setVal = (root, name, v) => { const el = root.querySelector(`[name="${name}"]`); if (el) el.value = v; };
  function bar(title, { back = 'inicio', actions = '', flat = false } = {}) {
    return `<header class="bar ${flat ? 'flat' : ''}"><button class="iconbtn" type="button" data-go="${back}" aria-label="Voltar">${svg('back')}</button><h1>${esc(title)}</h1>${actions}</header>`;
  }
  const locCard = (pos, status) => `<div class="card softer loc ${pos ? 'ok' : ''}">${svg(pos ? 'gps' : 'gpsOff')}<div><b>${pos ? pos.coords.latitude.toFixed(5) + ', ' + pos.coords.longitude.toFixed(5) : 'Sem coordenadas'}</b><span>${esc(status || '')}</span></div></div>`;
  function readFiles(input, limit, current) {
    const files = Array.from(input.files || []).filter((f) => f.type.startsWith('image/'));
    const room = limit - current.length;
    input.value = '';
    return files.slice(0, Math.max(room, 0));
  }
  const fileUrl = (f) => URL.createObjectURL(f);

  // ------------------------------------------------------------------ roteador
  let cleanup = null;
  const go = (hash) => { if (location.hash === '#' + hash) render(); else location.hash = hash; };
  const routes = { '': home, inicio: home, 'relatar-foco': foco, 'caso-suspeito': caso, alertas, chat, agente, enviados };
  function render() {
    const parts = location.hash.replace(/^#/, '').split('/');
    if (cleanup) { try { cleanup(); } catch (e) { /* nada */ } cleanup = null; }
    window.scrollTo(0, 0);
    const view = routes[parts[0]] || home;
    cleanup = view(parts.slice(1)) || null;
  }
  $app.addEventListener('click', (e) => {
    const b = e.target.closest('[data-go]'); if (b) go(b.dataset.go);
  });
  window.addEventListener('hashchange', render);

  // ------------------------------------------------------------------ configuração
  async function loadConfig() {
    try {
      state.config = await api.get('/api/mobile/config'); state.configError = null; store.set('config', state.config);
      if (state.prefeituraId == null && prefeituras().length === 1) setPrefeitura(prefeituras()[0].id);
    } catch (e) { state.configError = e.message; }
    document.dispatchEvent(new CustomEvent('config'));
  }

  // ------------------------------------------------------------------ Início
  function home() {
    const draw = () => {
      const has = state.prefeituraId != null && prefeituras().some((p) => p.id === state.prefeituraId);
      const pend = outbox.pendingCount();
      const card = (hash, icon, title, sub, needs) => `<button class="home-card ${needs && !has ? 'disabled' : ''}" type="button" data-card="${hash}" ${needs ? 'data-needs' : ''}><span class="ic">${svg(icon)}</span><span class="tx"><b>${title}</b><span>${sub}</span></span>${svg('chevron', 'chev')}</button>`;
      $app.innerHTML = `
        <section class="hero">
          <div class="hero-logo"><img src="/static/img/logo_oceano_azul_light.png" alt="Oceano Azul"></div>
          <h1>IJA Vigilância</h1>
          <p>Combate ao Aedes com a participação de todos.</p>
          <label for="municipio">Município</label>
          <div class="select">${svg('city')}<select id="municipio">
            <option value="" disabled ${has ? '' : 'selected'}>${prefeituras().length ? 'Escolha o município' : 'Carregando municípios…'}</option>
            ${prefeituras().map((p) => `<option value="${p.id}" ${p.id === state.prefeituraId ? 'selected' : ''}>${esc(p.nome)}</option>`).join('')}
          </select></div>
        </section>
        <main class="page home">
          ${navigator.onLine === false ? `<div class="card offline-banner">${svg('wifiOff')} Sem internet: você pode continuar e os relatos serão enviados depois.</div>` : ''}
          ${state.configError && !state.config ? `<div class="card item" style="background:#fff4ec">${svg('wifiOff', 'icon-warn')}<div class="tx"><b style="font-size:16px">Não foi possível carregar a configuração.</b><small>${esc(state.configError)}</small></div><button class="iconbtn" type="button" id="retryConfig" aria-label="Tentar de novo">${svg('refresh', 'icon-primary')}</button></div>` : ''}
          ${card('relatar-foco', 'bug', 'Relatar foco', 'Água parada, terreno sujo, caixa-d\'água aberta…', true)}
          ${card('caso-suspeito', 'sick', 'Relatar caso suspeito', 'Febre, manchas, dor no corpo: avise a vigilância.', true)}
          ${card('alertas', 'campaign', 'Alertas', 'Avisos recentes do seu município.', true)}
          ${card('chat', 'chat', 'Fale com a Azul', 'Tire dúvidas sobre dengue, zika e chikungunya.', false)}
          ${card('agente', 'badge', 'Sou agente de endemias', 'Área restrita: jornada de campo.', false)}
          <button class="btn outline mt" type="button" data-go="enviados">${svg('history')} ${pend > 0 ? `Enviados / pendentes (${pend} pendente(s))` : 'Enviados / pendentes'}</button>
          <div class="card item mt" style="align-items:center"><div class="tx"><b>Convide sua vizinhança</b><span class="muted small">Quanto mais gente relatando, mais rápido os focos são eliminados.</span></div><button class="btn outline sm" type="button" id="btnConvite" style="width:auto">${svg('send')} Compartilhar</button></div>
          <p class="footer">Oceano Azul · IJA Drones</p>
        </main>`;
      $app.querySelector('#municipio').addEventListener('change', (e) => { setPrefeitura(Number(e.target.value)); draw(); });
      const conv = $app.querySelector('#btnConvite'); if (conv) conv.addEventListener('click', () => window.ijaShare && window.ijaShare({ text: window.ijaShareTexts.app(nomePrefeitura(state.prefeituraId)) }));
      $app.querySelectorAll('[data-card]').forEach((b) => b.addEventListener('click', () => {
        if (b.hasAttribute('data-needs') && !has) { toast('Escolha o município primeiro.'); return; }
        go(b.dataset.card);
      }));
      const retry = $app.querySelector('#retryConfig'); if (retry) retry.addEventListener('click', loadConfig);
    };
    draw();
    document.addEventListener('config', draw); document.addEventListener('outbox', draw);
    window.addEventListener('online', draw); window.addEventListener('offline', draw);
    return () => { document.removeEventListener('config', draw); document.removeEventListener('outbox', draw); window.removeEventListener('online', draw); window.removeEventListener('offline', draw); };
  }

  // ------------------------------------------------------------------ Relatar foco
  function foco() {
    const cat = catalogo();
    const tipos = cat.tipo_visita_opcoes || ['Aedes', 'Culex', 'Outro'];
    const imoveis = cat.tipo_imovel_opcoes || [];
    const outroLabel = cat.tipo_visita_outro_label || 'Outro';
    let tipo = null, pos = null, placeId = '', fromGps = false, locating = false, sending = false;
    const fotos = []; const manual = new Set();
    const focos = (imovel) => tipo === 'Aedes' ? (imovel ? ((cat.aedes || {})[imovel] || []) : []) : tipo === 'Culex' ? (cat.culex || []) : tipo === 'Outro' ? (cat.outro || []) : [];
    $app.innerHTML = `${bar('Relatar foco')}
      <main class="page"><form id="f" novalidate>
        ${noteReq}
        <p class="section" id="tipoTitle" style="margin-top:12px">O que você encontrou? <b class="req">*</b></p>
        <div class="chips" id="tipos">${tipos.map((t) => `<button class="chip" type="button" data-tipo="${esc(t)}">${esc(t === 'Outro' ? outroLabel : t)}</button>`).join('')}</div>
        <div id="imovelWrap" class="mt" hidden>${field({ name: 'tipo_imovel', label: 'Tipo de imóvel', options: imoveis, placeholder: 'Selecione uma opção' })}</div>
        <div class="mt">${field({ name: 'foco', label: 'Foco encontrado', options: [], placeholder: 'Escolha os campos anteriores', disabled: true })}</div>
        ${field({ name: 'descricao', label: 'Descrição (opcional)', required: false, rows: 3, hint: 'Conte o que viu no local' })}
        <p class="section">Fotos (até 5)</p>
        <div class="row">
          <button class="btn outline" type="button" id="btnCam">${svg('camera')} Câmera</button>
          <button class="btn outline" type="button" id="btnGal">${svg('gallery')} Galeria</button>
        </div>
        <input type="file" id="inCam" accept="image/*" capture="environment" hidden>
        <input type="file" id="inGal" accept="image/*" multiple hidden>
        <div class="thumbs" id="thumbs"></div>
        <p class="section">Onde fica?</p>
        <div id="loc">${locCard(null, 'Obtendo localização…')}</div>
        <button class="btn outline" type="button" id="btnLoc">${svg('gps')} <span>Atualizar pela localização</span></button>
        <p class="hint-gps" id="gpsHint" hidden>Endereço sugerido pela sua localização — confira.</p>
        <div class="mt">${field({ name: 'cep', label: 'CEP (opcional)', required: false, hint: '00000-000', mask: 'cep', inputmode: 'numeric', trail: 'search' })}</div>
        ${field({ name: 'logradouro', label: 'Rua / logradouro' })}
        <div class="row">${field({ name: 'numero', label: 'Número', inputmode: 'numeric' })}<div class="w2">${field({ name: 'complemento', label: 'Complemento', required: false })}</div></div>
        ${field({ name: 'bairro', label: 'Bairro' })}
        <div class="row"><div class="w2">${field({ name: 'cidade', label: 'Cidade', value: nomePrefeitura(state.prefeituraId) })}</div>${field({ name: 'uf', label: 'UF', value: 'PE' })}</div>
        <p class="section">Seus dados</p>
        ${field({ name: 'nome', label: 'Nome completo', autocomplete: 'name' })}
        ${field({ name: 'cpf', label: 'CPF', mask: 'cpf', validate: 'cpf', inputmode: 'numeric' })}
        ${field({ name: 'rg', label: 'RG' })}
        ${field({ name: 'telefone', label: 'Telefone (com DDD)', mask: 'telefone', validate: 'telefone', inputmode: 'tel', type: 'tel', autocomplete: 'tel' })}
        ${checkbox('consentimento', 'Autorizo o uso destes dados pela vigilância do município apenas para triagem e retorno deste relato (LGPD).')}
        <button class="btn portal mt" type="submit" id="btnSend">${svg('send')} <span>Enviar relato</span></button>
      </form></main>`;
    const form = $app.querySelector('#f'); wire(form);
    const focoSel = form.querySelector('[name="foco"]'), imovelSel = form.querySelector('[name="tipo_imovel"]');
    form.querySelectorAll('input, textarea').forEach((el) => el.addEventListener('input', () => manual.add(el.name)));
    function renderFocos() {
      const list = focos(imovelSel.value);
      focoSel.innerHTML = `<option value="">${list.length ? 'Selecione uma opção' : 'Escolha os campos anteriores'}</option>` + list.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
      focoSel.disabled = list.length === 0;
    }
    form.querySelector('#tipos').addEventListener('click', (e) => {
      const b = e.target.closest('[data-tipo]'); if (!b) return;
      tipo = b.dataset.tipo;
      form.querySelectorAll('[data-tipo]').forEach((x) => x.classList.toggle('on', x === b));
      form.querySelector('#imovelWrap').hidden = tipo !== 'Aedes';
      imovelSel.value = ''; imovelSel.toggleAttribute('data-required', tipo === 'Aedes');
      form.querySelector('#tipoTitle').classList.remove('error');
      renderFocos();
    });
    imovelSel.addEventListener('change', renderFocos);
    // fotos
    const thumbs = form.querySelector('#thumbs');
    function drawThumbs() {
      thumbs.innerHTML = fotos.map((f, i) => `<div class="thumb"><img src="${fileUrl(f)}" alt=""><button type="button" data-rm="${i}" aria-label="Remover foto">${svg('close')}</button></div>`).join('');
      form.querySelector('#btnCam').disabled = form.querySelector('#btnGal').disabled = fotos.length >= 5;
    }
    thumbs.addEventListener('click', (e) => { const b = e.target.closest('[data-rm]'); if (b) { fotos.splice(Number(b.dataset.rm), 1); drawThumbs(); } });
    form.querySelector('#btnCam').addEventListener('click', () => form.querySelector('#inCam').click());
    form.querySelector('#btnGal').addEventListener('click', () => form.querySelector('#inGal').click());
    ['#inCam', '#inGal'].forEach((id) => form.querySelector(id).addEventListener('change', (e) => { fotos.push(...readFiles(e.target, 5, fotos)); drawThumbs(); }));
    // localização
    const fill = (e) => { let changed = false; for (const k of ['cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf']) { if (e[k] && !val(form, k)) { setVal(form, k, k === 'cep' ? applyMask(e[k], MASKS.cep) : e[k]); changed = true; } } return changed; };
    async function updateLocation() {
      locating = true; form.querySelector('#btnLoc').disabled = true; form.querySelector('#btnLoc span').textContent = 'Localizando…';
      form.querySelector('#loc').innerHTML = locCard(pos, 'Obtendo localização…');
      try {
        pos = await currentPosition();
        const prec = `Localização obtida (precisão ${Math.round(pos.coords.accuracy)} m)`;
        form.querySelector('#loc').innerHTML = locCard(pos, prec + '. Buscando endereço…');
        const e = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        form.querySelector('#loc').innerHTML = locCard(pos, prec);
        if (e) { placeId = e.place_id || ''; fromGps = fill(e) || fromGps; form.querySelector('#gpsHint').hidden = !fromGps; }
      } catch (e) { form.querySelector('#loc').innerHTML = locCard(pos, e.message); }
      locating = false; form.querySelector('#btnLoc').disabled = false; form.querySelector('#btnLoc span').textContent = 'Atualizar pela localização';
    }
    form.querySelector('#btnLoc').addEventListener('click', () => { if (!locating) updateLocation(); });
    updateLocation();
    // CEP → ViaCEP
    let ultimoCep = '';
    form.querySelector('[name="cep"]').addEventListener('input', async (e) => {
      const d = digits(e.target.value); if (d.length !== 8 || d === ultimoCep) return;
      ultimoCep = d;
      const r = await consultaCep(d); if (!r) return;
      for (const [k, src] of Object.entries({ logradouro: 'logradouro', bairro: 'bairro', cidade: 'localidade', uf: 'uf' })) {
        const v = String(r[src] || ''); if (v && (!val(form, k) || !manual.has(k))) setVal(form, k, v);
      }
    });
    // envio
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); if (sending) return;
      const ok = validate(form);
      if (!tipo) form.querySelector('#tipoTitle').classList.add('error');
      if (!ok || !tipo) {
        if (!tipo) form.querySelector('#tipoTitle').scrollIntoView({ behavior: 'smooth', block: 'center' });
        const only = form.querySelectorAll('.invalid');
        toast(tipo && only.length === 1 && only[0].classList.contains('check') ? 'É preciso autorizar o uso dos dados para a triagem.' : 'Preencha os campos obrigatórios destacados.');
        return;
      }
      sending = true; form.querySelector('#btnSend').disabled = true; form.querySelector('#btnSend span').textContent = 'Enviando…';
      const fields = { prefeitura_id: state.prefeituraId, tipo_visita: tipo, tipo_imovel: tipo === 'Aedes' ? val(form, 'tipo_imovel') : '', foco: val(form, 'foco') };
      for (const k of ['descricao', 'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'nome', 'cpf', 'rg', 'telefone']) fields[k] = val(form, k);
      Object.assign(fields, { latitude: pos ? String(pos.coords.latitude) : '', longitude: pos ? String(pos.coords.longitude) : '', place_id: placeId, consentimento: 'on' });
      try {
        const protocolo = await outbox.send('foco', fields, fotos.slice());
        await dialog(protocolo ? { icon: 'check', iconClass: 'icon-ok', title: 'Relato enviado', text: `Obrigado! Seu protocolo é ${protocolo}. Guarde este número para acompanhar.`, share: window.ijaShareTexts && window.ijaShareTexts.foco(nomePrefeitura(state.prefeituraId)) }
          : { icon: 'cloudOff', iconClass: 'icon-warn', title: 'Salvo no aparelho', text: 'Sem internet agora. O relato foi salvo no aparelho e será enviado automaticamente quando houver conexão.' });
        go('inicio');
      } catch (err) {
        sending = false; form.querySelector('#btnSend').disabled = false; form.querySelector('#btnSend span').textContent = 'Enviar relato';
        toast(err instanceof ApiError ? err.display : 'Falha ao enviar: ' + err.message);
      }
    });
  }

  // ------------------------------------------------------------------ Relatar caso suspeito
  function caso() {
    let sending = false, locating = false; const manual = new Set();
    $app.innerHTML = `${bar('Relatar caso suspeito')}
      <main class="page"><form id="f" novalidate>
        <p class="muted" style="margin:12px 0 0">Suspeita de dengue, zika ou chikungunya? Informe para a vigilância em saúde do seu município agir no bairro.</p>
        ${noteReq}
        <p class="section">Quem está com sintomas</p>
        ${field({ name: 'nome', label: 'Nome completo', autocomplete: 'name' })}
        ${field({ name: 'telefone', label: 'Telefone (com DDD)', mask: 'telefone', validate: 'telefone', type: 'tel', inputmode: 'tel', autocomplete: 'tel' })}
        <p class="section">Endereço</p>
        ${field({ name: 'cep', label: 'CEP (opcional, preenche o endereço)', required: false, hint: '00000-000', mask: 'cep', inputmode: 'numeric', trail: 'search' })}
        ${field({ name: 'logradouro', label: 'Rua / logradouro' })}
        ${field({ name: 'numero', label: 'Número', inputmode: 'numeric' })}
        ${field({ name: 'bairro', label: 'Bairro' })}
        <button class="btn outline" type="button" id="btnLoc">${svg('gps')} <span>Atualizar pela localização</span></button>
        <p class="hint-gps" id="locStatus" hidden></p>
        <p class="section">Sintomas</p>
        ${field({ name: 'descricao', label: 'Descreva os sintomas', rows: 3 })}
        ${field({ name: 'inicio_sintomas', label: 'Início dos sintomas (opcional)', required: false, type: 'date', min: addDias(-60), max: hoje(), lead: 'event' })}
        ${checkbox('consentimento', 'Autorizo o uso destes dados pela vigilância em saúde do município apenas para triagem e contato (LGPD).')}
        <button class="btn portal mt" type="submit" id="btnSend">${svg('send')} <span>Enviar relato</span></button>
      </form></main>`;
    const form = $app.querySelector('#f'); wire(form);
    form.querySelectorAll('input, textarea').forEach((el) => el.addEventListener('input', () => manual.add(el.name)));
    const status = form.querySelector('#locStatus');
    async function updateLocation() {
      locating = true; form.querySelector('#btnLoc').disabled = true; form.querySelector('#btnLoc span').textContent = 'Localizando…';
      try {
        const p = await currentPosition();
        const e = await reverseGeocode(p.coords.latitude, p.coords.longitude);
        if (!e) { status.textContent = 'Localização obtida; endereço não encontrado.'; status.hidden = false; }
        else {
          let changed = false;
          for (const k of ['logradouro', 'numero', 'bairro']) if (e[k] && !val(form, k)) { setVal(form, k, e[k]); changed = true; }
          if (changed) { status.textContent = 'Endereço sugerido pela sua localização — confira.'; status.hidden = false; }
        }
      } catch (e) { status.textContent = e.message; status.hidden = false; }
      locating = false; form.querySelector('#btnLoc').disabled = false; form.querySelector('#btnLoc span').textContent = 'Atualizar pela localização';
    }
    form.querySelector('#btnLoc').addEventListener('click', () => { if (!locating) updateLocation(); });
    updateLocation();
    let ultimoCep = '';
    form.querySelector('[name="cep"]').addEventListener('input', async (e) => {
      const d = digits(e.target.value); if (d.length !== 8 || d === ultimoCep) return;
      ultimoCep = d; const r = await consultaCep(d); if (!r) return;
      for (const k of ['logradouro', 'bairro']) { const v = String(r[k] || ''); if (v && (!val(form, k) || !manual.has(k))) setVal(form, k, v); }
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); if (sending) return;
      if (!validate(form)) {
        const only = form.querySelectorAll('.invalid');
        toast(only.length === 1 && only[0].classList.contains('check') ? 'É preciso autorizar o uso dos dados para a triagem.' : 'Preencha os campos obrigatórios destacados.');
        return;
      }
      sending = true; form.querySelector('#btnSend').disabled = true; form.querySelector('#btnSend span').textContent = 'Enviando…';
      const fields = { prefeitura_id: state.prefeituraId, consentimento: true, dispositivo: state.deviceId };
      for (const k of ['nome', 'telefone', 'logradouro', 'numero', 'bairro', 'descricao']) fields[k] = val(form, k);
      if (val(form, 'inicio_sintomas')) fields.inicio_sintomas = val(form, 'inicio_sintomas');
      try {
        const protocolo = await outbox.send('caso', fields, []);
        await dialog(protocolo ? { icon: 'check', iconClass: 'icon-ok', title: 'Relato enviado', text: `Obrigado! Seu protocolo é ${protocolo}. A equipe de saúde poderá entrar em contato.`, share: window.ijaShareTexts && window.ijaShareTexts.caso() }
          : { icon: 'cloudOff', iconClass: 'icon-warn', title: 'Salvo no aparelho', text: 'Sem internet agora. O relato foi salvo no aparelho e será enviado automaticamente quando houver conexão.' });
        go('inicio');
      } catch (err) {
        sending = false; form.querySelector('#btnSend').disabled = false; form.querySelector('#btnSend span').textContent = 'Enviar relato';
        toast(err instanceof ApiError ? err.display : 'Falha ao enviar: ' + err.message);
      }
    });
  }

  // ------------------------------------------------------------------ Alertas (lista + Web Push)
  const push = {
    supported: () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
    key(base64) { const pad = '='.repeat((4 - base64.length % 4) % 4); const raw = atob((base64 + pad).replace(/-/g, '+').replace(/_/g, '/')); return Uint8Array.from(raw, (c) => c.charCodeAt(0)); },
    position() { return new Promise((resolve) => { if (!navigator.geolocation) return resolve({}); navigator.geolocation.getCurrentPosition((p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }), () => resolve({}), { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }); }); },
    async registration() { const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' }); await navigator.serviceWorker.ready; return reg; },
    async enable() {
      if (!this.supported()) throw new Error('Este aparelho não suporta notificações neste modo. Abra pelo ícone instalado na tela inicial.');
      const { publicKey } = await api.get('/api/push/chave-publica');
      if (!publicKey) throw new Error('Alertas push ainda não configurados no servidor.');
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error(permission === 'denied' ? 'Notificações bloqueadas neste aparelho. Libere em Ajustes → Notificações e tente de novo.' : 'Permissão de notificação não concedida.');
      const reg = await this.registration();
      const sub = (await reg.pushManager.getSubscription()) || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: this.key(publicKey) }));
      const where = await this.position();
      await api.post('/api/push/inscrever', { canal: 'webpush', subscription: sub.toJSON(), ...where, prefeitura_id: state.prefeituraId || undefined });
      store.set('ija-push', 1);
      return where;
    },
    async disable() {
      const reg = await navigator.serviceWorker.getRegistration('/');
      const sub = reg && (await reg.pushManager.getSubscription());
      if (sub) { await api.post('/api/push/remover', { token: sub.endpoint }).catch(() => {}); await sub.unsubscribe(); }
      store.del('ija-push');
    },
    async subscribed() {
      if (!this.supported() || Notification.permission !== 'granted') return false;
      try { const reg = await navigator.serviceWorker.getRegistration('/'); return !!(reg && (await reg.pushManager.getSubscription())); } catch (e) { return false; }
    },
  };
  function alertas() {
    $app.innerHTML = `${bar('Alertas · ' + nomePrefeitura(state.prefeituraId))}
      <main class="page">
        <button class="btn portal" type="button" id="btnPush" style="margin-top:8px">${svg('bell')} <span>Receber alertas no celular</span></button>
        <button class="btn text" type="button" id="btnPushOff" hidden>Desativar alertas neste aparelho</button>
        <p class="push-status" id="pushStatus"></p>
        <p class="muted small">Prefere o Telegram? <a href="${esc((state.config && state.config.telegram) || 'https://t.me/ija_vigilancia_bot')}" target="_blank" rel="noopener">Falar com a Azul no Telegram</a></p>
        <div id="lista" class="mt"><p class="center muted">Carregando…</p></div>
      </main>`;
    const btn = $app.querySelector('#btnPush'), off = $app.querySelector('#btnPushOff'), st = $app.querySelector('#pushStatus'), lista = $app.querySelector('#lista');
    const say = (t, kind) => { st.textContent = t || ''; st.dataset.kind = kind || ''; };
    const showOn = (where) => { btn.querySelector('span').textContent = 'Alertas ativados'; btn.disabled = true; off.hidden = false; say(where && where.latitude ? 'Alertas ativados para a sua localização. Você será avisado quando houver aumento de focos ou casos perto de você.' : 'Alertas ativados para o município.', 'ok'); };
    const showOff = (t) => { btn.querySelector('span').textContent = 'Receber alertas no celular'; btn.disabled = false; off.hidden = true; if (t) say(t); };
    (async () => {
      if (!push.supported()) { say('Este aparelho não suporta notificações neste modo.'); return; }
      if (Notification.permission === 'denied') { say('Notificações bloqueadas neste aparelho. Libere em Ajustes do site para receber alertas.', 'error'); return; }
      if (await push.subscribed()) showOn(null);
    })();
    btn.addEventListener('click', async () => {
      btn.disabled = true; btn.querySelector('span').textContent = 'Ativando…'; say('Ativando…');
      try { showOn(await push.enable()); await dialog({ title: 'Alertas no celular', text: 'Pronto! Você receberá os alertas do município neste celular.' }); }
      catch (e) { showOff(); say(e.message, 'error'); await dialog({ title: 'Alertas no celular', text: e.message }); }
    });
    off.addEventListener('click', async () => { off.disabled = true; try { await push.disable(); showOff('Alertas desativados neste aparelho.'); } finally { off.disabled = false; } });
    (async () => {
      try {
        const r = await api.get('/api/mobile/alertas?prefeitura_id=' + encodeURIComponent(state.prefeituraId));
        const list = r.alertas || [];
        lista.innerHTML = list.length ? list.map((a, i) => `<div class="card item">${svg('warning', 'icon-warn')}<div class="tx"><b>${esc(a.titulo || 'Alerta')}</b><p>${esc(a.mensagem || '')}</p><small>${[a.bairro ? 'Bairro ' + a.bairro : '', a.quando ? fmtDataHora(a.quando) : ''].filter(Boolean).join(' · ')}</small><button class="btn text sm share-alert" type="button" data-i="${i}" style="min-height:36px;padding:0;justify-content:flex-start">${svg('send')} Compartilhar</button></div></div>`).join('')
          : '<p class="center">Nenhum alerta recente para este município.</p>';
        lista.querySelectorAll('.share-alert').forEach((b) => b.addEventListener('click', () => { const a = list[Number(b.dataset.i)]; window.ijaShare && window.ijaShare({ text: window.ijaShareTexts.alerta(nomePrefeitura(state.prefeituraId), a.titulo || 'Alerta', a.mensagem) }); }));
      } catch (e) { lista.innerHTML = `<p class="center">Não foi possível carregar os alertas.<br>${esc(e.message)}</p>`; }
    })();
  }

  // ------------------------------------------------------------------ Fale com a Azul
  function chat() {
    const msgs = [{ role: 'assistant', content: 'Olá! Eu sou a Azul. Posso ajudar com dúvidas sobre dengue, zika, chikungunya e como evitar focos do mosquito.', error: false }];
    let sending = false;
    const tg = (state.config && state.config.telegram) || 'https://t.me/ija_vigilancia_bot';
    $app.innerHTML = `${bar('Fale com a Azul')}
      <div class="chat"><a class="btn outline sm tg-link" href="${esc(tg)}" target="_blank" rel="noopener">${svg('send')} Abrir no Telegram</a><div class="msgs" id="msgs"></div>
      <form class="composer" id="composer"><input type="text" id="msg" placeholder="Digite sua pergunta" autocomplete="off" enterkeyhint="send"><button type="submit" aria-label="Enviar">${svg('send')}</button></form></div>`;
    const box = $app.querySelector('#msgs'), input = $app.querySelector('#msg');
    const draw = () => {
      box.innerHTML = msgs.map((m) => `<div class="bubble ${m.error ? 'err' : m.role === 'user' ? 'me' : 'bot'}">${esc(m.content)}</div>`).join('') + (sending ? '<p class="typing">Azul está digitando…</p>' : '');
      window.scrollTo(0, document.body.scrollHeight);
    };
    draw();
    $app.querySelector('#composer').addEventListener('submit', async (e) => {
      e.preventDefault(); const text = input.value.trim(); if (!text || sending) return;
      const history = msgs.filter((m) => !m.error).slice(1).slice(-6).map((m) => ({ role: m.role, content: m.content }));
      msgs.push({ role: 'user', content: text, error: false }); sending = true; input.value = ''; draw();
      try { const r = await api.post('/api/mobile/chat', { message: text, history, dispositivo: state.deviceId }, null, 60000); msgs.push({ role: 'assistant', content: String(r.answer || ''), error: false }); }
      catch (err) { msgs.push({ role: 'assistant', content: err.message, error: true }); }
      sending = false; draw();
    });
  }

  // ------------------------------------------------------------------ Agente de endemias
  let agentPos = null;
  const journey = { watch: null, timer: null, last: null, lastSent: null, sent: 0, lastAt: null, status: null, onChange: null, get active() { return this.watch !== null; } };
  const notify = () => { if (journey.onChange) journey.onChange(); };
  async function journeySend(p) {
    try {
      await api.post('/api/agente/posicao', { latitude: p.coords.latitude, longitude: p.coords.longitude, precisao: p.coords.accuracy, origem: 'app' }, state.token);
      journey.sent++; journey.lastAt = new Date(); journey.lastSent = p;
      journey.status = `Última posição: ${p.coords.latitude.toFixed(5)}, ${p.coords.longitude.toFixed(5)}`;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { journeyStop(); setAgente(null, null); go('agente'); return; }
      journey.status = e instanceof ApiError ? 'Servidor recusou a posição: ' + e.message : 'Sem conexão; tentando de novo em instantes.';
    }
    notify();
  }
  function journeyStart() {
    if (!navigator.geolocation) { journey.status = 'Localização não disponível neste aparelho.'; notify(); return; }
    journey.watch = navigator.geolocation.watchPosition((p) => {
      journey.last = p; agentPos = p;
      const far = !journey.lastSent || haversine([journey.lastSent.coords.latitude, journey.lastSent.coords.longitude], [p.coords.latitude, p.coords.longitude]) >= 25;
      if (far) journeySend(p); else notify();
    }, (e) => { journey.status = e.code === 1 ? 'Permissão de localização negada.' : 'Erro de GPS: ' + e.message; notify(); },
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 });
    journey.timer = setInterval(() => { if (journey.last) journeySend(journey.last); }, 30000);
    journey.status = 'Jornada iniciada. Aguardando GPS…'; notify();
  }
  function journeyStop() {
    if (journey.watch !== null) navigator.geolocation.clearWatch(journey.watch);
    clearInterval(journey.timer); journey.watch = null; journey.timer = null;
    journey.status = 'Jornada encerrada.'; notify();
  }
  async function loadPainel() {
    const r = await api.get('/api/mobile/agente/painel?demo=false', state.token);
    state.painel = r; store.set('agente_painel', r);
    try { state.me = await api.get('/api/mobile/me', state.token); store.set('agente_me', state.me); } catch (e) { /* mantém o último */ }
    return r;
  }
  function agente(rest) {
    if (!state.token) return agenteLogin();
    if (rest[0] === 'visita') return visita(Number(rest[1]));
    if (rest[0] === 'mapa') return mapa();
    return painel();
  }
  function agenteLogin() {
    let busy = false;
    $app.innerHTML = `${bar('Agente de endemias', { flat: true })}
      <main class="page" style="padding:20px"><form id="f" novalidate>
        <p class="section" style="margin-top:12px">Entre com seu usuário do IJA</p>
        ${noteReq}
        <div class="mt2">${field({ name: 'login', label: 'Usuário', lead: 'person', autocomplete: 'username' })}</div>
        ${field({ name: 'senha', label: 'Senha', type: 'password', lead: 'lock', autocomplete: 'current-password' })}
        <p class="error-text" id="erro" hidden></p>
        <button class="btn primary mt2" type="submit" id="btnLogin">Entrar</button>
      </form></main>`;
    const form = $app.querySelector('#f'); wire(form);
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); if (busy || !validate(form)) return;
      busy = true; form.querySelector('#btnLogin').textContent = 'Entrando…'; form.querySelector('#btnLogin').disabled = true; form.querySelector('#erro').hidden = true;
      try {
        const r = await api.post('/api/mobile/login', { login: val(form, 'login'), senha: form.querySelector('[name="senha"]').value });
        setAgente(String(r.token), r.usuario || {}); render();
      } catch (err) {
        form.querySelector('#erro').textContent = err.message; form.querySelector('#erro').hidden = false;
        busy = false; form.querySelector('#btnLogin').textContent = 'Entrar'; form.querySelector('#btnLogin').disabled = false;
      }
    });
  }
  function painel() {
    let erro = null, loading = false;
    const dist = (o) => (agentPos && o.latitude != null && o.longitude != null) ? haversine([agentPos.coords.latitude, agentPos.coords.longitude], [o.latitude, o.longitude]) : null;
    const draw = () => {
      const p = state.painel || {}, ag = state.agente || {}, resumo = p.resumo_hoje || {};
      const quarteiroes = p.quarteiroes || [], alertasAg = p.alertas || [];
      const ocorrencias = (p.ocorrencias || []).slice().sort((a, b) => (dist(a) ?? 1e12) - (dist(b) ?? 1e12));
      const tile = (label, value, icon, small) => `<div class="tile">${svg(icon)}<div><b class="${small ? 'small' : ''}">${esc(value)}</b><span>${label}</span></div></div>`;
      $app.innerHTML = `${bar('Painel do agente', { flat: true, actions: `<button class="iconbtn" type="button" data-go="agente/mapa" ${state.painel ? '' : 'disabled'} aria-label="Mapa do dia">${svg('map')}</button><button class="iconbtn" type="button" id="btnReload" ${loading ? 'disabled' : ''} aria-label="Atualizar">${svg('refresh', loading ? 'spin' : '')}</button><button class="iconbtn" type="button" id="btnLogout" aria-label="Sair">${svg('logout')}</button>` })}
        <main class="page" style="padding-top:16px">
          <div class="card item" style="align-items:center"><div class="avatar">${svg('badge')}</div><div class="tx"><b>${esc(ag.nome || '')}</b><span class="muted">${esc(nomePrefeitura(ag.prefeitura_id))}</span></div></div>
          ${erro ? `<p class="warn-text">${esc(erro)}</p>` : ''}
          <div class="card" id="tgCard">${(state.me && state.me.telegram && state.me.telegram.vinculado)
            ? `<div class="item" style="align-items:center"><div class="avatar" style="background:#e8f8fb;color:#229ED9">${svg('send')}</div><div class="tx"><b>Telegram vinculado</b><span class="muted small">Você recebe os alertas epidemiológicos por lá.</span></div></div>`
            : `<div class="item" style="align-items:center"><div class="avatar" style="background:#e8f8fb;color:#229ED9">${svg('send')}</div><div class="tx"><b>Alertas no Telegram</b><span class="muted small">Abra o link, toque em Iniciar no Telegram e volte aqui.</span></div></div>
               <a class="btn outline mt" href="${esc((state.me && state.me.telegram && state.me.telegram.link) || 'https://t.me/ija_vigilancia_bot')}" target="_blank" rel="noopener" id="btnTelegram">${svg('send')} Receber alertas no Telegram</a>`}</div>
          <div class="row">${tile('Visitas hoje', resumo.visitas ?? 0, 'home')}${tile('Pontos', resumo.posicoes ?? 0, 'route')}</div>
          <div class="row">${tile('Km hoje', resumo.km ?? 0, 'walk')}${tile('Início · último', `${resumo.inicio || '—'} · ${resumo.ultimo || '—'}`, 'schedule', true)}</div>
          <div class="card ${journey.active ? 'active' : ''}" id="jornada">
            <div class="stats"><div><b>${journey.active ? 'ativa' : 'parada'}</b><span>Jornada</span></div><div><b>${journey.sent}</b><span>Pontos enviados</span></div><div><b>${journey.lastAt ? pad(journey.lastAt.getHours()) + ':' + pad(journey.lastAt.getMinutes()) : '—'}</b><span>Último envio</span></div></div>
            ${journey.status ? `<p class="muted small" style="text-align:center;margin:8px 0 0">${esc(journey.status)}</p>` : ''}
            <p class="muted small" style="text-align:center;margin:8px 0 0">No aplicativo instalado pela web, o rastro só é enviado enquanto o app estiver aberto na tela.</p>
            <button class="btn ${journey.active ? 'danger' : 'primary'} mt" type="button" id="btnJornada">${svg(journey.active ? 'stop' : 'play')} ${journey.active ? 'Encerrar jornada' : 'Iniciar jornada'}</button>
          </div>
          <p class="section">Meus quarteirões (${quarteiroes.length})</p>
          ${quarteiroes.length ? '' : '<p class="muted">Nenhum quarteirão atribuído.</p>'}
          ${quarteiroes.map((q, i) => { const feitas = Number(q.visitas_registradas || 0), meta = Number(q.meta || 0), pct = meta ? Math.min(100, feitas / meta * 100) : 0; return `
            <button class="block" type="button" data-go="agente/visita/${i}">
              <div class="ttl"><b>${esc(q.quarteirao)} · ${esc(q.bairro || '')} / ${esc(q.area || '')}</b>${svg('chevron')}</div>
              <div class="muted small">${esc(q.titulo || q.plano)}</div>
              ${q.referencia ? `<div class="small">${esc(q.referencia)}</div>` : ''}
              <div class="progress ${feitas >= meta && meta > 0 ? 'done' : ''}"><i style="width:${pct}%"></i></div>
              <div class="small">${feitas} de ${meta} visitas (meta)</div>
            </button>`; }).join('')}
          <p class="section">Ocorrências abertas perto de mim (${ocorrencias.length})</p>
          ${agentPos ? '' : '<p class="muted small">Sem posição do GPS: lista sem ordenação por distância.</p>'}
          ${ocorrencias.map((o) => `<div class="card">
            <div style="display:flex;gap:8px;align-items:center"><span class="badge-dist">${fmtDist(dist(o))}</span><b style="flex:1">${esc(o.tipo || '')} · ${esc(o.foco || '')}</b></div>
            <div style="margin-top:6px">${esc(o.endereco || '')}</div>
            <div class="muted small">${esc(o.protocolo || '')} · ${esc(o.status || '')}${o.quando ? ' · ' + fmtCurta(o.quando) : ''}</div>
            ${o.latitude != null ? `<a class="btn outline sm mt" href="geo:${o.latitude},${o.longitude}?q=${o.latitude},${o.longitude}(${encodeURIComponent(o.endereco || '')})" data-maps="https://maps.google.com/?q=${o.latitude},${o.longitude}">${svg('nav')} Abrir rota no mapa</a>` : `<button class="btn outline sm mt" type="button" disabled>${svg('nav')} Abrir rota no mapa</button>`}
          </div>`).join('')}
          <p class="section">Alertas (${alertasAg.length})</p>
          ${alertasAg.map((a) => `<div class="card item">${svg('warning', 'icon-warn')}<div class="tx"><b style="font-size:16px">${esc(a.titulo || '')}</b><p style="margin-top:4px">${esc(a.mensagem || '')}${a.quando ? '<br><span class="muted small">' + fmtCurta(a.quando) + '</span>' : ''}</p></div></div>`).join('')}
        </main>`;
      $app.querySelector('#btnReload').addEventListener('click', load);
      $app.querySelector('#btnLogout').addEventListener('click', () => { journeyStop(); setAgente(null, null); render(); });
      $app.querySelector('#btnJornada').addEventListener('click', () => { journey.active ? journeyStop() : journeyStart(); });
      // iPhone não abre geo:; cai para o Google Maps na web.
      $app.querySelectorAll('[data-maps]').forEach((a) => a.addEventListener('click', (e) => { if (/iphone|ipad|ipod/i.test(navigator.userAgent)) { e.preventDefault(); window.open(a.dataset.maps, '_blank'); } }));
    };
    async function load() {
      if (loading) return; loading = true; draw();
      try { await loadPainel(); erro = null; }
      catch (e) {
        if (e instanceof ApiError && e.status === 401) { journeyStop(); setAgente(null, null); loading = false; render(); return; }
        erro = e instanceof ApiError ? e.message : (state.painel ? 'Sem conexão: mostrando dados salvos no aparelho.' : e.message);
      }
      loading = false; draw();
    }
    draw(); load();
    currentPosition().then((p) => { agentPos = p; draw(); }).catch(() => {});
    journey.onChange = draw;
    const onOutbox = () => load();
    document.addEventListener('outbox', onOutbox);
    return () => { journey.onChange = null; document.removeEventListener('outbox', onOutbox); };
  }
  function visita(idx) {
    const p = state.painel || {}; const q = (p.quarteiroes || [])[idx];
    if (!q) { go('agente'); return; }
    const depositos = p.depositos || [];
    const inicio = String(q.inicio || '').slice(0, 10), fim = String(q.fim || '').slice(0, 10);
    const clamp = (d) => (inicio && d < inicio ? inicio : fim && d > fim ? fim : d);
    let situacao = null, positivo = null, pos = agentPos, locating = false, foto = null, sending = false;
    const SIT = { INSPECIONADO: 'Inspecionado', FECHADO: 'Fechado', RECUSADO: 'Recusado', DESABITADO: 'Desabitado' };
    $app.innerHTML = `${bar('Registrar visita', { back: 'agente', flat: true })}
      <main class="page"><form id="f" novalidate>
        ${noteReq}
        <div class="card soft item mt" style="align-items:center">${svg('grid', 'icon-primary')}<div class="tx"><b style="font-size:16px">${esc(q.quarteirao)} · ${esc(q.bairro || '')} / ${esc(q.area || '')}</b><span class="muted small">${esc(q.titulo || q.plano)}<br>Período: ${fmtData(inicio)} a ${fmtData(fim)}</span></div></div>
        <div class="mt">${field({ name: 'imovel_codigo', label: 'Código do imóvel', hint: 'Ex.: 0123 ou número da casa' })}</div>
        ${field({ name: 'data_inspecao', label: 'Data da inspeção', type: 'date', value: clamp(hoje()), min: inicio, max: fim, lead: 'event' })}
        <p class="subsection" id="sitTitle">Situação do imóvel <b class="req">*</b><span class="err" hidden>Obrigatório</span></p>
        <div class="chips" id="sit">${Object.entries(SIT).map(([k, v]) => `<button class="chip" type="button" data-sit="${k}">${v}</button>`).join('')}</div>
        <div id="posWrap" hidden>
          <p class="subsection" id="posTitle">Positivo para Aedes? <b class="req">*</b><span class="err" hidden>Obrigatório</span></p>
          <div class="chips" id="posChips"><button class="chip" type="button" data-pos="SIM">Sim</button><button class="chip" type="button" data-pos="NAO">Não</button></div>
        </div>
        <div id="depWrap" hidden>
          <p class="subsection">Recipientes positivos por categoria <b class="req">*</b></p>
          ${depositos.map((d) => field({ name: 'dep_' + d.codigo, label: d.rotulo, value: '0', inputmode: 'numeric', required: false, validate: 'int' })).join('')}
        </div>
        <p class="subsection">Localização</p>
        <div id="loc"></div>
        <p class="subsection">Foto do imóvel (opcional)</p>
        <div class="row" style="align-items:center">
          <button class="btn outline" type="button" id="btnFoto">${svg('camera')} <span>Tirar foto</span></button>
          <div class="thumb sm" id="fotoThumb" hidden style="flex:0 0 64px"><img alt=""></div>
        </div>
        <input type="file" id="inFoto" accept="image/*" capture="environment" hidden>
        <p class="muted small" style="margin-top:6px">A foto fica guardada no aparelho junto do registro.</p>
        <button class="btn primary mt2" type="submit" id="btnSend">${svg('save')} <span>Registrar visita</span></button>
      </form></main>`;
    const form = $app.querySelector('#f'); wire(form);
    const drawLoc = () => { form.querySelector('#loc').innerHTML = `<div class="card softer loc ${pos ? 'ok' : ''}">${svg(pos ? 'gps' : 'gpsOff')}<div><b>${pos ? pos.coords.latitude.toFixed(5) + ', ' + pos.coords.longitude.toFixed(5) : 'Sem coordenadas'}</b><span>${pos ? 'Precisão ' + Math.round(pos.coords.accuracy) + ' m' : 'Toque em atualizar'}</span></div><span class="spacer"></span><button class="iconbtn" type="button" id="btnLoc" ${locating ? 'disabled' : ''} aria-label="Atualizar localização">${svg('gps', 'icon-primary ' + (locating ? 'spin' : ''))}</button></div>`;
      form.querySelector('#btnLoc').addEventListener('click', localizar); };
    async function localizar() { locating = true; drawLoc(); try { pos = await currentPosition(); agentPos = pos; } catch (e) { toast(e.message); } locating = false; drawLoc(); }
    drawLoc(); localizar();
    form.querySelector('#sit').addEventListener('click', (e) => {
      const b = e.target.closest('[data-sit]'); if (!b) return;
      situacao = b.dataset.sit; form.querySelectorAll('[data-sit]').forEach((x) => { x.classList.toggle('on', x === b); x.classList.toggle('plain', x === b); });
      form.querySelector('#sitTitle').classList.remove('error'); form.querySelector('#sitTitle .err').hidden = true;
      if (situacao !== 'INSPECIONADO') { positivo = null; form.querySelectorAll('[data-pos]').forEach((x) => x.classList.remove('on', 'plain')); }
      form.querySelector('#posWrap').hidden = situacao !== 'INSPECIONADO'; form.querySelector('#depWrap').hidden = !(situacao === 'INSPECIONADO' && positivo === 'SIM');
    });
    form.querySelector('#posChips').addEventListener('click', (e) => {
      const b = e.target.closest('[data-pos]'); if (!b) return;
      positivo = b.dataset.pos; form.querySelectorAll('[data-pos]').forEach((x) => { x.classList.toggle('on', x === b); x.classList.toggle('plain', x === b); });
      form.querySelector('#posTitle').classList.remove('error'); form.querySelector('#posTitle .err').hidden = true;
      form.querySelector('#depWrap').hidden = positivo !== 'SIM';
    });
    form.querySelector('#btnFoto').addEventListener('click', () => form.querySelector('#inFoto').click());
    form.querySelector('#inFoto').addEventListener('change', (e) => { const f = readFiles(e.target, 1, [])[0]; if (!f) return; foto = f; const t = form.querySelector('#fotoThumb'); t.hidden = false; t.querySelector('img').src = fileUrl(f); form.querySelector('#btnFoto span').textContent = 'Trocar foto'; });
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); if (sending) return;
      form.querySelector('#depWrap [data-validate]') && form.querySelectorAll('#depWrap [data-validate]').forEach((el) => { if (form.querySelector('#depWrap').hidden) el.removeAttribute('data-validate'); else el.setAttribute('data-validate', 'int'); });
      const ok = validate(form);
      const erroSit = situacao === null, erroPos = situacao === 'INSPECIONADO' && positivo === null;
      form.querySelector('#sitTitle').classList.toggle('error', erroSit); form.querySelector('#sitTitle .err').hidden = !erroSit;
      form.querySelector('#posTitle').classList.toggle('error', erroPos); form.querySelector('#posTitle .err').hidden = !erroPos;
      if (!ok || erroSit || erroPos) { if (ok) form.querySelector(erroSit ? '#sitTitle' : '#posTitle').scrollIntoView({ behavior: 'smooth', block: 'center' }); toast('Preencha os campos obrigatórios destacados.'); return; }
      sending = true; form.querySelector('#btnSend').disabled = true; form.querySelector('#btnSend span').textContent = 'Enviando…';
      const fields = { plano: q.plano, quarteirao: q.quarteirao, imovel_codigo: val(form, 'imovel_codigo'), data_inspecao: val(form, 'data_inspecao'), situacao, demo: false };
      if (situacao === 'INSPECIONADO') fields.positivo_aedes = positivo;
      if (situacao === 'INSPECIONADO' && positivo === 'SIM') fields.depositos = Object.fromEntries(depositos.map((d) => [d.codigo, parseInt(val(form, 'dep_' + d.codigo), 10) || 0]));
      if (pos) { fields.latitude = pos.coords.latitude; fields.longitude = pos.coords.longitude; }
      try {
        // a foto fica só no aparelho (dentro da fila local): o servidor ainda não recebe mídia de visita
        const codigo = await outbox.send('visita', fields, foto ? [foto] : []);
        await dialog(codigo ? { icon: 'check', iconClass: 'icon-ok', title: 'Visita registrada', text: `Inspeção ${codigo} registrada no quarteirão ${q.quarteirao}.` }
          : { icon: 'cloudOff', iconClass: 'icon-warn', title: 'Salva no aparelho', text: 'Sem internet agora. A visita foi salva no aparelho e será enviada automaticamente quando houver conexão.' });
        go('agente');
      } catch (err) {
        sending = false; form.querySelector('#btnSend').disabled = false; form.querySelector('#btnSend span').textContent = 'Registrar visita';
        toast(err instanceof ApiError ? err.display : 'Falha ao enviar: ' + err.message);
      }
    });
  }
  function loadLeaflet() {
    if (window.L) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.appendChild(css);
      const s = document.createElement('script'); s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; s.onload = resolve; s.onerror = () => reject(new Error('Mapa indisponível sem internet.')); document.head.appendChild(s);
    });
  }
  function mapa() {
    const p = state.painel || {};
    $app.innerHTML = `${bar('Mapa do dia', { back: 'agente', flat: true })}<div id="map"><p class="center muted">Carregando mapa…</p></div>`;
    let map = null;
    loadLeaflet().then(() => {
      const rastro = (p.rastro_hoje || []).map((x) => [Number(x[0]), Number(x[1])]);
      const ocorrencias = (p.ocorrencias || []).filter((o) => o.latitude != null && o.longitude != null);
      const centro = agentPos ? [agentPos.coords.latitude, agentPos.coords.longitude] : rastro.length ? rastro[rastro.length - 1] : ocorrencias.length ? [ocorrencias[0].latitude, ocorrencias[0].longitude] : [-8.357, -36.697];
      $app.querySelector('#map').innerHTML = '';
      map = L.map('map').setView(centro, 15);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap', maxZoom: 19 }).addTo(map);
      if (rastro.length > 1) L.polyline(rastro, { color: '#2c5282', weight: 4 }).addTo(map);
      const pin = (color) => L.divIcon({ className: '', html: `<svg viewBox="0 0 24 24" width="40" height="40" style="fill:${color}"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`, iconSize: [40, 40], iconAnchor: [20, 40] });
      ocorrencias.forEach((o) => L.marker([o.latitude, o.longitude], { icon: pin('#e53e3e') }).addTo(map).bindPopup(`${esc(o.tipo || '')} · ${esc(o.foco || '')}<br>${esc(o.endereco || '')}`));
      if (agentPos) L.marker(centro, { icon: L.divIcon({ className: '', html: `<svg viewBox="0 0 24 24" width="32" height="32" style="fill:#2c5282"><path d="${I.gps}"/></svg>`, iconSize: [32, 32], iconAnchor: [16, 16] }) }).addTo(map);
    }).catch((e) => { $app.querySelector('#map').innerHTML = `<p class="center">${esc(e.message)}</p>`; });
    return () => { if (map) map.remove(); };
  }

  // ------------------------------------------------------------------ Enviados / pendentes
  function enviados() {
    const draw = () => {
      const items = outbox.items;
      $app.innerHTML = `${bar('Enviados / pendentes', { actions: `<button class="iconbtn" type="button" id="btnSync" aria-label="Reenviar pendentes">${svg('sync')}</button>` })}
        <main class="page" style="padding-top:16px">${items.length ? items.map((it) => {
          const [icon, cls, status] = it.protocolo ? ['check', 'icon-ok', (it.kind === 'visita' ? 'Inspeção ' : 'Protocolo ') + it.protocolo] : it.erro ? ['error', 'icon-danger', 'Rejeitado: ' + it.erro] : ['schedule', 'icon-warn', 'Pendente: será enviado quando houver internet'];
          return `<div class="card item">${svg(icon, cls)}<div class="tx"><b style="font-size:16px">${esc(outbox.titulo(it))}</b><span class="muted small">${fmtDataHora(it.createdAt)}</span><br><span class="small">${esc(status)}</span></div></div>`;
        }).join('') : '<p class="center">Nenhum relato feito neste aparelho.</p>'}</main>`;
      $app.querySelector('#btnSync').addEventListener('click', () => { toast('Reenviando pendentes…'); outbox.flush(); });
    };
    draw(); document.addEventListener('outbox', draw);
    return () => document.removeEventListener('outbox', draw);
  }

  // ------------------------------------------------------------------ inicialização
  (async () => {
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    await outbox.init();
    render();
    loadConfig();
    outbox.flush();
    window.addEventListener('online', () => { outbox.flush(); });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) outbox.flush(); });
  })();
})();
