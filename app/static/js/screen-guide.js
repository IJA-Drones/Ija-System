/* Azul tutorials on authorized real screens. Never submits business controls. */
(() => {
  'use strict';
  const FIELD_HINTS = {
    tipo_visita: 'Escolha o tipo de visita conforme o atendimento. Culex é apenas uma das opções. Quando Aedes exigir o tipo de imóvel, preencha também esse campo.',
    tipo_imovel: 'Informe o tipo de imóvel correspondente ao atendimento. As opções de foco acompanham essa escolha.',
    foco: 'Selecione o foco da ação. Para uma solicitação de quadra, escolha QUADRA aqui. O tratamento e monitoramento de quadra é definido automaticamente.',
    tipo_operacao: 'Confira a operação. Quando o foco for QUADRA, o sistema seleciona o tratamento e monitoramento de quadra.',
    altura_voo: 'Confira a altura de voo com a equipe responsável antes de informar este campo.',
    distrito_administrativo: 'Informe o distrito administrativo correspondente ao local.',
    apoio_cet: 'Indique se o atendimento precisa de apoio de trânsito.',
    observacao: 'Registre as informações que ajudam a equipe a compreender o atendimento. Para quadras, descreva os limites e as referências do trecho.',
    observacoes: 'Inclua as informações complementares necessárias para compreender este cadastro.',
    cep: 'Informe o CEP e confira os campos de endereço retornados. Complete ou corrija o endereço antes de confirmar.',
    logradouro: 'Informe somente o nome da rua, avenida ou praça. O número deve ficar no campo próprio.',
    numero: 'Informe o número do endereço. Quando o local não tiver número, use S/N.',
    complemento: 'Inclua referências, bloco, acesso ou outro complemento necessário.',
    bairro: 'Confira o bairro correspondente ao endereço.',
    cidade: 'Confira o município correspondente ao endereço.',
    uf: 'Confira a sigla do estado.',
    latitude: 'Confira a latitude calculada para o endereço. Use as opções da própria tela quando precisar ajustar a localização.',
    longitude: 'Confira a longitude calculada para o endereço. Use as opções da própria tela quando precisar ajustar a localização.',
    data: 'Informe a data correspondente à atividade desta tela e confira o período permitido.',
    data_agendamento: 'Confira a data prevista para o atendimento.',
    hora: 'Informe o horário previsto para a atividade.',
    hora_agendamento: 'Confira o horário previsto para o atendimento.',
    status: 'Use a situação correspondente ao registro ou ao filtro que deseja consultar. Filtrar a lista não altera a situação dos registros.',
    busca: 'Informe uma referência para localizar os registros disponíveis no seu acesso.',
    q: 'Informe o termo que deseja procurar e aplique os filtros da tela.',
    empresa_id: 'Confira a empresa antes de consultar ou registrar informações.',
    empresa_slug: 'Confira a empresa antes de consultar ou registrar informações.',
    prefeitura_id: 'Confira a prefeitura. Os registros apresentados continuam sujeitos aos vínculos do seu usuário.',
    uvis_responsavel_id: 'Escolha a unidade responsável pelo atendimento entre as opções permitidas.',
    equipe_id: 'Confira a equipe responsável antes de continuar.',
    piloto_id: 'Confira o piloto vinculado à operação.',
    cliente_id: 'Localize e confira o cliente relacionado a este registro.',
    valor: 'Informe o valor e confira os demais dados antes de confirmar o lançamento.',
    vencimento: 'Confira a data de vencimento. Ela não comprova que houve pagamento.',
    data_pagamento: 'Informe a data efetiva do pagamento quando essa informação se aplicar ao registro.',
    criadouro: 'Registre o criadouro identificado na execução. Essa informação é separada do foco QUADRA da solicitação.',
  };
  const clean = text => String(text || '').replace(/\s+/g, ' ').trim();
  const normalize = text => clean(text).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function permitted(element) {
    if (!element || element.disabled || element.getAttribute?.('aria-disabled') === 'true') return false;
    if (element.closest?.('[data-ti-blocked="true"],[aria-disabled="true"],[inert],fieldset[disabled]')) return false;
    const denied = element.closest?.('[data-ti-allowed="false"]');
    return !denied || (denied.tagName === 'FORM' && !!element.closest?.('[data-ti-independent="true"],[data-bs-toggle="tab"]'));
  }
  function fieldBody(name, type, readonly, scope = {}) {
    if (readonly && !['latitude', 'longitude', 'tipo_operacao'].includes(name)) return 'Este campo é apresentado para conferência. A edição não está disponível aqui.';
    if (name === 'observacao' && !scope.request) return 'Registre as informações complementares necessárias para compreender este cadastro ou lançamento.';
    if (name === 'numero' && !scope.address) return 'Informe o número solicitado pelo cadastro ou documento desta tela.';
    if (name === 'tipo_visita' && !scope.culex) return 'Escolha o tipo de visita conforme o atendimento, entre as opções disponíveis nesta tela.';
    if (name === 'foco' && !scope.quadra) return 'Selecione o foco compatível com o tipo de visita e com as opções disponíveis no formulário.';
    if (name === 'tipo_operacao' && !scope.quadra) return 'Confira a operação correspondente ao serviço desta tela.';
    if (FIELD_HINTS[name]) return FIELD_HINTS[name];
    if (type === 'file') return 'Escolha o arquivo solicitado nesta tela e confira o formato e o limite indicados. O guia não anexa nem envia arquivos.';
    if (type === 'password') return 'Preencha este campo diretamente no formulário. O guia não lê o conteúdo digitado.';
    if (['date', 'datetime-local', 'month', 'time'].includes(type)) return 'Confira a data ou o horário correspondente a este registro ou filtro.';
    if (['checkbox', 'radio'].includes(type)) return 'Confira a opção indicada e marque apenas o que corresponde à atividade ou ao registro.';
    if (type === 'select-one' || type === 'select-multiple') return 'Escolha entre as opções disponíveis para este campo. Outros campos podem aparecer conforme a seleção.';
    if (['number', 'range'].includes(type)) return 'Informe a quantidade ou o valor solicitado e confira a unidade e os limites mostrados na tela.';
    return 'Preencha ou confira este campo conforme o rótulo e as orientações do formulário. Revise a informação antes de confirmar.';
  }
  function actionBody(label, method) {
    const text = normalize(label);
    if (/excluir|remover|cancelar|aprovar|rejeitar|concluir|finalizar|fechar caixa|reabrir/.test(text)) return 'Confira o registro e a situação antes de usar esta ação. Ela pode alterar informações reais e continua sujeita às permissões e validações do sistema.';
    if (/salvar|enviar|cadastrar|registrar|confirmar|gravar|publicar|importar/.test(text)) return 'Revise os campos e os avisos antes de confirmar. O guia apenas explica o controle; quem realiza o envio ou a gravação é você.';
    if (/exportar|baixar|relatorio|imprimir/.test(text)) return 'Confira o período e os filtros antes de usar esta opção. O conteúdo disponível depende do seu acesso.';
    if (method === 'get' || /filtrar|buscar|pesquisar|consultar|aplicar filtro/.test(text)) return 'Use este controle para atualizar a consulta com os filtros informados.';
    return 'Use esta opção quando precisar da função indicada. O guia não aciona este controle automaticamente.';
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {permitted, fieldBody, actionBody};
  if (typeof window === 'undefined' || typeof document === 'undefined' || window.AzulScreenGuide) return;

  let active = null;
  let config = null;
  try { config = JSON.parse(document.querySelector('[data-screen-guide-config]')?.textContent || 'null'); } catch (_) { /* Public pages retain their contextual guide. */ }
  const groups = Array.isArray(config?.groups) ? config.groups : [];
  const functions = new Map(groups.flatMap(group => group.functions.map(item => [item.id, item])));
  const samePage = item => { const url = new URL(item.url, location.origin); return url.origin === location.origin && url.pathname === location.pathname; };
  const companion = () => document.querySelector('[data-azul-help]')?.azulCompanion;
  const EXCLUDE = '.screen-guide-ui,[data-guide],[data-guide-open],[data-screen-guide-open],.azul-training-dialog,.main-footer';
  function excluded(element) {
    if (element.closest(EXCLUDE)) return true;
    const chat = element.closest('[data-azul-help],[data-azul-companion]');
    return !!chat && !chat.classList.contains('azul-page');
  }
  function visible(element) {
    if (!element || !element.isConnected || excluded(element) || !permitted(element)) return false;
    if (element.hidden || element.closest('[hidden],[aria-hidden="true"],.d-none')) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden' && !!element.getClientRects().length;
  }
  function labelFor(element) {
    let label = clean(element.getAttribute('aria-label'));
    if (!label && element.labels?.length) label = clean(element.labels[0].textContent);
    if (!label && element.matches('input,select,textarea')) {
      const previous = element.previousElementSibling;
      if (previous?.matches('label,.form-label')) label = clean(previous.textContent);
      let parent = element.parentElement;
      for (let i = 0; !label && parent && i < 3 && parent.tagName !== 'FORM'; i++, parent = parent.parentElement) {
        const labels = [...parent.children].filter(child => child.matches('label,.form-label'));
        if (labels.length === 1) label = clean(labels[0].textContent);
      }
    }
    if (!label) label = clean(element.getAttribute('placeholder') || element.getAttribute('title'));
    if (!label && element.matches('input[type="submit"],input[type="reset"],input[type="button"]')) label = clean(element.getAttribute('value'));
    if (!label && element.matches('button,a,summary')) label = clean(element.textContent);
    if (!label && /^[a-z_]{1,45}$/i.test(element.getAttribute('name') || '')) label = clean(element.getAttribute('name').replace(/_/g, ' '));
    if (label && element.matches('input[type="radio"],input[type="checkbox"]')) {
      let parent = element.parentElement;
      for (let i = 0; parent && i < 4 && parent.tagName !== 'FORM'; i++, parent = parent.parentElement) {
        const group = [...parent.children].filter(child => child.matches('label,.form-label') && child !== element.labels?.[0]);
        if (group.length === 1) { label = clean(group[0].textContent) + ': ' + label; break; }
      }
    }
    return label.slice(0, 150);
  }
  function pageContent() {
    return document.querySelector('.modal.show,dialog[open]') || document.querySelector('#appContent,.app-content,#mobileApp,#app,main,[role="main"]') || document.body;
  }
  function collectSteps() {
    const content = pageContent();
    const heading = [...content.querySelectorAll('h1,h2')].find(visible);
    const title = clean(heading?.textContent) || clean(document.title.split('|')[0]) || 'Esta tela';
    const steps = [{title, body: 'Este guia acompanha a tela real e os controles visíveis no seu acesso. Você pode usar a página e avançar no seu ritmo. Nenhum campo é preenchido e nenhuma ação é confirmada pelo guia.', target: heading || content, kind: 'Nesta tela'}];
    const seen = new Set();
    const add = (title, body, target, kind) => {
      const key = kind + ':' + normalize(title);
      if (!title || seen.has(key) || !visible(target)) return;
      seen.add(key); steps.push({title, body, target, kind});
    };
    for (const element of content.querySelectorAll('input,select,textarea,button,a[href],summary,[role="tab"],table,.leaflet-container,.maplibregl-map,.mapboxgl-map,iframe')) {
      if (!visible(element) || element.matches('input[type="hidden"]')) continue;
      if (element.matches('input:not([type="submit"]):not([type="reset"]):not([type="button"]),select,textarea')) {
        const name = element.getAttribute('name') || '';
        const label = labelFor(element);
        const form = element.closest('form') || content;
        const options = selector => [...form.querySelectorAll(selector)].map(option => normalize(option.textContent));
        const scope = {request: !!form.querySelector('[name="tipo_visita"]'), address: !!form.querySelector('[name="logradouro"],[name="cep"]'), quadra: options('[name="foco"] option').includes('quadra'), culex: options('[name="tipo_visita"] option').includes('culex')};
        add(label, fieldBody(name, element.type, element.readOnly, scope), element, element.closest('form[method="get"],form:not([method])') ? 'Filtro ou campo' : 'Campo');
      } else if (element.matches('table')) {
        add('Confira os registros da lista', 'Use os cabeçalhos para identificar as informações da tabela. Abra apenas os registros disponíveis para sua conta e confira o contexto antes de usar uma ação da linha.', element, 'Lista');
      } else if (element.matches('.leaflet-container,.maplibregl-map,.mapboxgl-map')) {
        add('Explore o mapa', 'Use os controles de camadas, busca e navegação disponíveis nesta tela. Confira o local antes de usar qualquer ação de cadastro ou edição. O guia não move nem desenha no mapa.', element, 'Mapa');
      } else if (element.matches('iframe')) {
        if (element.id === 'trainingVideoPlayer') add('Reproduza o vídeo', 'Use os controles do reprodutor para assistir. A lista da central e os botões anterior e próximo permitem escolher outro vídeo autorizado.', element, 'Reprodutor');
        else add(labelFor(element) || 'Consulte o conteúdo incorporado', 'Use os controles disponíveis neste conteúdo. As ações de consulta ou edição continuam sujeitas às permissões da própria tela.', element, 'Conteúdo');
      } else {
        let label = labelFor(element);
        if (element.closest('tbody,.list-group')) {
          const action = label.match(/^(abrir|editar|visualizar|detalhes|ver|excluir|cancelar|aprovar|rejeitar|concluir|finalizar|exportar|baixar|imprimir|anexos|m[ií]dias)\b/i);
          if (!action) continue;
          label = action[0];
        }
        if (!label || label.length > 120 || element.closest('thead')) continue;
        const method = normalize(element.closest('form')?.getAttribute('method') || '');
        add(label, actionBody(label, method), element, element.matches('a') ? 'Atalho' : 'Controle');
      }
    }
    if (steps.length === 1) steps.push({title: 'Encontre as opções da tela', body: 'Confira as informações apresentadas e use os atalhos e o menu permitidos para sua conta. Se abrir outra tela ou um formulário, você pode iniciar o guia novamente para acompanhar os controles dela.', target: content, kind: 'Consulta'});
    steps.push({title: 'Revisão concluída', body: 'Você percorreu os controles visíveis desta tela. Revise os dados e use as ações da página somente quando estiver pronto. Para outra tela ou aba, abra o guia novamente; o passo a passo acompanha o que estiver disponível.', target: null, kind: 'Concluir'});
    return steps;
  }
  function close(restore = true) {
    if (!active) return;
    const previous = active; active = null;
    previous.request?.abort(); companion()?.stopVoice();
    previous.panel.remove(); previous.focus.remove();
    if (restore && previous.opener?.isConnected) previous.opener.focus();
  }
  function position() {
    if (!active) return;
    const {panel, focus, steps, index} = active;
    if (active.mode === 'picker') {
      focus.hidden = false;
      panel.style.left = Math.max(8, (innerWidth - panel.offsetWidth) / 2) + 'px';
      panel.style.top = Math.max(8, (innerHeight - panel.offsetHeight) / 2) + 'px';
      return;
    }
    const target = steps[index]?.target;
    if (!target?.isConnected || !visible(target)) {
      focus.hidden = true;
      panel.style.left = Math.max(12, (innerWidth - panel.offsetWidth) / 2) + 'px';
      panel.style.top = Math.max(12, (innerHeight - panel.offsetHeight) / 2) + 'px';
      return;
    }
    const rect = target.getBoundingClientRect();
    const left = Math.max(6, rect.left - 6), top = Math.max(6, rect.top - 6);
    const right = Math.min(innerWidth - 6, rect.right + 6), bottom = Math.min(innerHeight - 6, rect.bottom + 6);
    focus.hidden = right <= left || bottom <= top;
    Object.assign(focus.style, {left: left + 'px', top: top + 'px', width: Math.max(0, right - left) + 'px', height: Math.max(0, bottom - top) + 'px'});
    const width = panel.offsetWidth, height = panel.offsetHeight;
    const clampX = x => Math.max(12, Math.min(innerWidth - width - 12, x));
    const clampY = y => Math.max(12, Math.min(innerHeight - height - 12, y));
    const candidates = [[rect.right + 16, rect.top], [rect.left - width - 16, rect.top], [rect.left, rect.bottom + 16], [rect.left, rect.top - height - 16], [innerWidth - width - 16, innerHeight - height - 16]];
    const score = ([x, y]) => Math.max(0, Math.min(x + width, right) - Math.max(x, left)) * Math.max(0, Math.min(y + height, bottom) - Math.max(y, top));
    const points = candidates.map(([x, y]) => [clampX(x), clampY(y)]).sort((a, b) => score(a) - score(b));
    panel.style.left = points[0][0] + 'px'; panel.style.top = points[0][1] + 'px';
  }
  function render(scroll = true) {
    if (!active) return;
    const {panel, steps, index} = active, step = steps[index];
    panel.querySelector('[data-screen-guide-progress]').textContent = `${index + 1} de ${steps.length}`;
    panel.querySelector('[data-screen-guide-kind]').textContent = step.kind;
    panel.querySelector('h2').textContent = step.title;
    panel.querySelector('[data-screen-guide-body]').textContent = step.body;
    if (active.mode === 'ai') {
      companion()?.stopVoice();
      const audio = panel.querySelector('[data-screen-guide-audio]'); audio.replaceChildren();
      companion()?.attachSpeech(audio, step.speech, 'Ouvir etapa');
    }
    panel.querySelector('[data-screen-guide-prev]').disabled = index === 0;
    panel.querySelector('[data-screen-guide-next]').textContent = index === steps.length - 1 ? 'Concluir' : 'Próximo';
    const list = panel.querySelector('[data-screen-guide-list]'); list.replaceChildren();
    steps.forEach((item, i) => {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = `${i + 1}. ${item.title}`;
      if (i === index) button.setAttribute('aria-current', 'step');
      button.addEventListener('click', () => { if (active) { active.index = i; render(); } });
      list.append(button);
    });
    if (scroll && step.target && step.target !== pageContent()) step.target.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'auto'});
    if (!step.target) { active.focus.hidden = true; panel.style.left = Math.max(12, (innerWidth - panel.offsetWidth) / 2) + 'px'; panel.style.top = Math.max(12, (innerHeight - panel.offsetHeight) / 2) + 'px'; }
    else position();
  }
  function advance(direction) {
    if (!active) return;
    const current = active.steps[active.index];
    if (direction > 0 && active.index === active.steps.length - 1) { close(); return; }
    if (active.mode === 'ai') {
      let next = active.index + direction;
      while (next > 0 && next < active.steps.length - 1 && !visible(active.steps[next].target)) next += direction;
      active.index = Math.max(0, Math.min(active.steps.length - 1, next)); render(); return;
    }
    const updated = collectSteps();
    const found = updated.findIndex(item => item.target === current.target && item.title === current.title);
    active.steps = updated;
    active.index = Math.max(0, Math.min(updated.length - 1, (found >= 0 ? found : active.index) + direction));
    render();
  }
  function openScreen(opener) {
    close(false);
    document.body.classList.remove('sidebar-open');
    for (const root of document.querySelectorAll('[data-azul-help],[data-azul-companion]')) {
      root.azulCompanion?.stop(); root.dispatchEvent(new CustomEvent('azul:close'));
    }
    const panel = document.createElement('aside'); panel.className = 'screen-guide-ui screen-guide-panel';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'false'); panel.setAttribute('aria-labelledby', 'screenGuideTitle');
    panel.innerHTML = '<header><strong>Guia prático</strong><span data-screen-guide-progress></span><button type="button" data-screen-guide-close aria-label="Fechar guia prático">×</button></header><span class="screen-guide-kind" data-screen-guide-kind></span><h2 id="screenGuideTitle"></h2><p data-screen-guide-body></p><details><summary>Ver todas as etapas</summary><div data-screen-guide-list></div></details><footer><button type="button" data-screen-guide-prev>Voltar</button><button type="button" data-screen-guide-next>Próximo</button></footer>';
    const focus = document.createElement('div'); focus.className = 'screen-guide-ui screen-guide-focus'; focus.setAttribute('aria-hidden', 'true');
    const host = document.querySelector('.modal.show,dialog[open]') || document.body; host.append(focus, panel);
    active = {panel, focus, opener, steps: collectSteps(), index: 0};
    panel.querySelector('[data-screen-guide-close]').addEventListener('click', () => close());
    panel.querySelector('[data-screen-guide-prev]').addEventListener('click', () => advance(-1));
    panel.querySelector('[data-screen-guide-next]').addEventListener('click', () => advance(1));
    panel.querySelector('details').addEventListener('toggle', position);
    render(); panel.querySelector('[data-screen-guide-next]').focus({preventScroll: true});
  }
  function openPicker(opener) {
    if (!config) { openScreen(opener); return; }
    openScreen(opener);
    const state = active, panel = state.panel; state.mode = 'picker'; state.steps = [];
    panel.classList.add('screen-guide-picker'); panel.setAttribute('aria-modal', 'true');
    state.focus.className = 'screen-guide-ui screen-guide-picker-shade'; state.focus.hidden = false;
    state.focus.removeAttribute('style');
    state.focus.addEventListener('click', () => close());
    panel.innerHTML = '<header><div><strong>Aprender na prática</strong><small>Azul · tutoriais do sistema</small></div><span>Aprenda no seu ritmo</span><button type="button" data-screen-guide-close aria-label="Fechar tutoriais">×</button></header><div class="screen-guide-picker-content"><section class="screen-guide-hero"><div><span class="screen-guide-eyebrow">GUIA PRÁTICO · COM A AZUL</span><h2 id="screenGuideTitle">Aprenda fazendo,<br>com Azul.</h2><p>Escolha um módulo e uma função. A Azul mostra o passo a passo nos controles da tela real e responde às suas dúvidas.</p><div class="screen-guide-context"><b>TELAS REAIS</b><span>Etapas conforme suas permissões</span></div></div><div class="screen-guide-hero-mascot azul-help"><div data-practical-mascot></div><span>Vamos dar o primeiro passo?</span></div></section><label class="screen-guide-search">Encontre o que deseja aprender<input type="search" placeholder="Buscar módulo ou função…" data-practical-search></label><nav class="screen-guide-area-filters" aria-label="Áreas dos tutoriais" data-practical-areas></nav><div class="screen-guide-breadcrumb" data-practical-breadcrumb></div><div class="screen-guide-module-grid" aria-live="polite" data-practical-cards></div><p class="screen-guide-note">A Azul orienta usando inteligência artificial. Os dados dos formulários permanecem na tela; você revisa e confirma as ações.</p></div>';
    const source = document.querySelector('[data-azul-help] .azul-drone');
    if (source) panel.querySelector('[data-practical-mascot]').append(source.cloneNode(true));
    panel.querySelector('[data-screen-guide-close]').addEventListener('click', () => close());
    let selected = null, areaFilter = '';
    const list = panel.querySelector('[data-practical-cards]'), areas = panel.querySelector('[data-practical-areas]'), breadcrumb = panel.querySelector('[data-practical-breadcrumb]');
    const search = panel.querySelector('[data-practical-search]');
    function card(title, description, footer, onClick) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'screen-guide-module-card';
      const icon = document.createElement('span'); icon.className = 'screen-guide-card-icon'; icon.textContent = '▤'; icon.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('span'), heading = document.createElement('strong'), detail = document.createElement('small'), meta = document.createElement('em');
      heading.textContent = title; detail.textContent = description; meta.textContent = footer; copy.append(heading, detail, meta);
      const arrow = document.createElement('b'); arrow.textContent = '↗'; arrow.setAttribute('aria-hidden', 'true');
      button.append(icon, copy, arrow); button.addEventListener('click', onClick); return button;
    }
    function draw() {
      const term = normalize(search.value);
      const filtered = groups.filter(group => !areaFilter || group.area === areaFilter).map(group => ({...group, functions: group.functions.filter(item => normalize(group.title + ' ' + group.area_title + ' ' + item.title).includes(term))})).filter(group => group.functions.length);
      areas.replaceChildren(); list.replaceChildren(); breadcrumb.replaceChildren();
      for (const [id, title] of [['','Todas as áreas'], ...new Map(groups.map(group => [group.area, group.area_title]))]) {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = title; button.setAttribute('aria-pressed', String(id === areaFilter));
        button.addEventListener('click', () => { areaFilter = id; selected = null; draw(); }); areas.append(button);
      }
      if (!filtered.length) { const empty = document.createElement('p'); empty.textContent = groups.length ? 'Nenhum tutorial corresponde à busca.' : 'Nenhum tutorial da Azul está disponível para seu acesso. As permissões da Azul e dos módulos são definidas pelo administrador.'; list.append(empty); position(); return; }
      const chosen = selected && filtered.find(group => group.id === selected);
      if (selected) {
        const back = document.createElement('button'); back.type = 'button'; back.textContent = '← Todos os módulos'; back.addEventListener('click', () => { selected = null; search.value = ''; draw(); }); breadcrumb.append(back);
      }
      if (chosen) {
        const heading = document.createElement('h3'); heading.textContent = chosen.title + ' · escolha uma função'; breadcrumb.append(heading);
        for (const item of chosen.functions) list.append(card(item.title, 'A Azul explica os campos e controles desta função e ajuda com suas dúvidas.', samePage(item) ? 'Iniciar com a Azul nesta tela' : 'Abrir a tela e iniciar com a Azul', () => startTutorial(item, opener)));
      } else if (!selected) {
        for (const group of filtered) list.append(card(group.title, 'Tutoriais: ' + group.functions.slice(0,3).map(item => item.title).join(' · '), group.functions.length + (group.functions.length === 1 ? ' função disponível' : ' funções disponíveis') + ' · ' + group.area_title, () => { selected = group.id; draw(); }));
      } else { const empty = document.createElement('p'); empty.textContent = 'Nenhuma função deste módulo corresponde à busca.'; list.append(empty); }
      position();
    }
    search.addEventListener('input', draw);
    panel.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const focusable = [...panel.querySelectorAll('button,input')].filter(element => !element.disabled && element.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    draw(); search.focus({preventScroll: true}); position();
  }
  function startTutorial(item, opener) {
    const url = new URL(item.url, location.origin);
    if (url.origin !== location.origin || !functions.has(item.id)) return;
    if (!samePage(item)) {
      const pending = {id: item.id, key: config.chat_key, expires: Date.now() + 300000};
      try { sessionStorage.setItem('azul-practical-start', JSON.stringify(pending)); } catch (_) { /* The destination offers an explicit start button. */ }
      url.searchParams.set('guia_pratico', item.id); location.assign(url.pathname + url.search); return;
    }
    generate(item, opener);
  }
  function snapshot() {
    return collectSteps().slice(1, -1).filter(item => !item.target?.closest('tbody,.list-group')).map(item => {
      if (item.kind !== 'Controle' && item.kind !== 'Atalho') return item;
      const action = item.title.match(/^(abrir|editar|visualizar|detalhes|ver|excluir|cancelar|aprovar|rejeitar|concluir|finalizar|exportar|baixar|imprimir|anexos|m[ií]dias|buscar|filtrar|pesquisar|consultar|salvar|enviar|cadastrar|registrar|confirmar|gravar|publicar|importar|novo|nova|voltar|anterior|pr[oó]ximo)\b/i);
      return action ? {...item, title:action[0]} : null;
    }).filter(Boolean).slice(0, 60).map((item, index) => ({...item, id:'c' + index}));
  }
  async function askAi(state, action, message, controls) {
    if (config?.url !== '/api/azul/ajuda') throw new Error('A integração da Azul não está disponível nesta tela.');
    const controller = new AbortController(); state.request?.abort(); state.request = controller;
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(config.url, {method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''},
        body: JSON.stringify({intent: 'practical_guide', tutorial: state.tutorial.id, tutorial_action: action,
          message, page: state.tutorial.url, chat_key: config.chat_key, history: state.history || [],
          controls: controls.map(({id, title, body, kind}) => ({id, title, body, kind}))})});
      const result = await response.json();
      if (!response.ok || result.mode !== 'ia') throw new Error(result.answer || 'Não foi possível preparar o tutorial com a Azul.');
      return result;
    } finally { clearTimeout(timeout); if (state.request === controller) state.request = null; }
  }
  async function generate(item, opener) {
    openScreen(opener); const state = active; state.mode = 'loading'; state.tutorial = item;
    const controls = snapshot(), panel = state.panel;
    panel.innerHTML = '<header><strong>Guia prático · Azul</strong><button type="button" data-screen-guide-close aria-label="Fechar tutorial">×</button></header><h2 id="screenGuideTitle"></h2><p role="status">A Azul está preparando as etapas desta tela…</p>';
    panel.querySelector('h2').textContent = item.title; state.steps = []; position();
    panel.querySelector('[data-screen-guide-close]').addEventListener('click', () => close());
    const message = 'Quero um tutorial de como usar ' + item.title + ' no sistema Oceano Azul.';
    try {
      if (!controls.length) throw new Error('Não há controles disponíveis nesta tela para orientar este tutorial. Abra o formulário ou registro que deseja consultar.');
      const result = await askAi(state, 'plan', message, controls);
      if (active !== state) return;
      const linked = (result.steps || []).map(step => ({...step, target: controls.find(control => control.id === step.control)?.target, kind: 'Azul · etapa'})).filter(step => visible(step.target));
      if (!linked.length) throw new Error('Os controles desta tela mudaram. Escolha o tutorial novamente para atualizar as etapas.');
      openScreen(opener); const guide = active; guide.mode = 'ai'; guide.tutorial = item;
      guide.history = [{role:'user', content:message}, {role:'assistant', content:(result.answer + '\n' + linked.map(step => step.title + ': ' + step.body).join('\n')).slice(0, 3000)}];
      guide.steps = [{title:item.title, body:result.answer, speech:result.speech, target:null, kind:'Azul · tutorial'}, ...linked,
        {title:'Confira antes de confirmar', body:'Revise as informações e os avisos da tela. A Azul apenas orienta; as ações continuam sob sua confirmação e as permissões do sistema.', target:null, kind:'Concluir'}];
      const tools = document.createElement('div'); tools.className = 'screen-guide-ai';
      tools.innerHTML = '<div data-screen-guide-audio></div><button type="button" data-practical-refresh>Atualizar etapas com a Azul</button><form data-practical-question><label>Dúvida nesta função<textarea rows="2" maxlength="1200" required placeholder="Pergunte à Azul sobre esta etapa"></textarea></label><button type="submit">Perguntar à Azul</button></form><div data-practical-answer role="status"></div><button type="button" data-practical-choose>Escolher outro tutorial</button>';
      guide.panel.querySelector('footer').before(tools);
      tools.querySelector('[data-practical-choose]').addEventListener('click', () => openPicker(opener));
      tools.querySelector('[data-practical-refresh]').addEventListener('click', () => generate(item, opener));
      tools.querySelector('form').addEventListener('submit', event => askQuestion(event, guide));
      render();
    } catch (error) {
      if (active !== state) return;
      const text = panel.querySelector('p'); text.textContent = error.name === 'AbortError' ? 'A Azul demorou para responder. Tente novamente.' : error.message;
      const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'screen-guide-function'; retry.textContent = 'Tentar novamente'; retry.addEventListener('click', () => generate(item, opener));
      const choose = document.createElement('button'); choose.type = 'button'; choose.className = 'screen-guide-function'; choose.textContent = 'Escolher outro tutorial'; choose.addEventListener('click', () => openPicker(opener)); panel.append(retry, choose); position();
    }
  }
  async function askQuestion(event, state) {
    event.preventDefault(); event.stopPropagation();
    const form = event.target, input = form.querySelector('textarea'), button = form.querySelector('button');
    const message = input.value.trim(); if (!message || state.request) return;
    const output = state.panel.querySelector('[data-practical-answer]'); output.textContent = 'A Azul está respondendo…'; button.disabled = true;
    try {
      const result = await askAi(state, 'question', message, snapshot());
      if (active !== state) return;
      const text = document.createElement('p'); text.textContent = result.answer;
      const audio = document.createElement('div'); output.replaceChildren(text, audio);
      companion()?.attachSpeech(audio, result.speech, 'Ouvir resposta');
      state.history.push({role:'user', content:message}, {role:'assistant', content:result.answer.slice(0, 3000)}); state.history = state.history.slice(-6); input.value = '';
    } catch (error) { if (active === state) output.textContent = error.name === 'AbortError' ? 'A resposta demorou. Tente novamente.' : error.message; }
    finally { button.disabled = false; if (active === state) position(); }
  }
  document.addEventListener('click', event => {
    const opener = event.target.closest('[data-screen-guide-open],[data-guide-open]');
    if (!opener || !opener.matches('button,a') || opener.disabled) return;
    event.preventDefault(); event.stopImmediatePropagation(); openPicker(opener);
  }, true);
  document.addEventListener('keydown', event => { if (active && event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close(); } }, true);
  document.addEventListener('azul:access-changed', () => close(false), true);
  document.addEventListener('shown.bs.modal', () => { if (active && !active.mode) openScreen(active.opener); });
  document.addEventListener('hidden.bs.modal', () => close(false));
  document.addEventListener('shown.bs.tab', () => window.AzulScreenGuide.refresh());
  window.addEventListener('pagehide', () => close(false));
  window.addEventListener('hashchange', () => close(false));
  let queued = false;
  function schedulePosition() { if (!active || queued) return; queued = true; requestAnimationFrame(() => { queued = false; position(); }); }
  window.addEventListener('resize', schedulePosition); document.addEventListener('scroll', schedulePosition, true);
  window.AzulScreenGuide = {open:openPicker, inspect:openScreen, close, refresh() { if (active && !active.mode) { active.steps = collectSteps(); active.index = 0; render(); } }};
  function resume() {
    const id = new URLSearchParams(location.search).get('guia_pratico'); const item = functions.get(id);
    if (!item || !samePage(item)) return;
    let pending = null;
    try { pending = JSON.parse(sessionStorage.getItem('azul-practical-start') || 'null'); sessionStorage.removeItem('azul-practical-start'); } catch (_) { /* No auto-generation without the explicit start marker. */ }
    if (pending?.id === id && pending.key === config.chat_key && pending.expires > Date.now()) generate(item);
    else openPicker();
  }
  if (document.readyState === 'loading' || document.readyState === 'interactive') document.addEventListener('DOMContentLoaded', resume, {once:true}); else resume();
})();
