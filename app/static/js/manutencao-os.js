(() => {
  'use strict';
  const form = document.getElementById('os-manutencao-form');
  if (!form) return;
  const catalog = new Map(JSON.parse(document.getElementById('os-parts-catalog').textContent).map(part => [String(part.id), part]));
  const status = document.getElementById('os-save-status');
  const workspace = form.closest('.equipamento-manutencao-pecas-page');
  const saveActions = [...form.elements].filter(control => control.hasAttribute('data-save-action'));
  const photoInput = document.getElementById('imagens-ocorrido');
  const photoDropzone = form.querySelector('[data-photo-dropzone]');
  const photoStatus = document.getElementById('os-upload-status');
  const stageLinks = [...workspace.querySelectorAll('.os-stage-nav a')];
  let dirty = false;
  let submitting = false;
  let photos = [];
  const markDirty = () => {
    dirty = true;
    status.textContent = 'Alterações não salvas';
  };
  function updateRow(row) {
    const select = row.querySelector('[data-part-select]');
    const part = catalog.get(select.value);
    const manual = row.querySelector('[data-manual-field]');
    if (manual) manual.hidden = select.value !== 'manual';
    row.classList.toggle('is-manual', select.value === 'manual');
    const detail = row.querySelector('[data-part-detail]');
    if (detail) {
      detail.hidden = !part || (part.nome.length <= 48 && !part.serie);
      detail.textContent = part ? `${part.nome}${part.serie ? ' · S/N ' + part.serie : ''}` : '';
    }
    const compatibility = row.querySelector('[data-part-compatibility]');
    if (compatibility) {
      compatibility.value = part ? `Compatível · ${form.dataset.equipmentModel}` : select.value === 'manual' ? 'Peça informada manualmente' : select.value ? 'Verifique a peça selecionada' : 'Selecione a peça';
      compatibility.classList.toggle('is-neutral', !part);
    }
    if (row.dataset.partRow !== 'repair') return;
    row.querySelector('[data-part-code]').value = part ? part.codigo || 'Não cadastrado' : '—';
    const balance = row.querySelector('[data-part-balance]');
    balance.value = part ? `${part.saldo} un.` : '—';
    balance.classList.toggle('is-neutral', !part);
    balance.classList.toggle('is-unavailable', Boolean(part && (!part.disponivel || part.saldo === 0)));
    const quantity = row.querySelector('[name="reparo_quantidade"]');
    const requested = Number(quantity.value);
    const decrease = row.querySelector('[data-quantity-step="-1"]');
    const increase = row.querySelector('[data-quantity-step="1"]');
    if (decrease) decrease.disabled = !(requested > Number(quantity.min));
    if (increase) increase.disabled = requested >= Number(quantity.max);
    const duplicate = select.value && [...form.querySelectorAll('[name="reparo_id"]')].filter(item => item.value === select.value).length > 1;
    const warning = row.querySelector('[data-part-warning]');
    warning.textContent = duplicate ? 'Peça repetida: ajuste a quantidade em uma única linha.' : !part ? (select.value ? 'Selecione uma peça compatível.' : '') : !part.disponivel ? 'Indisponível para conclusão.' : requested > part.saldo ? 'Saldo insuficiente para concluir.' : '';
  }
  function refreshRows() {
    for (const type of ['damaged', 'repair']) {
      form.querySelectorAll(`[data-part-row="${type}"]`).forEach((row, index) => {
        row.querySelector('[data-part-select]').setAttribute('aria-label', `${type === 'damaged' ? 'Peça avariada' : 'Peça nova'} ${index + 1}`);
        row.querySelector('[data-remove-row]').setAttribute('aria-label', `Remover peça ${type === 'damaged' ? 'avariada' : 'do reparo'} ${index + 1}`);
        row.querySelector('[data-part-code]')?.setAttribute('aria-label', `Código DJI da peça nova ${index + 1}`);
        row.querySelector('[name="avariada_descricao"]')?.setAttribute('aria-label', `Descrição da avaria ${index + 1}`);
        row.querySelector('[name="reparo_observacoes"]')?.setAttribute('aria-label', `Observação da substituição ${index + 1}`);
        row.querySelector('[name="reparo_quantidade"]')?.setAttribute('aria-label', `Quantidade ${index + 1}`);
        row.querySelectorAll('[data-quantity-step]').forEach(button => {
          button.setAttribute('aria-label', `${button.dataset.quantityStep === '1' ? 'Aumentar' : 'Diminuir'} quantidade da peça ${index + 1}`);
        });
        updateRow(row);
      });
    }
  }
  function activateStage(section) {
    if (!section) return;
    stageLinks.forEach(link => {
      if (link.hash === `#${section.id}`) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    });
  }

  function revealHash(hash) {
    if (!hash) return;
    const target = document.getElementById(hash.slice(1));
    const section = target?.closest('[data-os-stage]');
    if (!section) return;
    section.open = true;
    if (target.matches('details')) target.open = true;
    activateStage(section);
  }

  workspace.addEventListener('click', event => {
    const link = event.target.closest('.os-stage-nav a, .os-validation-summary a[href^="#"]');
    if (link) revealHash(link.hash);
  });
  form.addEventListener('focusin', event => activateStage(event.target.closest('[data-os-stage]')));
  window.addEventListener('hashchange', () => revealHash(location.hash));
  revealHash(location.hash);

  function replacePhotoSelection(files) {
    const transfer = new DataTransfer();
    files.forEach(file => transfer.items.add(file));
    photoInput.files = transfer.files;
    photoInput.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function validPhoto(file) {
    return file.size <= 12 * 1024 * 1024 && ['image/jpeg', 'image/png'].includes(file.type);
  }

  photoDropzone?.addEventListener('dragover', event => {
    if (!Array.from(event.dataTransfer.types).includes('Files')) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    photoDropzone.classList.add('is-dragover');
  });
  photoDropzone?.addEventListener('dragleave', event => {
    if (!photoDropzone.contains(event.relatedTarget)) photoDropzone.classList.remove('is-dragover');
  });
  photoDropzone?.addEventListener('drop', event => {
    photoDropzone.classList.remove('is-dragover');
    if (!event.dataTransfer.files.length) return;
    event.preventDefault();
    const files = [...photoInput.files, ...event.dataTransfer.files];
    if (files.length > 10 || files.some(file => !validPhoto(file))) {
      photoStatus.textContent = 'Confira os arquivos: até 10 fotos JPG ou PNG, de no máximo 12 MB cada.';
      photoStatus.classList.add('os-error');
      return;
    }
    replacePhotoSelection(files);
  });

  form.addEventListener('click', event => {
    const add = event.target.closest('[data-add-row]');
    const remove = event.target.closest('[data-remove-row]');
    const step = event.target.closest('[data-quantity-step]');
    const photo = event.target.closest('[data-remove-photo]');
    if (event.target.closest('[data-choose-photos]')) photoInput.click();
    if (step) {
      const quantity = step.closest('[data-part-row]').querySelector('[name="reparo_quantidade"]');
      quantity.stepUp(Number(step.dataset.quantityStep));
      quantity.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (photo) {
      replacePhotoSelection([...photoInput.files].filter((file, index) => index !== Number(photo.dataset.removePhoto)));
      document.querySelector('[data-choose-photos]')?.focus();
    }
    if (add) {
      const type = add.dataset.addRow;
      const container = document.getElementById(type === 'damaged' ? 'os-damaged-rows' : 'os-repair-rows');
      if (container.children.length >= 100) { status.textContent = 'Limite de 100 peças por seção.'; return; }
      const fragment = document.getElementById(type === 'damaged' ? 'os-damaged-template' : 'os-repair-template').content.cloneNode(true);
      container.append(fragment);
      refreshRows();
      container.lastElementChild.querySelector('select').focus();
      markDirty();
    }
    if (remove) {
      const row = remove.closest('[data-part-row]');
      const type = row.dataset.partRow;
      row.remove();
      refreshRows();
      form.querySelector(`[data-add-row="${type}"]`).focus();
      markDirty();
    }
  });
  form.addEventListener('input', event => {
    markDirty();
    if (event.target.closest('[data-part-row]')) refreshRows();
  });
  form.addEventListener('change', event => {
    markDirty();
    if (event.target.closest('[data-part-row]')) refreshRows();
  });
  const finalCondition = document.getElementById('os-condicao_final');
  function updateFinalStatus() {
    document.getElementById('os-final-status').textContent = finalCondition.value === 'inapto'
      ? 'Ao concluir, o drone ficará Inativo, sem liberação para operação.'
      : finalCondition.value ? 'Ao concluir, o drone voltará ao status Ativo.' : 'A condição final define se o drone pode voltar à operação.';
  }
  finalCondition.addEventListener('change', updateFinalStatus);
  photoInput.addEventListener('change', event => {
    photos.forEach(url => URL.revokeObjectURL(url)); photos = [];
    const preview = document.getElementById('os-photo-preview');
    preview.querySelectorAll('[data-new-photo]').forEach(element => element.remove());
    const files = [...event.target.files];
    const invalid = files.length > 10 || files.some(file => !validPhoto(file));
    photoStatus.textContent = invalid ? 'Confira os arquivos: até 10 fotos JPG ou PNG, de no máximo 12 MB cada.'
      : files.length ? `${files.length} foto(s) selecionada(s). Serão enviadas ao salvar.` : '';
    photoStatus.classList.toggle('os-error', invalid);
    files.slice(0, 10).forEach((file, index) => {
      if (!validPhoto(file)) return;
      const url = URL.createObjectURL(file); photos.push(url);
      const item = document.createElement('div'); item.className = 'os-new-photo'; item.dataset.newPhoto = '';
      const image = document.createElement('img'); image.src = url; image.alt = `Nova foto da avaria ${index + 1}`;
      const remove = document.createElement('button'); remove.type = 'button'; remove.dataset.removePhoto = String(index);
      remove.setAttribute('aria-label', `Remover foto selecionada ${index + 1}`);
      const icon = document.createElement('i'); icon.className = 'bi bi-trash3'; icon.setAttribute('aria-hidden', 'true');
      remove.append(icon);
      item.append(image, remove);
      preview.insertBefore(item, preview.querySelector('[data-choose-photos]'));
    });
  });
  form.addEventListener('submit', event => {
    if (submitting) { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    submitting = true;
    const action = event.submitter?.value || 'rascunho';
    let hidden = form.querySelector('[data-submitted-action]');
    if (!hidden) { hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.name = 'acao'; hidden.dataset.submittedAction = ''; form.append(hidden); }
    hidden.value = action;
    form.setAttribute('aria-busy', 'true');
    saveActions.forEach(button => { button.disabled = true; });
    if (event.submitter) {
      event.submitter.dataset.originalLabel = event.submitter.innerHTML;
      event.submitter.replaceChildren();
      const spinner = document.createElement('span'); spinner.className = 'spinner-border spinner-border-sm me-2'; spinner.setAttribute('aria-hidden', 'true');
      event.submitter.append(spinner, action === 'concluir' ? 'Concluindo…' : 'Salvando…');
    }
    status.textContent = action === 'concluir' ? 'Concluindo OS e atualizando o estoque…' : 'Salvando rascunho…';
  });
  window.addEventListener('beforeunload', event => {
    if (dirty && !submitting) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    submitting = false;
    form.removeAttribute('aria-busy');
    saveActions.forEach(button => { button.disabled = false; if (button.dataset.originalLabel) button.innerHTML = button.dataset.originalLabel; });
    form.querySelector('[data-submitted-action]')?.remove();
    status.textContent = dirty ? 'Alterações não salvas' : 'Confira a OS antes de salvar';
  });
  document.querySelector('.os-validation-summary')?.focus();
  refreshRows(); updateFinalStatus();
})();
