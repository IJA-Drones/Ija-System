(function (root) {
  'use strict';

  // A new selection invalidates old list, detail, export and map responses.
  function createSelection() {
    let revision = 0;
    return { next: () => ++revision, current: value => value === revision };
  }
  function eligible(job) { return Boolean(job && ['completed', 'partial'].includes(job.status)); }
  if (typeof module !== 'undefined' && module.exports) module.exports = { createSelection, eligible };
  if (!root.document) return;
  const document = root.document;
  const panel = document.getElementById('sinan-workflow');
  if (!panel) return;
  const el = id => document.getElementById('sinan-' + id);
  const config = JSON.parse(el('config').textContent);
  const selection = createSelection();
  const labels = { running: 'Em andamento', completed: 'Concluído', partial: 'Parcial', failed: 'Falhou', cancelled: 'Cancelado' };
  const caseLabels = { suspeito: 'Suspeito', confirmado: 'Confirmado', descartado: 'Descartado', ignorado: 'Não informado' };
  const colors = { suspeito: '#e28b08', confirmado: '#dc2626', descartado: '#15803d', ignorado: '#64748b' };
  const scope = () => ({ disease: el('disease').value, ibge: el('scope').value, year: Number(el('year').value) });
  const isOpen = () => panel.classList.contains('active');
  const number = n => Number(n || 0).toLocaleString('pt-BR');
  const date = n => new Date(n * 1000).toLocaleString('pt-BR');
  let selected = null, jobs = [], pollTimer = null, busy = false, map = null, shapes = [], mapData = null, mapVersion = 0;

  function message(text, error = false) {
    el('import-status').textContent = text;
    el('import-status').dataset.error = String(error);
  }
  async function request(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, { ...options, cache: 'no-store', signal: controller.signal,
        headers: { Accept: 'application/json', 'X-CSRFToken': panel.dataset.csrf, ...options.headers } });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `Não foi possível concluir a operação (HTTP ${response.status}).`);
      }
      return response;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('A operação demorou para responder. Atualize o histórico antes de tentar novamente.');
      if (error instanceof TypeError) throw new Error('Não foi possível conectar ao sistema. Confira a conexão e atualize o histórico. Se o servidor foi reiniciado, recarregue a página.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function json(url, options) { return (await request(url, options)).json(); }
  function td(tr, text) { const cell = document.createElement('td'); cell.textContent = text; tr.appendChild(cell); return cell; }
  function classLabel(job, code) {
    return job.kind === 'csv' ? (caseLabels[code] || code) : `${code === 'unknown' ? '' : code + ' · '}${config.diseases[job.disease].classifications[code] || 'Sem descrição validada'}`;
  }
  function controls() {
    const running = jobs.some(job => job.status === 'running');
    ['import-api', 'import-cases'].forEach(id => { if (el(id)) el(id).disabled = busy || running; });
    el('export-job').disabled = busy || !eligible(selected);
    el('open-map').disabled = !eligible(selected);
  }
  function clearMap() {
    mapVersion++;
    shapes.forEach(shape => shape.setMap(null)); shapes = [];
    mapData = null;
    el('map-section').hidden = true;
    el('map').hidden = false;
  }
  function renderDetail(job) {
    selected = job;
    el('snapshot').hidden = !job;
    if (!job) return;
    const origin = job.kind === 'api' ? 'Fonte pública · município de notificação' : job.demo ? 'DEMONSTRAÇÃO · dados fictícios' : 'Arquivo fornecido pelo usuário';
    el('snapshot-title').textContent = `Detalhes da importação · ${number(job.count)} registros · ${labels[job.status]}`;
    el('snapshot-note').textContent = `${origin} · ${date(job.updated)}. ${job.message || (job.cancel ? 'Cancelamento solicitado; aguardando a requisição em curso.' : 'Importação em andamento. Você pode continuar usando o sistema.')}`;
    el('snapshot-note').classList.toggle('sinan-demo-label', job.demo);
    el('cancel-job').hidden = job.status !== 'running';
    el('cancel-job').disabled = job.cancel;
    el('snapshot-stats').hidden = !eligible(job);
    el('saved-classes').replaceChildren();
    for (const [code, count] of Object.entries(job.summary?.classifications || {})) {
      const tr = document.createElement('tr'); td(tr, classLabel(job, code)); td(tr, number(count)); el('saved-classes').appendChild(tr);
    }
    const weeks = Object.entries(job.summary?.weeks || {}).sort(([a], [b]) => a.localeCompare(b));
    const maximum = Math.max(1, ...weeks.map(([, n]) => n));
    el('saved-weeks').replaceChildren();
    for (const [week, count] of weeks) {
      const row = document.createElement('div'); row.className = 'sinan-week';
      const label = document.createElement('span'); label.textContent = `${week.slice(0, 4)}/${week.slice(4)}`;
      const track = document.createElement('div'); const bar = document.createElement('div');
      bar.className = 'sinan-week-bar'; bar.style.width = `${100 * count / maximum}%`; track.appendChild(bar);
      const value = document.createElement('span'); value.textContent = number(count);
      row.append(label, track, value); el('saved-weeks').appendChild(row);
    }
    if (!weeks.length) el('saved-weeks').textContent = 'Sem semana informada.';
    if (job.summary?.unknown_week) {
      const note = document.createElement('p'); note.className = 'small text-muted';
      note.textContent = `${number(job.summary.unknown_week)} registro(s) sem semana informada.`; el('saved-weeks').appendChild(note);
    }
    controls();
  }
  function renderJobs(currentId) {
    const body = el('jobs'); body.replaceChildren();
    if (!jobs.length) {
      const tr = document.createElement('tr'); td(tr, 'Nenhuma importação sua neste filtro.').colSpan = 5; body.appendChild(tr);
    }
    jobs.forEach(job => {
      const tr = document.createElement('tr');
      tr.classList.toggle('sinan-job-selected', job.id === selected?.id);
      td(tr, date(job.created)); td(tr, job.kind === 'api' ? 'API SINAN' : job.demo ? 'CSV · Demonstração' : 'CSV · Vigilância');
      td(tr, `${labels[job.status]}${job.id === currentId ? ' · Atual' : ''}`); td(tr, number(job.count));
      const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-sm btn-outline-primary'; button.textContent = 'Ver detalhes';
      button.setAttribute('aria-controls', 'sinan-snapshot');
      button.addEventListener('click', () => {
        selection.next(); clearTimeout(pollTimer); clearMap(); renderDetail(job); renderJobs(currentId); schedule();
        el('snapshot').scrollIntoView({ behavior: 'smooth', block: 'start' });
        el('snapshot-title').focus({ preventScroll: true });
      });
      td(tr, '').appendChild(button); body.appendChild(tr);
    });
    controls();
  }
  function context() {
    const filters = scope(); const city = config.municipalities.find(c => c.ibge === filters.ibge);
    el('saved-context').textContent = `${config.diseases[filters.disease].label} · ${city.name} / ${city.uf} · ${filters.year}`;
  }
  async function refresh({ selectId = null, polling = false } = {}) {
    const version = selection.next();
    clearTimeout(pollTimer);
    context();
    try {
      const payload = await json(`${panel.dataset.url}?${new URLSearchParams(scope())}`);
      if (!selection.current(version)) return;
      jobs = payload.jobs;
      const next = jobs.find(j => j.id === (selectId || selected?.id)) || jobs.find(j => j.status === 'running') || jobs.find(j => j.id === payload.current_id) || jobs[0] || null;
      if (next?.id !== selected?.id) clearMap();
      renderDetail(next); renderJobs(payload.current_id);
      if (!polling) message('');
      schedule();
    } catch (error) { if (selection.current(version)) message(`${error.message} Use “Atualizar histórico” para consultar o andamento.`, true); }
  }
  function schedule() {
    clearTimeout(pollTimer);
    if (isOpen() && !document.hidden && jobs.some(job => job.status === 'running')) pollTimer = setTimeout(() => refresh({ polling: true }), 3000);
  }
  function reset() {
    selection.next(); clearTimeout(pollTimer); clearMap(); jobs = []; selected = null;
    el('snapshot').hidden = true; el('jobs').replaceChildren(); message(''); context(); controls();
    if (isOpen()) refresh();
  }
  async function begin(url, options) {
    if (busy) return;
    busy = true; controls();
    const version = selection.next(); clearTimeout(pollTimer); message('Iniciando importação…');
    try {
      const payload = await json(url, options);
      if (!selection.current(version)) return;
      clearMap(); renderDetail(payload.job);
      await refresh({ selectId: payload.job.id });
      message(payload.existing ? 'Este arquivo já foi importado. O lote existente foi aberto.' : 'Importação iniciada. Você pode continuar usando a consulta.');
    } catch (error) { if (selection.current(version)) message(error.message, true); }
    finally { busy = false; controls(); }
  }
  async function download(url, filename) {
    if (busy) return;
    busy = true; controls();
    const version = selection.next(); clearTimeout(pollTimer);
    try {
      const response = await request(url);
      const blob = await response.blob();
      if (!selection.current(version)) return;
      const objectUrl = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = objectUrl; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 30000);
      message('Arquivo CSV preparado.');
    } catch (error) { if (selection.current(version)) message(error.message, true); }
    finally { busy = false; controls(); schedule(); }
  }
  function mapsReady() {
    if (root.__GOOGLE_MAPS_AUTH_FAILED__) return Promise.reject(new Error('Google Maps indisponível neste endereço. Abra o sistema no domínio autorizado. Importações e exportações continuam disponíveis.'));
    if (root.google?.maps?.Map) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const cleanup = () => { clearTimeout(timer); document.removeEventListener('googlemaps:ready', ready); document.removeEventListener('googlemaps:auth-failed', failed); };
      const ready = () => { cleanup(); resolve(); };
      const failed = () => { cleanup(); reject(new Error('Não foi possível carregar o Google Maps. Os indicadores continuam disponíveis.')); };
      const timer = setTimeout(failed, 12000);
      document.addEventListener('googlemaps:ready', ready, { once: true }); document.addEventListener('googlemaps:auth-failed', failed, { once: true });
    });
  }
  function ensureMap() {
    el('map').hidden = false;
    if (!map) map = new root.google.maps.Map(el('map'), { center: { lat: -14, lng: -48 }, zoom: 4, streetViewControl: false, mapTypeControl: false });
    root.google.maps.event.trigger(map, 'resize');
    shapes.forEach(shape => shape.setMap(null)); shapes = [];
  }
  function drawCases() {
    if (!mapData || mapData.kind !== 'csv') return;
    ensureMap();
    const filter = el('map-class').value;
    const points = mapData.points.filter(p => !filter || p.classification === filter);
    const bounds = new root.google.maps.LatLngBounds();
    points.forEach(point => {
      const position = { lat: point.latitude, lng: point.longitude };
      // Fixed-radius symbols mark supplied coordinates, not outbreak/risk areas.
      const marker = new root.google.maps.Circle({ map, center: position, radius: 18, strokeWeight: 1, strokeColor: colors[point.classification], fillColor: colors[point.classification], fillOpacity: .85 });
      const info = new root.google.maps.InfoWindow();
      marker.addListener('click', () => { const content = document.createElement('div'); content.textContent = `${mapData.demo ? 'DEMONSTRAÇÃO · ' : ''}${caseLabels[point.classification]} · ${point.week || 'Sem semana informada'}`; info.setContent(content); info.setPosition(position); info.open({ map }); });
      shapes.push(marker); bounds.extend(position);
    });
    if (points.length) { map.fitBounds(bounds); root.google.maps.event.addListenerOnce(map, 'idle', () => { if (map.getZoom() > 16) map.setZoom(16); }); }
    el('map-status').textContent = `${number(points.length)} de ${number(mapData.points.length)} casos exibidos. Coordenadas fornecidas no CSV.`;
  }
  async function openMap() {
    if (!eligible(selected)) return;
    const jobId = selected.id; const version = ++mapVersion;
    el('map-section').hidden = false; el('map-status').textContent = 'Carregando mapa…';
    el('open-map').disabled = true;
    try {
      const [data] = await Promise.all([json(`${panel.dataset.url}/${jobId}/mapa`), mapsReady()]);
      if (version !== mapVersion || selected?.id !== jobId) return;
      mapData = data; ensureMap();
      el('map-class').hidden = data.kind !== 'csv'; el('map-legend').hidden = data.kind !== 'csv';
      el('map-class').value = '';
      el('map-caption').textContent = data.kind === 'csv'
        ? `${data.demo ? 'DEMONSTRAÇÃO — dados fictícios. ' : ''}Casos com coordenadas · ${data.municipality.name}`
        : `Município de notificação · ${data.municipality.name} · ${number(data.count)} registros${data.status === 'partial' ? ' · LOTE PARCIAL' : ''}`;
      el('map-caption').classList.toggle('sinan-demo-label', data.demo);
      if (data.kind === 'csv') { drawCases(); return; }
      const geocoder = new root.google.maps.Geocoder();
      const result = await Promise.race([
        geocoder.geocode({ address: `${data.municipality.name.replace(' — capital', '').replace(' (São Caetano)', '')}, ${data.municipality.uf}, Brasil`, componentRestrictions: { country: 'BR' } }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('A localização do município demorou para responder. Tente novamente.')), 12000)),
      ]);
      if (version !== mapVersion || selected?.id !== jobId) return;
      const geometry = result.results?.[0]?.geometry;
      if (!geometry) throw new Error('Município não localizado no Google Maps.');
      if (geometry.viewport) map.fitBounds(geometry.viewport); else { map.setCenter(geometry.location); map.setZoom(11); }
      shapes.push(new root.google.maps.Circle({ map, center: geometry.location, radius: 120, strokeColor: '#2563eb', fillColor: '#2563eb', fillOpacity: .5 }));
      el('map-status').textContent = 'O símbolo identifica o município; não representa endereço de paciente, foco ou área de risco.';
    } catch (error) { if (version === mapVersion) { el('map-status').textContent = error.message; el('map').hidden = true; } }
    finally { controls(); }
  }

  el('saved-tab').addEventListener('shown.bs.tab', () => { el('filter-actions').hidden = true; refresh(); });
  el('saved-tab').addEventListener('hidden.bs.tab', () => { el('filter-actions').hidden = false; clearTimeout(pollTimer); selection.next(); });
  el('refresh-jobs').addEventListener('click', () => refresh());
  el('import-api')?.addEventListener('click', () => begin(panel.dataset.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scope()) }));
  el('case-form').addEventListener('submit', event => {
    event.preventDefault();
    const file = el('case-file').files[0];
    if (!file || !file.name.toLowerCase().endsWith('.csv') || file.size > 1024 * 1024) { message('Selecione um CSV de até 1 MiB.', true); return; }
    if (el('case-mode').value === 'false' && !el('case-authorized').checked) { message('Confirme a autorização do arquivo.', true); return; }
    const body = new FormData(); Object.entries(scope()).forEach(([k, v]) => body.append(k, v));
    body.append('file', file); body.append('demo', el('case-mode').value); body.append('authorized', String(el('case-authorized').checked));
    begin(panel.dataset.casesUrl, { method: 'POST', body });
  });
  el('case-mode').addEventListener('change', () => { el('case-authorization').hidden = el('case-mode').value !== 'false'; el('case-authorized').checked = false; });
  function importSource() {
    const csv = el('import-source').value === 'csv';
    el('upload-details').hidden = !csv;
    el('api-import').hidden = csv;
  }
  el('import-source').addEventListener('change', importSource);
  importSource();
  el('export-job').addEventListener('click', () => { if (eligible(selected)) download(`${panel.dataset.url}/${selected.id}/exportar.csv`, `sinan-${selected.disease}-${selected.ibge}-${selected.year}-${selected.status}${selected.demo ? '-DEMONSTRACAO' : ''}.csv`); });
  el('cancel-job').addEventListener('click', async () => {
    if (!selected || selected.status !== 'running') return;
    const jobId = selected.id; const version = selection.next(); clearTimeout(pollTimer);
    el('cancel-job').disabled = true;
    try { await json(`${panel.dataset.url}/${jobId}/cancelar`, { method: 'POST' }); if (selection.current(version)) await refresh({ selectId: jobId }); }
    catch (error) { if (selection.current(version)) { message(error.message, true); el('cancel-job').disabled = false; schedule(); } }
  });
  el('open-map').addEventListener('click', openMap);
  el('map-class').addEventListener('change', drawCases);
  document.addEventListener('googlemaps:auth-failed', () => {
    mapVersion++;
    if (!el('map-section').hidden) {
      el('map').hidden = true;
      el('map-status').textContent = 'Google Maps indisponível neste endereço. Abra o sistema no domínio autorizado. Importações e exportações continuam disponíveis.';
    }
    controls();
  });
  ['disease', 'scope', 'year'].forEach(id => el(id).addEventListener('change', reset));
  el('clear').addEventListener('click', reset);
  document.addEventListener('visibilitychange', () => { if (document.hidden) clearTimeout(pollTimer); else if (isOpen()) refresh(); });
  root.addEventListener('pagehide', () => { clearTimeout(pollTimer); selection.next(); clearMap(); });
})(typeof window !== 'undefined' ? window : globalThis);
