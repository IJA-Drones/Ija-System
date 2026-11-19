/* Practical guidance on the rendered page. Never fills, clicks or submits business controls. */
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
    previous.panel.remove(); previous.focus.remove();
    if (restore && previous.opener?.isConnected) previous.opener.focus();
  }
  function position() {
    if (!active) return;
    const {panel, focus, steps, index} = active;
    const target = steps[index].target;
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
    const updated = collectSteps();
    const found = updated.findIndex(item => item.target === current.target && item.title === current.title);
    active.steps = updated;
    active.index = Math.max(0, Math.min(updated.length - 1, (found >= 0 ? found : active.index) + direction));
    render();
  }
  function open(opener) {
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
  document.addEventListener('click', event => {
    const opener = event.target.closest('[data-screen-guide-open],[data-guide-open]');
    if (!opener || !opener.matches('button,a') || opener.disabled) return;
    event.preventDefault(); event.stopImmediatePropagation(); open(opener);
  }, true);
  document.addEventListener('keydown', event => { if (active && event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close(); } }, true);
  document.addEventListener('azul:access-changed', () => close(false), true);
  document.addEventListener('shown.bs.modal', () => { if (active) open(active.opener); });
  document.addEventListener('hidden.bs.modal', () => close(false));
  document.addEventListener('shown.bs.tab', () => window.AzulScreenGuide.refresh());
  window.addEventListener('pagehide', () => close(false));
  window.addEventListener('hashchange', () => close(false));
  let queued = false;
  function schedulePosition() { if (!active || queued) return; queued = true; requestAnimationFrame(() => { queued = false; position(); }); }
  window.addEventListener('resize', schedulePosition); document.addEventListener('scroll', schedulePosition, true);
  window.AzulScreenGuide = {open, close, refresh() { if (active) { active.steps = collectSteps(); active.index = 0; render(); } }};
})();
