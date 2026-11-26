/* Individual selections are independent snapshots. Account scope stays on the server. */
(() => {
  'use strict';
  const root = document.getElementById('ti-users-central');
  if (!root) return;
  const data = JSON.parse(document.getElementById('ti-users-data').textContent);
  const get = id => root.querySelector(`#${id}`);
  const editorDialog = get('ti-user-access-dialog');
  const create = (tag, className = '', text = '') => {
    const node = document.createElement(tag);
    node.className = className; node.textContent = text; return node;
  };
  const catalog = data.catalog;
  const unavailable = new Set(data.unavailable_permissions || []);
  let state = null, draft = null, areaId = catalog[0].id, page = 1;
  let listing = [], loading = false, saving = false, searching = false, hasMore = false, searchSequence = 0, userSequence = 0, searchTimer;
  const snapshot = value => JSON.stringify({
    areas: [...value.areas].sort(), permissions: [...value.permissions].sort(), nome_acesso: value.nome_acesso.trim(),
  });
  const dirty = () => state && snapshot(state) !== snapshot(draft);
  const copy = value => ({areas: new Set(value.areas), permissions: new Set(value.permissions), nome_acesso: value.nome_acesso || ''});
  const endpoint = (url, id) => url.replace('/0', `/${id}`);
  function message(text = '', type = '') {
    for (const id of ['ti-user-feedback', 'ti-user-editor-feedback']) {
      get(id).textContent = text; get(id).hidden = !text; get(id).dataset.type = type;
    }
  }
  async function api(url, options = {}, timeoutMs = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', ...options, signal: controller.signal});
      if (response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) {
        const error = new Error('Sua sessão pode ter expirado. Entre novamente e recarregue a central.');
        error.code = response.redirected ? 'session_expired' : 'invalid_response'; throw error;
      }
      const result = await response.json();
      if (!response.ok) {
        const error = new Error(result.error || 'Não foi possível concluir a operação.');
        error.status = response.status; error.code = result.code; throw error;
      }
      return result;
    } catch (error) {
      if (error.name === 'AbortError') { const failure = new Error('A conexão demorou.'); failure.code = 'request_timeout'; throw failure; }
      if (error instanceof TypeError) { const failure = new Error('Confira sua conexão e tente novamente.'); failure.code = 'network_error'; throw failure; }
      if (error instanceof SyntaxError) error.code = 'invalid_response';
      throw error;
    } finally { clearTimeout(timer); }
  }
  function renderList() {
    const list = get('ti-user-list'); list.replaceChildren();
    for (const user of listing) {
      const item = create('tr', state?.user.id === user.id ? 'is-selected' : '');
      const initials = user.name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toLocaleUpperCase('pt-BR');
      const avatar = create('span', 'ti-avatar', initials); avatar.setAttribute('aria-hidden', 'true');
      const identity = create('td', 'ti-directory-identity');
      const content = create('span', 'ti-profile-label');
      const name = create('button', 'ti-user-name-button', user.name); name.type = 'button';
      const action = create('button', 'btn btn-outline-primary ti-manage-user', 'Gerenciar acessos'); action.type = 'button';
      action.setAttribute('aria-label', `Gerenciar acessos de ${user.name} (${user.login})`);
      for (const button of [name, action]) {
        button.disabled = loading || saving || searching || !user.editable;
        if (user.editable) button.addEventListener('click', () => selectUser(user.id));
      }
      content.append(name, create('small', 'ti-user-login', user.login)); identity.append(avatar, content);
      const role = create('td', 'ti-directory-role'); role.dataset.label = 'Perfil';
      role.append(create('span', 'ti-user-role', user.role_label));
      const city = create('td', 'ti-directory-city'); city.dataset.label = 'Prefeitura / região';
      city.append(create('span', '', user.prefeitura_nome || 'Sem prefeitura'));
      if (user.regiao) city.append(create('small', '', user.regiao));
      const actions = create('td', 'ti-directory-actions'); actions.append(action);
      item.append(identity, role, city, actions); list.append(item);
    }
    get('ti-users-empty').hidden = listing.length > 0;
  }
  async function search() {
    const sequence = ++searchSequence;
    searching = true;
    root.querySelector('.ti-user-directory').setAttribute('aria-busy', 'true');
    get('ti-user-results').textContent = 'Buscando usuários…';
    get('ti-user-prev').disabled = true; get('ti-user-next').disabled = true;
    get('ti-user-clear').hidden = ![get('ti-user-search').value.trim(), get('ti-user-profile').value, get('ti-user-prefeitura').value].some(Boolean);
    renderList(); get('ti-users-empty').hidden = true;
    try {
      const params = new URLSearchParams({q: get('ti-user-search').value.trim(), page,
        profile: get('ti-user-profile').value, prefeitura: get('ti-user-prefeitura').value});
      const result = await api(`${data.search_url}?${params}`);
      if (sequence !== searchSequence) return;
      listing = result.users; page = result.page; hasMore = result.has_more;
      get('ti-user-page').textContent = `${page} de ${result.pages}`;
      get('ti-user-page').setAttribute('aria-label', `Página ${page} de ${result.pages}`);
      const start = result.total ? (page - 1) * result.page_size + 1 : 0;
      get('ti-user-results').textContent = result.total === 1 ? '1 usuário encontrado'
        : result.total ? `${start}–${start + listing.length - 1} de ${result.total} usuários` : '0 usuários encontrados';
      get('ti-user-list').scrollTop = 0;
    } catch (error) {
      if (sequence === searchSequence) {
        listing = []; hasMore = false; message(error.message);
        get('ti-user-results').textContent = 'Não foi possível carregar os usuários.';
      }
    } finally {
      if (sequence === searchSequence) {
        searching = false; root.querySelector('.ti-user-directory').removeAttribute('aria-busy'); renderList();
        get('ti-users-empty').hidden = listing.length > 0 || !get('ti-user-results').textContent.startsWith('0 ');
        get('ti-user-prev').disabled = page === 1;
        get('ti-user-next').disabled = !hasMore;
      }
    }
  }
  function changed() {
    get('ti-user-source').textContent = dirty() ? 'Alterações não salvas' : state.configured ? 'Acesso individual' : 'Acessos do perfil atual';
    for (const button of root.querySelectorAll('[data-ti-user-save]')) {
      button.disabled = saving || loading || (state.configured && !dirty());
      button.textContent = saving ? 'Salvando…' : 'Salvar alterações';
    }
  }
  function progress(text) {
    get('ti-user-saving-text').textContent = text;
    get('ti-user-save-note').textContent = text;
  }
  function setSaving(active) {
    saving = active;
    root.querySelector('.ti-access-dialog-body').inert = active;
    get('ti-user-close').disabled = active;
    get('ti-user-check-save').disabled = active;
    get('ti-user-saving').hidden = !active;
    root.querySelector('.ti-access-dialog-body').setAttribute('aria-busy', String(active));
    changed();
  }
  function acceptSaved(configuration, recovered = false, active = data.active) {
    state = configuration; draft = copy(state); render();
    get('ti-user-check-save').hidden = true;
    message(!active ? 'Alterações salvas para validação. A aplicação das permissões está desativada neste ambiente.'
      : recovered ? 'Salvamento conferido: suas alterações foram gravadas.' : 'Alterações salvas com sucesso.', 'success');
    get('ti-user-save-note').textContent = 'Alterações salvas. Você já pode fechar esta janela.';
  }
  async function selectUser(id) {
    if (saving || loading) return;
    if (state?.user.id === id) { render(); editorDialog.showModal(); return; }
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
      render(); message(); get('ti-user-check-save').hidden = true; editorDialog.showModal(); editorDialog.scrollTop = 0;
    } catch (error) { if (sequence === userSequence) message(error.message); }
    finally {
      if (sequence === userSequence) {
        loading = false; get('ti-user-editor').inert = false; renderList(); if (state) changed();
      }
    }
  }
  function render() {
    get('ti-user-name').textContent = state.user.name;
    get('ti-user-scope').textContent = [state.user.login, state.user.role_label, state.user.prefeitura_nome, state.user.regiao].filter(Boolean).join(' · ');
    get('ti-user-access-name').value = draft.nome_acesso;
    get('ti-user-save-note').textContent = 'Revise e confirme para salvar as alterações apenas para este usuário.';
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
  function resetSearch(debounce = false) {
    ++searchSequence; clearTimeout(searchTimer); page = 1;
    get('ti-user-prev').disabled = true; get('ti-user-next').disabled = true;
    if (debounce) searchTimer = setTimeout(search, 250);
    else search();
  }
  for (const [key, options] of [['profile', data.user_filters.profiles], ['prefeitura', data.user_filters.prefeituras]]) {
    for (const option of options) {
      const node = create('option', '', option.name); node.value = option.id; get(`ti-user-${key}`).append(node);
    }
    get(`ti-user-${key}`).addEventListener('change', () => resetSearch());
  }
  get('ti-user-search').addEventListener('input', () => resetSearch(true));
  get('ti-user-clear').addEventListener('click', () => {
    for (const key of ['search', 'profile', 'prefeitura']) get(`ti-user-${key}`).value = '';
    resetSearch(); get('ti-user-search').focus();
  });
  get('ti-user-prev').addEventListener('click', () => { if (!searching && page > 1) { page--; search(); } });
  get('ti-user-next').addEventListener('click', () => { if (!searching && hasMore) { page++; search(); } });
  function closeEditor() {
    if (saving || loading) return;
    if (dirty() && !window.confirm('Descartar as alterações não salvas deste usuário?')) return;
    if (state) draft = copy(state);
    editorDialog.close();
  }
  get('ti-user-close').addEventListener('click', closeEditor);
  editorDialog.addEventListener('cancel', event => { event.preventDefault(); closeEditor(); });
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
  function reviewChanges() {
    if (!state || saving || loading) return;
    const changes = diff(), list = get('ti-user-review-changes'); list.replaceChildren();
    get('ti-user-review-target').textContent = `${state.user.name} · ${state.user.login}`;
    get('ti-user-review-summary').textContent = `Adições: ${changes.added.length}. Remoções: ${changes.removed.length}. O conjunto será individual; outros usuários do perfil permanecem com seus acessos atuais.`;
    for (const [label, codes] of [['Liberar', changes.added], ['Remover', changes.removed]]) {
      for (const code of codes) list.append(create('li', '', `${label}: ${permissionLabel(code)}`));
    }
    if (state.nome_acesso !== draft.nome_acesso.trim()) list.append(create('li', '', `Nome do acesso: ${draft.nome_acesso.trim() || 'Sem nome'}`));
    get('ti-user-dialog').showModal();
  }
  for (const button of root.querySelectorAll('[data-ti-user-save]')) button.addEventListener('click', reviewChanges);
  get('ti-user-cancel').addEventListener('click', () => get('ti-user-dialog').close());
  get('ti-user-confirm').addEventListener('click', async () => {
    if (saving || !state) return;
    const submitted = JSON.parse(snapshot(draft)), previousVersion = state.version;
    get('ti-user-dialog').close(); setSaving(true); message();
    progress(`Salvando alterações de ${state.user.name}…`);
    const slow = setTimeout(() => { if (saving) progress('Ainda salvando… aguarde a confirmação antes de fechar.'); }, 8000);
    try {
      const result = await window.IjaTiSave.save({submitted, previousVersion,
        write: () => api(endpoint(data.save_url, state.user.id), {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Central-TI-CSRF': data.csrf_token, 'X-CSRFToken': data.global_csrf_token || '',
          'X-Central-TI-Permission-Schema': data.permission_schema_version},
        body: JSON.stringify({version: previousVersion, ...submitted})}, 45000),
        read: () => api(endpoint(data.detail_url, state.user.id)),
        onVerify: () => { clearTimeout(slow); progress('Conferindo se as alterações foram gravadas…'); },
      });
      acceptSaved(result.configuration, result.recovered, result.active_rules_changed ?? data.active);
    } catch (error) {
      message(error.message, 'error');
      get('ti-user-check-save').hidden = error.code !== 'save_unconfirmed';
      get('ti-user-save-note').textContent = 'Salvamento não confirmado. Suas alterações foram mantidas nesta tela.';
    } finally { clearTimeout(slow); setSaving(false); }
  });
  get('ti-user-check-save').addEventListener('click', async () => {
    if (saving || !state) return;
    setSaving(true); progress('Conferindo o salvamento…');
    try {
      const latest = await api(endpoint(data.detail_url, state.user.id));
      if (window.IjaTiSave.matches(latest, JSON.parse(snapshot(draft)), state.version)) acceptSaved(latest, true);
      else {
        message('As alterações desta tela ainda não foram confirmadas no servidor. Confira os acessos antes de tentar novamente.', 'error');
        get('ti-user-save-note').textContent = 'Salvamento não confirmado. Suas alterações continuam nesta tela.';
      }
    } catch (error) {
      message(error.message, 'error');
      get('ti-user-save-note').textContent = 'Não foi possível conferir. Suas alterações continuam nesta tela.';
    }
    finally { setSaving(false); }
  });
  window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
  search();
})();
