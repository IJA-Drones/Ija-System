(function (root) {
  'use strict';
  const PAGE_SIZE = 10;

  // Uma consulta tem uma doença e um município. Cada página substitui a tabela;
  // voltar usa o cache da própria consulta, sem misturar filtros ou duplicar dados.
  function createPager({ fetchPage, onUpdate }) {
    let active = null;
    function emit(run) { if (active === run) onUpdate(run); }
    function clear() {
      if (active) active.controller.abort();
      active = null;
      onUpdate(null);
    }
    function cancel() {
      if (!active || active.phase !== 'loading') return;
      active.controller.abort();
      active.phase = 'cancelled';
      emit(active);
    }
    async function load(run, offset) {
      const controller = new AbortController();
      run.controller = controller;
      run.requestedOffset = offset;
      run.error = '';
      if (run.pages.has(offset)) {
        run.data = run.pages.get(offset);
        run.phase = 'ready';
        emit(run);
        return run;
      }
      run.phase = 'loading';
      emit(run);
      const isCurrent = () => active === run && run.controller === controller && !controller.signal.aborted;
      try {
        const page = await fetchPage(run.city.ibge, run.year, offset, controller.signal, run.disease);
        if (!isCurrent()) return run;
        if (page.disease !== run.disease || page.municipality?.ibge !== run.city.ibge || page.year !== run.year || page.offset !== offset ||
            !Array.isArray(page.records) || page.records.length > PAGE_SIZE || page.summary?.total !== page.records.length ||
            (!page.finished && !page.limit_reached && (page.records.length !== PAGE_SIZE || page.next_offset !== offset + PAGE_SIZE)) ||
            ((page.finished || page.limit_reached) && page.next_offset !== null)) {
          throw new Error('A resposta não corresponde à página solicitada. Recarregue a tela e tente novamente.');
        }
        // Se o total é múltiplo de 10, só a página vazia confirma o fim.
        // Permanecer na última página com registros evita uma página extra vazia.
        if (!page.records.length && offset > 0 && run.data) {
          run.data = { ...run.data, finished: true, next_offset: null };
          run.pages.set(run.data.offset, run.data);
        } else {
          run.pages.set(offset, page);
          run.data = page;
        }
        run.phase = 'ready';
      } catch (error) {
        if (!isCurrent()) return run;
        run.phase = 'error';
        run.error = error.message || 'Não foi possível consultar a fonte.';
      }
      if (isCurrent()) emit(run);
      return run;
    }
    async function start(city, year, disease = 'dengue') {
      if (active) active.controller.abort();
      const run = { city, year, disease, data: null, pages: new Map(), phase: 'loading', error: '', requestedOffset: 0, controller: new AbortController() };
      active = run;
      return load(run, 0);
    }
    async function next() {
      if (!active || active.phase === 'loading' || !active.data || active.data.next_offset === null) return active;
      return load(active, active.data.next_offset);
    }
    async function previous() {
      if (!active || active.phase === 'loading' || !active.data || active.data.offset === 0) return active;
      return load(active, active.data.offset - PAGE_SIZE);
    }
    async function retry() {
      if (!active || !['error', 'cancelled'].includes(active.phase)) return active;
      return load(active, active.requestedOffset);
    }
    return { start, next, previous, retry, cancel, clear, get state() { return active; } };
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { createPager };
  if (!root.document) return;
  const document = root.document;
  const page = document.getElementById('sinan-page');
  if (!page) return;
  const config = JSON.parse(document.getElementById('sinan-config').textContent);
  const element = id => document.getElementById('sinan-' + id);
  const number = value => value.toLocaleString('pt-BR');
  const weekLabel = value => value ? `${value.slice(0, 4)}/${value.slice(4)}` : 'Não informada';
  const classLabel = (code, disease) => code === 'unknown' ? 'Não informada' : `${code} · ${disease.classifications[code] || 'Sem descrição validada'}`;
  function cell(row, value) { const td = document.createElement('td'); td.textContent = value; row.appendChild(td); }
  function updateSource() {
    const disease = config.diseases[element('disease').value];
    element('source').href = disease.source_url;
    element('source').textContent = `Ministério da Saúde · SINAN · ${disease.label}`;
    element('dictionary').href = disease.dictionary_url;
    element('dictionary').textContent = `dicionário de ${disease.label}`;
    element('legacy-layout').hidden = !disease.legacy_layout;
  }
  function render(run) {
    const running = run?.phase === 'loading';
    element('submit').disabled = running;
    element('spinner').hidden = !running;
    element('search-icon').hidden = running;
    element('submit-label').textContent = running ? 'Consultando...' : 'Consultar';
    element('cancel').hidden = !running;
    element('retry').hidden = !run || Boolean(run.data) || !['error', 'cancelled'].includes(run.phase);
    element('form').setAttribute('aria-busy', String(running));
    const hasStatus = run && (run.phase !== 'ready' || run.data?.limit_reached);
    element('status').hidden = !hasStatus || Boolean(run?.data);
    element('page-status').hidden = !hasStatus || !run?.data;
    element('results').hidden = !run?.data;
    element('indicators').hidden = !run?.data?.records.length;
    if (!run) {
      ['records', 'classifications', 'weeks'].forEach(id => element(id).replaceChildren());
      element('indicators').open = false;
      return;
    }
    element('status').dataset.phase = run.phase;
    element('status').textContent = run.phase === 'loading' ? `Carregando página ${run.requestedOffset / PAGE_SIZE + 1}…`
      : run.phase === 'error' ? run.error
      : run.phase === 'cancelled' ? 'Consulta interrompida. Você pode tentar novamente.'
      : 'Limite de leitura atingido. Há registros não consultados.';
    element('page-status').textContent = element('status').textContent;
    const data = run.data;
    if (!data) return;
    const disease = config.diseases[run.disease];
    const pageNumber = data.offset / PAGE_SIZE + 1;
    element('context').textContent = `${disease.label} · ${run.city.name} / ${run.city.uf} · ${run.year}`;
    element('badge').textContent = `Página ${pageNumber}`;
    element('page-number').textContent = pageNumber;
    const prevDisabled = running || data.offset === 0;
    const nextDisabled = running || data.next_offset === null;
    element('prev').disabled = prevDisabled;
    element('next').disabled = nextDisabled;
    element('next').textContent = running ? 'Carregando…' : 'Próxima';
    element('prev-item').classList.toggle('disabled', prevDisabled);
    element('next-item').classList.toggle('disabled', nextDisabled);
    element('page-summary').textContent = data.records.length
      ? `Registros ${number(data.offset + 1)}–${number(data.offset + data.records.length)}${data.finished ? ' · Fim dos registros' : ' · Resultado parcial'}`
      : 'Nenhum registro neste filtro';
    const body = element('records'); body.replaceChildren();
    const residenceLabels = { local: 'Neste município', other: 'Outro município', unknown: 'Não informada' };
    data.records.forEach((record, index) => {
      const tr = document.createElement('tr');
      cell(tr, number(data.offset + index + 1)); cell(tr, `${run.city.name} / ${run.city.uf}`);
      cell(tr, weekLabel(record.week)); cell(tr, classLabel(record.classification, disease));
      cell(tr, residenceLabels[record.residence] || 'Não informada'); body.appendChild(tr);
    });
    if (!data.records.length) {
      const tr = document.createElement('tr'); cell(tr, `Nenhuma notificação de ${disease.label} retornada para ${run.city.name} em ${run.year}. Tente outro ano.`);
      tr.firstChild.colSpan = 5; body.appendChild(tr);
    }
    const classifications = element('classifications'); classifications.replaceChildren();
    for (const [code, count] of Object.entries(data.summary.classifications).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))) {
      const tr = document.createElement('tr'); cell(tr, classLabel(code, disease)); cell(tr, number(count)); classifications.appendChild(tr);
    }
    const weeks = element('weeks'); weeks.replaceChildren();
    const entries = Object.entries(data.summary.weeks).sort(([a], [b]) => a.localeCompare(b));
    const maximum = Math.max(1, ...entries.map(([, count]) => count));
    for (const [week, count] of entries) {
      const row = document.createElement('div'); row.className = 'sinan-week';
      const label = document.createElement('span'); label.textContent = weekLabel(week);
      const track = document.createElement('div');
      const bar = document.createElement('div'); bar.className = 'sinan-week-bar'; bar.style.width = `${100 * count / maximum}%`; bar.setAttribute('aria-hidden', 'true'); track.appendChild(bar);
      const value = document.createElement('span'); value.className = 'sinan-week-count'; value.textContent = number(count);
      row.append(label, track, value); weeks.appendChild(row);
    }
    if (!entries.length) weeks.textContent = 'Sem semana informada.';
    element('week-missing').hidden = !data.summary.unknown_week;
    element('week-missing').textContent = `${number(data.summary.unknown_week)} registro(s) sem semana informada.`;
    element('timestamp').textContent = `Consultado em ${new Date(data.retrieved_at).toLocaleString('pt-BR')}.`;
  }
  async function fetchPage(ibge, year, offset, signal, disease) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) controller.abort();
    const timer = setTimeout(abort, 55000);
    try {
      const query = new URLSearchParams({ ibge, year, offset, disease });
      const response = await fetch(`${page.dataset.endpoint}?${query}`, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'A consulta à fonte falhou.');
      return payload;
    } catch (error) {
      if (error.name === 'AbortError' && !signal.aborted) throw new Error('A fonte demorou para responder. Tente novamente.');
      if (error instanceof TypeError) throw new Error('Não foi possível conectar ao sistema. Confira a conexão e tente novamente. Se o servidor foi reiniciado, recarregue a página.');
      if (error instanceof SyntaxError) throw new Error('Não foi possível ler a resposta. Recarregue a página e confira sua sessão.');
      throw error;
    } finally {
      clearTimeout(timer); signal.removeEventListener('abort', abort);
    }
  }
  const pager = createPager({ fetchPage, onUpdate: render });
  element('form').addEventListener('submit', event => {
    event.preventDefault();
    const queryTab = element('query-tab');
    if (queryTab && root.bootstrap?.Tab) root.bootstrap.Tab.getOrCreateInstance(queryTab).show();
    const city = config.municipalities.find(item => item.ibge === element('scope').value);
    pager.start(city, Number(element('year').value), element('disease').value);
  });
  element('next').addEventListener('click', () => pager.next());
  element('prev').addEventListener('click', () => pager.previous());
  element('retry').addEventListener('click', () => pager.retry());
  element('cancel').addEventListener('click', () => pager.cancel());
  element('saved-tab')?.addEventListener('show.bs.tab', () => pager.cancel());
  ['disease', 'scope', 'year'].forEach(id => element(id).addEventListener('change', () => { pager.clear(); updateSource(); }));
  element('clear').addEventListener('click', () => { pager.clear(); element('form').reset(); updateSource(); });
  root.addEventListener('pagehide', () => pager.cancel());
})(typeof window !== 'undefined' ? window : globalThis);
