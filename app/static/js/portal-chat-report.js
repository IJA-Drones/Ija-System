(() => {
  const root = document.querySelector('[data-portal-chat]');
  const form = document.getElementById('portalCidadaoForm');
  if (!root || !form) return;
  const report = root.querySelector('[data-report]');
  const slot = root.querySelector('[data-report-form]');
  const review = root.querySelector('[data-report-review]');
  const title = root.querySelector('[data-report-title]');
  const help = root.querySelector('[data-report-help]');
  const progress = root.querySelector('[data-report-progress]');
  const feedback = root.querySelector('[data-report-feedback]');
  const next = root.querySelector('[data-report-next]');
  const back = root.querySelector('[data-report-back]');
  const exit = root.querySelector('[data-report-exit]');
  const chatForm = root.querySelector('form');
  const chatSections = [root.querySelector('.portal-chat-messages'), root.querySelector('.portal-chat-links'), chatForm];
  const originalParent = form.parentNode;
  const originalNext = form.nextSibling;
  const fieldsets = Array.from(form.querySelectorAll(':scope > fieldset'));
  const groups = [
    [fieldsets[0], form.querySelector('#portalCidadaoDependentFields')],
    [fieldsets[1]], [fieldsets[2]], [fieldsets[3]],
    [form.querySelector('.portal-cidadao-consent')]
  ];
  const titles = ['O que você encontrou?', 'Onde está o problema?', 'Como podemos identificar você?', 'Quer acrescentar detalhes?', 'Revise antes de enviar'];
  const hints = ['Escolha a ocorrência, o tipo de local e o foco.', 'Preencha e confira o endereço. Você também pode usar o CEP ou sua localização.', 'Use os campos abaixo. Estes dados vão diretamente ao sistema, sem passar pela IA.', 'Descreva a situação e, se quiser, anexe até cinco fotos ou vídeos.', 'Confira os dados e confirme o uso das informações. O registro só acontece ao clicar em Confirmar e enviar.'];
  let step = 0;
  let active = false;
  let sending = false;
  let wrappers = [];
  const placeholder = document.createElement('div');
  placeholder.className = 'portal-cidadao-feedback';
  placeholder.hidden = true;
  const note = document.createElement('p');
  note.textContent = 'Seu relato está aberto no assistente. Você pode continuar aqui sem perder os dados.';
  const restore = document.createElement('button');
  restore.type = 'button';
  restore.className = 'btn btn-outline-primary';
  restore.textContent = 'Usar formulário nesta página';
  restore.addEventListener('click', () => {
    if (sending) return;
    leave();
    root.querySelector('.portal-chat-panel').hidden = true;
    root.querySelector('.portal-chat-toggle').setAttribute('aria-expanded', 'false');
    form.querySelector('[data-tipo-visita]').focus();
  });
  placeholder.append(note, restore);
  form.before(placeholder);

  function showStep(index) {
    step = index;
    wrappers.forEach((wrapper, i) => { wrapper.hidden = i !== step; });
    title.textContent = titles[step];
    help.textContent = hints[step];
    progress.textContent = `Etapa ${step + 1} de 5`;
    review.hidden = step !== 4;
    if (step === 4) renderReview();
    back.hidden = step === 0;
    next.textContent = step === 4 ? 'Confirmar e enviar' : 'Continuar';
    feedback.textContent = '';
    title.focus();
    report.scrollTop = 0;
  }

  function renderReview() {
    review.replaceChildren();
    const labels = {tipo_visita:'Ocorrência',tipo_imovel:'Tipo de local',foco:'Foco',logradouro:'Logradouro',numero:'Número',complemento:'Complemento',bairro:'Bairro',cidade:'Cidade',uf:'UF',cep:'CEP',nome:'Nome',cpf:'CPF',rg:'RG',telefone:'Telefone',descricao:'Descrição'};
    const data = new FormData(form);
    const list = document.createElement('dl');
    for (const [key, label] of Object.entries(labels)) {
      const value = data.get(key);
      if (!value) continue;
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd'); dd.textContent = value;
      list.append(dt, dd);
    }
    const files = Array.from(form.querySelector('[name="midias"]').files || []);
    const media = document.createElement('p');
    media.textContent = files.length ? 'Anexos: ' + files.map(file => file.name).join(', ') : 'Sem anexos.';
    review.append(list, media);
    // Summary precedes consent in the visual and keyboard order.
    form.insertBefore(review, wrappers[4]);
  }

  function validStep() {
    if (step === 0 && !form.querySelector('[name="tipo_visita"]').value) {
      feedback.textContent = 'Escolha o tipo de ocorrência.';
      return false;
    }
    if (step === 3 && form.querySelector('[name="midias"]').files.length > 5) {
      feedback.textContent = 'Envie no máximo cinco arquivos.';
      return false;
    }
    for (const input of wrappers[step].querySelectorAll('input, select, textarea')) {
      if (!input.disabled && !input.checkValidity()) { input.reportValidity(); return false; }
    }
    return true;
  }

  function start() {
    if (active || form.dataset.submitting === "true" || chatForm.querySelector('button').disabled) return;
    active = true;
    root.querySelector('.portal-chat-panel').hidden = false;
    root.querySelector('.portal-chat-toggle').setAttribute('aria-expanded', 'true');
    chatSections.forEach(element => { element.hidden = true; });
    wrappers = groups.map(nodes => {
      const wrapper = document.createElement('div');
      wrapper.className = 'portal-report-step';
      nodes[0].before(wrapper);
      nodes.forEach(node => wrapper.append(node));
      return wrapper;
    });
    form.dataset.chatReport = 'true';
    form.querySelector('.portal-cidadao-form-footer').hidden = true;
    form.querySelector('#portalCidadaoFeedback').hidden = true;
    slot.append(form);
    placeholder.hidden = false;
    // Keep the summary inside the form alongside its final consent step.
    wrappers[4].before(review);
    report.hidden = false;
    next.hidden = false;
    exit.disabled = false;
    showStep(0);
  }

  function leave() {
    if (sending) return;
    report.append(review);
    review.hidden = true;
    wrappers.forEach(wrapper => { wrapper.replaceWith(...wrapper.childNodes); });
    originalParent.insertBefore(form, originalNext);
    form.querySelector('.portal-cidadao-form-footer').hidden = false;
    delete form.dataset.chatReport;
    delete form.dataset.reportConfirmed;
    report.hidden = true;
    placeholder.hidden = true;
    chatSections.forEach(element => { element.hidden = false; });
    active = false;
    chatForm.querySelector('textarea').focus();
  }
  function lock(value) {
    sending = value;
    next.disabled = back.disabled = exit.disabled = restore.disabled = value;
  }
  next.addEventListener('click', () => {
    if (sending || !validStep()) return;
    if (step < 4) { showStep(step + 1); return; }
    lock(true);
    feedback.textContent = 'Enviando relato. Aguarde a confirmação do sistema…';
    form.dataset.reportConfirmed = 'true';
    form.requestSubmit();
    // Existing validation may prevent sending (e.g. invalid fields in prior steps).
    if (form.dataset.submitting !== 'true') lock(false);
  });
  back.addEventListener('click', () => { if (!sending) showStep(Math.max(0, step - 1)); });
  exit.addEventListener('click', leave);
  root.querySelector('[data-start-report]').addEventListener('click', start);
  root.addEventListener('portal:start-report', start);
  form.addEventListener('portal:report-success', event => {
    if (!active) return;
    lock(false);
    wrappers.forEach(wrapper => { wrapper.hidden = true; });
    review.hidden = true;
    title.textContent = 'Relato registrado';
    help.textContent = 'Guarde seu protocolo. A equipe responsável fará a triagem.';
    progress.textContent = 'Concluído';
    feedback.textContent = `Protocolo: ${event.detail.protocolo}`;
    next.hidden = back.hidden = true;
    title.focus();
  });
  form.addEventListener('portal:report-error', event => {
    if (!active) return;
    lock(false);
    form.querySelector('#portalCidadaoFeedback').hidden = true;
    const field = Object.keys(event.detail.errors)[0];
    const index = groups.findIndex(nodes => nodes.some(node => Array.from(node.querySelectorAll('[name]')).some(input => input.name === field)));
    if (index >= 0) showStep(index);
    feedback.textContent = event.detail.message;
  });
})();
