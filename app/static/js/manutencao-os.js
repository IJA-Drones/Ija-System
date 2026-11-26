(() => {
  'use strict';
  const form = document.getElementById('os-manutencao-form');
  if (!form) return;
  const catalog = new Map(JSON.parse(document.getElementById('os-parts-catalog').textContent).map(part => [String(part.id), part]));
  const status = document.getElementById('os-save-status');
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
    if (row.dataset.partRow !== 'repair') return;
    row.querySelector('[data-part-code]').value = part?.codigo || '';
    row.querySelector('[data-part-balance]').textContent = part ? `${part.saldo} un.` : '—';
    const requested = Number(row.querySelector('[name="reparo_quantidade"]').value);
    const duplicate = select.value && [...form.querySelectorAll('[name="reparo_id"]')].filter(item => item.value === select.value).length > 1;
    const warning = row.querySelector('[data-part-warning]');
    warning.textContent = duplicate ? 'Peça repetida: ajuste a quantidade em uma única linha.' : !part ? (select.value ? 'Selecione uma peça compatível.' : '') : !part.disponivel ? 'Indisponível para conclusão.' : requested > part.saldo ? 'Saldo insuficiente para concluir.' : '';
  }
  function refreshRows() {
    for (const type of ['damaged', 'repair']) {
      form.querySelectorAll(`[data-part-row="${type}"]`).forEach((row, index) => {
        row.querySelectorAll('[data-row-number]').forEach(number => { number.textContent = String(index + 1); });
        row.querySelector('[data-remove-row]').setAttribute('aria-label', `Remover peça ${type === 'damaged' ? 'avariada' : 'do reparo'} ${index + 1}`);
        row.querySelector('[data-part-code]')?.setAttribute('aria-label', `Código DJI da peça nova ${index + 1}`);
        updateRow(row);
      });
    }
  }
  form.addEventListener('click', event => {
    const add = event.target.closest('[data-add-row]');
    const remove = event.target.closest('[data-remove-row]');
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
  document.getElementById('imagens-ocorrido').addEventListener('change', event => {
    photos.forEach(url => URL.revokeObjectURL(url)); photos = [];
    const preview = document.getElementById('os-photo-preview');
    preview.querySelectorAll('[data-new-photo]').forEach(element => element.remove());
    const files = [...event.target.files];
    const invalid = files.length > 10 || files.some(file => file.size > 12 * 1024 * 1024 || !['image/jpeg', 'image/png'].includes(file.type));
    const info = document.getElementById('os-upload-status');
    info.textContent = invalid ? 'Confira os arquivos: até 10 imagens JPG ou PNG de no máximo 12 MB cada.' : `${files.length} nova(s) foto(s) selecionada(s). Serão enviadas ao salvar.`;
    info.classList.toggle('os-error', invalid);
    files.slice(0, 10).filter(file => ['image/jpeg', 'image/png'].includes(file.type)).forEach((file, index) => {
      const url = URL.createObjectURL(file); photos.push(url);
      const image = document.createElement('img'); image.src = url; image.alt = `Nova foto da avaria ${index + 1}`; image.dataset.newPhoto = ''; preview.append(image);
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
    form.querySelectorAll('[data-save-action]').forEach(button => { button.disabled = true; });
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
    form.querySelectorAll('[data-save-action]').forEach(button => { button.disabled = false; if (button.dataset.originalLabel) button.innerHTML = button.dataset.originalLabel; });
    form.querySelector('[data-submitted-action]')?.remove();
    status.textContent = dirty ? 'Alterações não salvas' : 'Confira a OS antes de salvar';
  });
  document.querySelector('.os-validation-summary')?.focus();
  refreshRows(); updateFinalStatus();
})();
