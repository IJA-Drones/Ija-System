/* Individual selections are independent snapshots. Account scope stays on the server. */
(() => {
  'use strict';
  const root = document.getElementById('ti-users-central');
  if (!root) return;
  const data = JSON.parse(document.getElementById('ti-users-data').textContent);
  const get = id => root.querySelector(`#${id}`);
  const create = (tag, className = '', text = '') => {
    const node = document.createElement(tag);
    node.className = className; node.textContent = text; return node;
  };
  const catalog = data.catalog;
  const unavailable = new Set(data.unavailable_permissions || []);
  let state = null, draft = null, areaId = catalog[0].id, page = 1;
  let listing = [], loading = false, saving = false, searchSequence = 0, userSequence = 0, searchTimer;
  const snapshot = value => JSON.stringify({
    areas: [...value.areas].sort(), permissions: [...value.permissions].sort(), nome_acesso: value.nome_acesso.trim(),
  });
  const dirty = () => state && snapshot(state) !== snapshot(draft);
  const copy = value => ({areas: new Set(value.areas), permissions: new Set(value.permissions), nome_acesso: value.nome_acesso || ''});
  const endpoint = (url, id) => url.replace('/0', `/${id}`);
  function message(text = '') {
    get('ti-user-feedback').textContent = text;
    get('ti-user-feedback').hidden = !text;
  }
  async function api(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', ...options, signal: controller.signal});
      if (response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) {
        throw new Error('Sua sessão pode ter expirado. Entre novamente e recarregue a central.');
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Não foi possível concluir a operação.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('A conexão demorou. Tente novamente.');
      if (error instanceof TypeError) throw new Error('Confira sua conexão e tente novamente.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function renderList() {
    const list = get('ti-user-list'); list.replaceChildren();
    for (const user of listing) {
      const item = create('li');
      const button = create('button', 'ti-profile-button'); button.type = 'button';
      button.setAttribute('aria-pressed', String(state?.user.id === user.id));
      button.disabled = loading || saving;
      const content = create('span', 'ti-profile-label');
      content.append(create('strong', '', user.name), create('small', 'ti-user-login', `${user.login} · ${user.role_label}`));
      button.append(content); button.addEventListener('click', () => selectUser(user.id));
      item.append(button); list.append(item);
    }
    get('ti-users-empty').hidden = listing.length > 0;
  }
  async function search() {
    const sequence = ++searchSequence;
    try {
      const params = new URLSearchParams({q: get('ti-user-search').value.trim(), page});
      const result = await api(`${data.search_url}?${params}`);
      if (sequence !== searchSequence) return;
      listing = result.users; renderList();
      get('ti-user-page').textContent = `Página ${page}`;
      get('ti-user-prev').disabled = page === 1;
      get('ti-user-next').disabled = !result.has_more;
    } catch (error) { if (sequence === searchSequence) message(error.message); }
  }
  function changed() {
    get('ti-user-source').textContent = dirty() ? 'Alterações não salvas' : state.configured ? 'Acesso individual' : 'Acessos do perfil atual';
    get('ti-user-review').disabled = saving || loading || (state.configured && !dirty());
  }
  async function selectUser(id) {
    if (saving || loading || state?.user.id === id) return;
    if (dirty() && !window.confirm('Descartar as alterações não salvas deste usuário?')) return;
    const sequence = ++userSequence;
    loading = true; renderList();
    get('ti-user-editor').inert = true;
    message('Carregando os acessos do usuário…');
    try {
      const result = await api(endpoint(data.detail_url, id));
      if (sequence !== userSequence) return;
      state = result; draft = copy(result);
      areaId = catalog.find(area => draft.areas.has(area.id))?.id || catalog[0].id;
      render(); message();
    } catch (error) { if (sequence === userSequence) message(error.message); }
    finally {
      if (sequence === userSequence) {
        loading = false; get('ti-user-editor').inert = false; renderList(); if (state) changed();
      }
    }
  }
  function render() {
    get('ti-user-placeholder').hidden = true; get('ti-user-editor').hidden = false;
    get('ti-user-name').textContent = state.user.name;
    get('ti-user-scope').textContent = `${state.user.login} · ${state.user.role_label}${state.user.regiao ? ` · ${state.user.regiao}` : ''}`;
    get('ti-user-access-name').value = draft.nome_acesso;
    get('ti-user-save-note').textContent = data.active ? 'Os acessos passam a valer na próxima requisição.' : 'Configuração em validação: os acessos atuais permanecem iguais.';
    renderAreas(); renderModules(); changed(); renderList();
  }
  function renderAreas() {
    const nav = get('ti-user-areas'); nav.replaceChildren();
    for (const area of catalog) {
      const button = create('button', 'ti-area-button', area.label); button.type = 'button';
      button.setAttribute('aria-pressed', String(area.id === areaId));
      button.addEventListener('click', () => { areaId = area.id; renderAreas(); renderModules(); });
      nav.append(button);
    }
  }
  function renderModules() {
    const area = catalog.find(value => value.id === areaId), enabled = draft.areas.has(areaId);
    get('ti-user-area-title').textContent = area.label;
    get('ti-user-area-enabled').checked = enabled;
    const list = get('ti-user-modules'); list.replaceChildren();
    area.modules.forEach(([id, label, description, glyph, actions], index) => {
      const prefix = `${area.id}.${id}`, codes = actions.split(' ').map(action => `${prefix}.${action}`);
      const details = create('details', 'ti-module'); details.open = codes.some(code => draft.permissions.has(code));
      const summary = create('summary'); summary.append(create('span', 'ti-module-label', label));
      const count = create('span', 'ti-module-count'); summary.append(count);
      const fieldset = create('fieldset'); fieldset.disabled = !enabled || prefix === 'sistema.perfis';
      fieldset.append(create('legend', 'visually-hidden', `Ações de ${label}`));
      const tools = create('div', 'ti-module-tools'), grid = create('div', 'ti-action-grid');
      const inputs = [];
      function sync() {
        for (const input of inputs) input.checked = draft.permissions.has(input.value);
        count.textContent = `${inputs.filter(input => input.checked).length}/${inputs.length}`;
      }
      for (const [text, checked] of [['Marcar todas', true], ['Limpar', false]]) {
        const button = create('button', 'ti-text-button', text); button.type = 'button';
        button.setAttribute('aria-label', `${text} em ${label}`);
        button.addEventListener('click', () => {
          for (const code of codes) {
            if (checked && unavailable.has(code)) continue;
            draft.permissions[checked ? 'add' : 'delete'](code);
          }
          sync(); changed();
        }); tools.append(button);
      }
      for (const code of codes) {
        const action = code.split('.').at(-1), item = create('label', 'ti-action'), input = create('input');
        input.type = 'checkbox'; input.value = code; input.disabled = unavailable.has(code);
        input.addEventListener('change', () => {
          draft.permissions[input.checked ? 'add' : 'delete'](code);
          if (input.checked) draft.permissions.add(`${prefix}.consultar`);
          else if (action === 'consultar') codes.forEach(value => draft.permissions.delete(value));
          sync(); changed();
        });
        item.append(input, create('span', 'ti-action-label', data.labels[action] || action));
        inputs.push(input); grid.append(item);
      }
      if (prefix === 'sistema.perfis') fieldset.title = 'A administração dos acessos permanece exclusiva de Dev e Gestor de TI.';
      fieldset.append(tools, grid); details.append(summary, fieldset); list.append(details); sync();
    });
  }
  function diff() {
    const before = new Set([...state.permissions, ...state.areas.map(id => `area:${id}`)]);
    const after = new Set([...draft.permissions, ...[...draft.areas].map(id => `area:${id}`)]);
    return {added: [...after].filter(code => !before.has(code)), removed: [...before].filter(code => !after.has(code))};
  }
  function permissionLabel(code) {
    if (code.startsWith('area:')) return catalog.find(area => area.id === code.slice(5))?.label || code;
    const [areaId, moduleId, action] = code.split('.'), area = catalog.find(item => item.id === areaId);
    const module = area?.modules.find(item => item[0] === moduleId);
    return `${area?.label || areaId} / ${module?.[1] || moduleId} / ${data.labels[action] || action}`;
  }
  get('ti-user-search').addEventListener('input', () => {
    ++searchSequence; clearTimeout(searchTimer); page = 1; searchTimer = setTimeout(search, 250);
  });
  get('ti-user-prev').addEventListener('click', () => { if (page > 1) { page--; search(); } });
  get('ti-user-next').addEventListener('click', () => { page++; search(); });
  get('ti-user-access-name').addEventListener('input', event => { draft.nome_acesso = event.target.value; changed(); });
  get('ti-user-area-enabled').addEventListener('change', event => {
    draft.areas[event.target.checked ? 'add' : 'delete'](areaId);
    if (!event.target.checked) for (const code of draft.permissions) if (code.startsWith(`${areaId}.`)) draft.permissions.delete(code);
    renderModules(); changed();
  });
  get('ti-user-copy-profile').addEventListener('click', () => {
    draft = {...copy(state.profile_template), nome_acesso: draft.nome_acesso}; render();
    message('Acessos do perfil copiados para revisão. Salve para aplicar apenas a este usuário.');
  });
  get('ti-user-review').addEventListener('click', () => {
    if (!state || saving || loading) return;
    const changes = diff(), list = get('ti-user-review-changes'); list.replaceChildren();
    get('ti-user-review-target').textContent = `${state.user.name} · ${state.user.login}`;
    get('ti-user-review-summary').textContent = `Adições: ${changes.added.length}. Remoções: ${changes.removed.length}. O conjunto será individual; outros usuários do perfil permanecem com seus acessos atuais.`;
    for (const [label, codes] of [['Liberar', changes.added], ['Remover', changes.removed]]) {
      for (const code of codes) list.append(create('li', '', `${label}: ${permissionLabel(code)}`));
    }
    if (state.nome_acesso !== draft.nome_acesso.trim()) list.append(create('li', '', `Nome do acesso: ${draft.nome_acesso.trim() || 'Sem nome'}`));
    get('ti-user-dialog').showModal();
  });
  get('ti-user-cancel').addEventListener('click', () => get('ti-user-dialog').close());
  get('ti-user-confirm').addEventListener('click', async () => {
    if (saving || !state) return;
    saving = true; get('ti-user-dialog').close(); root.inert = true; root.setAttribute('aria-busy', 'true');
    try {
      const result = await api(endpoint(data.save_url, state.user.id), {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Central-TI-CSRF': data.csrf_token, 'X-CSRFToken': data.global_csrf_token || '',
          'X-Central-TI-Permission-Schema': data.permission_schema_version},
        body: JSON.stringify({version: state.version, ...JSON.parse(snapshot(draft))})});
      state = result.configuration; draft = copy(state); render();
      message(result.active_rules_changed ? 'Acessos individuais salvos. Eles passam a valer na próxima requisição.' : 'Acessos individuais salvos para validação.');
    } catch (error) { message(error.message); }
    finally { saving = false; root.inert = false; root.removeAttribute('aria-busy'); changed(); }
  });
  window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
  search();
})();
