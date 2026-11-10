/* An isolated practice room. All actions change only this document's memory. */
(() => {
  const app = document.getElementById('tutorialApp');
  const flyer = document.querySelector('[data-flyer]');
  const spotlight = document.querySelector('[data-spotlight]');
  const mascot = document.getElementById('tutorialDrone').innerHTML;
  const lessons = JSON.parse(document.getElementById('tutorialCatalog').textContent);
  let lesson = null, index = 0, automatic = false, timer = null, reactionTimer = null;
  let renderVersion = 0;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const post = payload => { if (parent !== window) parent.postMessage(payload, '*'); };
  const current = () => lesson?.steps[index];
  const active = action => current()?.action === action;
  const actionButton = (action, label, classes = '') => `<button type="button" class="practice-button ${classes}" data-action="${action}" data-target="${action}" ${active(action) ? '' : 'disabled'}>${escape(label)}</button>`;
  function choice(action, label, value, selected) {
    return `<label class="practice-field">${escape(label)}<select data-action="${action}" data-target="${action}" ${active(action) ? '' : 'disabled'}><option value="">Selecione uma opção</option><option value="demo" ${selected ? 'selected' : ''}>${escape(value)}</option></select></label>`;
  }
  const badge = '<span class="practice-badge">DADOS FICTÍCIOS</span>';
  const note = '<p class="practice-note">Simulação de aprendizagem. Nenhum cadastro real é consultado ou alterado.</p>';
  function stopAutomatic() { clearTimeout(timer); timer = null; automatic = false; }
  function notifyStep() {
    const item = current();
    post({type:'azul-tutorial:step', title:item?.title || '', speech:item?.speech || null});
  }
  function menu() {
    stopAutomatic(); lesson = null; index = 0; renderVersion++;
    flyer.hidden = true; spotlight.hidden = true;
    document.body.dataset.droneState = 'idle'; notifyStep();
    app.innerHTML = `<section class="tutorial-welcome"><div class="tutorial-hero"><div><span class="tutorial-eyebrow">GUIA PRÁTICO · MODO TREINAMENTO</span><h1>Aprenda fazendo,<br>com a Azul.</h1><p>Escolha um exercício. Eu mostro onde clicar e você pratica com informações inventadas.</p><span class="tutorial-safe">${badge} Sem envio para a operação real</span></div><div class="tutorial-hero-mascot">${mascot}<span>Vamos dar o primeiro passo?</span></div></div><div class="tutorial-catalog" aria-label="Escolha um tutorial">${lessons.map(item => `<button type="button" class="tutorial-lesson" data-lesson="${escape(item.id)}"><span class="tutorial-lesson-icon" aria-hidden="true">${escape(item.icon)}</span><span><strong>${escape(item.title)}</strong><small>${escape(item.description)}</small><em>${item.steps.length} passos · cerca de ${item.minutes} min</em></span><b aria-hidden="true">↗</b></button>`).join('')}</div><p class="tutorial-disclaimer">Esta é uma sala de prática, com telas simplificadas. Você pode errar, repetir e sair quando quiser. Os exemplos não representam pessoas, municípios ou resultados reais.</p></section>`;
  }
  function reportReview(health = false) {
    return `<article class="practice-review"><span class="tutorial-eyebrow">REVISÃO DO EXEMPLO</span><h2>${health ? 'Suspeita de adoecimento' : 'Relato de foco'} · DEMO</h2><dl><div><dt>Município</dt><dd>Município Exemplo</dd></div><div><dt>Pessoa</dt><dd>Pessoa de Exemplo · fictícia</dd></div><div><dt>Local</dt><dd>Local de Treinamento · sem endereço real</dd></div><div><dt>${health ? 'Sintomas' : 'Ocorrência'}</dt><dd>${health ? 'Febre — situação inventada' : 'Água parada · Aedes — exemplo'}</dd></div></dl><label class="practice-consent" data-target="consent"><input type="checkbox" data-action="consent" ${active('send') ? 'checked disabled' : ''}> Entendi que este exercício usa dados fictícios.</label>${actionButton('send','Enviar simulação')}${note}</article>`;
  }
  function citizen() {
    if (index < 2) return `<div class="practice-intro"><span class="tutorial-eyebrow">PORTAL DO CIDADÃO · SIMULAÇÃO</span><h1>Como podemos ajudar?</h1><p>Aprenda a comunicar um problema no ambiente.</p>${choice('city','Município','Município Exemplo',index > 0)}<div class="practice-home-cards">${actionButton('open','◎  Relatar foco','practice-large')}<div class="practice-muted-card">♡  Relatar caso suspeito<br><small>Outro caminho para situações de saúde</small></div></div></div>`;
    if (index >= 5) return reportReview();
    return `<div class="practice-intro"><span class="tutorial-eyebrow">RELATO DE FOCO · EXEMPLO</span><h1>Conte o que encontrou</h1>${choice('type','Tipo de ocorrência','Aedes',index > 2)}<section class="practice-location"><h2>Onde fica?</h2><p>Desenho ilustrativo, sem coordenadas ou endereço real.</p><div class="practice-map"><span class="practice-map-block block-a"></span><span class="practice-map-block block-b"></span><span class="practice-map-block block-c"></span><button type="button" data-action="location" data-target="location" class="practice-map-pin" aria-label="Usar local de exemplo" ${active('location') ? '' : 'disabled'}>◎<span>Local de Exemplo</span></button></div>${index > 3 ? '<p class="practice-success">✓ Local fictício selecionado</p>' : ''}</section>${index >= 4 ? `<div class="practice-summary"><strong>Exemplo preenchido</strong><p>Município Exemplo · Pessoa de Exemplo · Água parada</p></div>${actionButton('review','Revisar exemplo')}` : ''}${note}</div>`;
  }
  function health() {
    if (index === 0) return `<div class="practice-intro"><span class="tutorial-eyebrow">PORTAL DO CIDADÃO · SIMULAÇÃO</span><h1>Qual caminho usar?</h1><p>Um relato de foco descreve um problema no ambiente. Para suspeita de adoecimento, use o formulário específico.</p><div class="practice-home-cards">${actionButton('open','♡  Relatar caso suspeito','practice-large')}<div class="practice-muted-card">◎ Relatar foco<br><small>Para problemas no ambiente</small></div></div></div>`;
    if (index >= 3) return reportReview(true);
    return `<div class="practice-intro"><span class="tutorial-eyebrow">FORMULÁRIO DE SAÚDE · EXEMPLO</span><h1>Uma situação inventada</h1><div class="practice-summary"><strong>Pessoa de Exemplo</strong><p>Não há pessoa ou caso real neste exercício.</p></div>${choice('symptom','Exemplo de sintomas','Febre — exemplo fictício',index > 1)}<p class="practice-note">Uma suspeita não representa diagnóstico ou caso confirmado. Informações pessoais ficam nos campos do formulário, não no chat.</p>${index === 2 ? actionButton('review','Revisar exemplo') : ''}</div>`;
  }
  function bulletin() {
    return `<div class="practice-intro"><span class="tutorial-eyebrow">BOLETIM DE SAÚDE · SIMULAÇÃO</span><h1>Confira o contexto dos números</h1><div class="practice-filters">${choice('city','Município','Município Exemplo',index > 0)}${choice('disease','Doença','Dengue',index > 1)}${choice('period','Ano','2026',index > 2)}</div><article class="practice-chart-card"><div><h2>Números inventados</h2>${badge}</div><p>Exemplo didático. Não representa incidência, risco ou resultados reais.</p><div class="practice-chart" role="img" aria-label="Gráfico ilustrativo com valores inventados: 4, 7, 3 e 5"><div><i class="bar-1"></i><span>4</span></div><div><i class="bar-2"></i><span>7</span></div><div><i class="bar-3"></i><span>3</span></div><div><i class="bar-4"></i><span>5</span></div></div>${index === 3 ? actionButton('source','Sobre estes dados') : ''}${index === 4 ? `<div class="practice-source"><strong>Fonte: material fictício de treinamento</strong><p>Período ilustrativo: 2026. Não há dados de um município real. No boletim de verdade, confira a fonte e a data de referência.</p></div>${actionButton('finish','Conferi município, doença, período e fonte')}` : ''}</article></div>`;
  }
  function records() {
    if (index === 0) return `<div class="practice-intro"><span class="tutorial-eyebrow">IJA SYSTEM · SALA DE PRÁTICA</span><h1>Encontre ${escape(lesson.title.toLowerCase())}</h1><p>O menu reúne os recursos disponíveis. Comece pela área destacada.</p><div class="practice-empty"><span>▤</span><p>Um exemplo vai aparecer depois que você escolher a área.</p></div></div>`;
    if (index >= 3) return `<div class="practice-intro"><span class="tutorial-eyebrow">${escape(lesson.noun.toUpperCase())} · DEMO-001</span><h1>Confira antes de agir</h1><article class="practice-review"><dl>${lesson.fields.map(([key,value]) => `<div><dt>${escape(key)}</dt><dd>${escape(value)}</dd></div>`).join('')}<div><dt>Situação de exemplo</dt><dd>${escape(lesson.status)}</dd></div></dl>${index === 3 ? actionButton('details','Conferir informações') : `<div class="practice-source"><strong>Consulta de treinamento</strong><p>As informações acima são fictícias. No sistema real, confirme o registro, o escopo e as ações permitidas para sua conta.</p></div>${actionButton('finish','Concluir consulta simulada')}`}</article></div>`;
    return `<div class="practice-intro"><span class="tutorial-eyebrow">LISTA DE EXEMPLO</span><h1>${escape(lesson.title)}</h1>${choice('filter','Filtrar por situação',lesson.status,index > 1)}<div class="practice-table" role="table" aria-label="Registros fictícios"><div role="row" class="practice-table-head"><span>Identificação</span><span>Situação</span></div><button type="button" role="row" data-action="item" data-target="item" ${active('item') ? '' : 'disabled'}><span><strong>DEMO-001</strong><small>${escape(lesson.fields[0][1])}</small></span><span class="practice-status">${escape(lesson.status)} ↗</span></button><div role="row" class="practice-table-muted"><span>DEMO-002 · Outro exemplo</span><span>${escape(lesson.status)}</span></div></div>${note}</div>`;
  }
  function coach() {
    const item = current();
    return `<footer class="tutorial-coach"><div class="tutorial-coach-copy"><span class="tutorial-eyebrow">AZUL ORIENTA · PASSO ${index + 1} DE ${lesson.steps.length}</span><h2 data-coach-title>${escape(item.title)}</h2><p data-coach-body>${escape(item.body)}</p><p class="tutorial-feedback" role="status" data-feedback></p></div><div class="tutorial-coach-actions"><button type="button" class="tutorial-back" data-back ${index === 0 ? 'disabled' : ''}>← Voltar</button><button type="button" class="tutorial-demonstrate" data-demonstrate>${automatic ? 'Pausar demonstração' : 'Ver a Azul demonstrar'}</button><small>${automatic ? 'Apenas ações simuladas. Pause para praticar.' : 'Você pratica no controle destacado acima.'}</small></div></footer>`;
  }
  function complete() {
    stopAutomatic(); clearTimeout(reactionTimer); flyer.hidden = true; spotlight.hidden = true;
    document.body.dataset.droneState = 'happy'; notifyStep();
    app.innerHTML = `<section class="tutorial-complete">${mascot}<span class="tutorial-eyebrow">TREINAMENTO CONCLUÍDO</span><h1>Você deu o primeiro passo.</h1><p>Exercício: <strong>${escape(lesson.title)}</strong></p><div class="tutorial-completion-note"><strong>DEMO · Apenas uma simulação</strong><p>Nenhum relato, cadastro, pagamento ou alteração foi enviado para a operação real.</p></div><div class="tutorial-complete-actions"><button type="button" data-restart>Praticar de novo</button><button type="button" data-menu>Escolher outro tutorial</button></div><p class="tutorial-disclaimer">Quando usar o sistema real, confira o município, os dados e as permissões antes de confirmar uma ação.</p></section>`;
    app.querySelector('[data-restart]').focus();
  }
  function render() {
    clearTimeout(timer); clearTimeout(reactionTimer); const version = ++renderVersion;
    if (!current()) { complete(); return; }
    const scene = lesson.kind === 'foco' ? citizen() : lesson.kind === 'saude' ? health() : lesson.kind === 'boletim' ? bulletin() : records();
    app.innerHTML = `<section class="tutorial-shell"><header class="tutorial-top"><button type="button" data-menu>← Tutoriais</button><strong>${escape(lesson.title)}</strong>${badge}<span>${index + 1} / ${lesson.steps.length}</span></header><div class="tutorial-progress" aria-hidden="true">${lesson.steps.map((_,i) => `<span class="${i <= index ? 'is-done' : ''}"></span>`).join('')}</div><div class="tutorial-workspace"><nav class="practice-nav" aria-label="Menu simulado"><span class="practice-logo">IJA<span>System</span></span><small>AMBIENTE DE TREINAMENTO</small><span class="practice-town">Município Exemplo</span>${lesson.kind === 'lista' ? actionButton('menu',lesson.title,'practice-nav-item') : `<span class="practice-nav-item is-current">Portal do Cidadão</span>`}<p>Todos os exemplos<br>são fictícios.</p></nav><section class="practice-scene">${scene}</section></div>${coach()}</section>`;
    document.body.dataset.droneState = 'wave';
    reactionTimer = setTimeout(() => { if (version === renderVersion) document.body.dataset.droneState = 'idle'; },700);
    notifyStep();
    requestAnimationFrame(() => {
      if (version !== renderVersion) return;
      const target = app.querySelector(`[data-target="${current().target}"]`);
      target?.scrollIntoView({block:'center', inline:'nearest', behavior:'instant'});
      const focusable = target?.matches('button,select,input') ? target : target?.querySelector('input');
      focusable?.focus({preventScroll:true});
      indicate();
      if (automatic) timer = setTimeout(demonstrate,1800);
    });
  }
  function indicate() {
    const item = current();
    if (!item) return;
    const target = app.querySelector(`[data-target="${item.target}"]`);
    if (!target) return;
    const rect = target.getBoundingClientRect();
    const workspace = app.querySelector('.tutorial-workspace').getBoundingClientRect();
    if (rect.bottom < workspace.top || rect.top > workspace.bottom) { flyer.hidden = true; spotlight.hidden = true; return; }
    spotlight.hidden = false; flyer.hidden = false;
    Object.assign(spotlight.style,{left:(rect.left-5)+'px',top:(rect.top-5)+'px',width:(rect.width+10)+'px',height:(rect.height+10)+'px'});
    const right = rect.right + 10;
    const x = right + 96 < innerWidth ? right : Math.max(6,Math.min(innerWidth-102,rect.left-15));
    const y = Math.max(workspace.top+3,Math.min(workspace.bottom-78,rect.top-80));
    flyer.style.transform = `translate3d(${x}px,${y}px,0)`;
    flyer.querySelector('[data-pointer]').textContent = automatic ? 'Observe aqui' : 'Sua vez';
  }
  function advance() { clearTimeout(timer); index++; render(); }
  function demonstrate() {
    if (!automatic || !current()) return;
    const target = app.querySelector(`[data-target="${current().target}"]`);
    const control = target?.matches('select,input,button') ? target : target?.querySelector('input');
    if (!control) return;
    if (control.tagName === 'SELECT') control.value = 'demo';
    if (control.type === 'checkbox') control.checked = true;
    target.classList.add('tutorial-auto-click');
    document.body.dataset.droneState = 'think';
    timer = setTimeout(() => { if (automatic) advance(); },750);
  }
  app.addEventListener('click', event => {
    const selected = event.target.closest('[data-lesson]');
    if (selected) { lesson = lessons.find(item => item.id === selected.dataset.lesson); index = 0; stopAutomatic(); render(); return; }
    if (event.target.closest('[data-menu]')) { menu(); return; }
    if (event.target.closest('[data-restart]')) { index = 0; render(); return; }
    if (event.target.closest('[data-back]')) { stopAutomatic(); index = Math.max(0,index-1); render(); return; }
    if (event.target.closest('[data-demonstrate]')) { automatic ? stopAutomatic() : automatic = true; render(); return; }
    const action = event.target.closest('button[data-action]');
    if (action && active(action.dataset.action)) { stopAutomatic(); advance(); }
  });
  app.addEventListener('change', event => {
    const action = event.target.dataset.action;
    if (!active(action) || (event.target.type === 'checkbox' ? !event.target.checked : event.target.value !== 'demo')) return;
    stopAutomatic(); advance();
  });
  window.addEventListener('resize', indicate);
  document.addEventListener('scroll', indicate, true);
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'azul-tutorial:voice-state') return;
    if (['idle','think','speak'].includes(event.data.state) && lesson && current()) document.body.dataset.droneState = event.data.state;
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || event.defaultPrevented) return;
    event.preventDefault();
    if (parent !== window) post({type:'azul-tutorial:exit'});
    else menu();
  });
  window.addEventListener('pagehide', () => { stopAutomatic(); clearTimeout(reactionTimer); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && automatic) { stopAutomatic(); render(); } });
  menu();
})();
