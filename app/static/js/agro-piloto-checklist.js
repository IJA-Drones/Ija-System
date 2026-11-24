(() => {
  const form = document.getElementById('agro-weekly-checklist');
  if (!form) return;

  const { saved, draft } = JSON.parse(document.getElementById('agro-checklist-data').textContent);
  const canSave = form.dataset.canSave === 'true';
  const sections = [...form.querySelectorAll('[data-checklist-section]')];
  const submit = form.querySelector('[type="submit"]');

  function syncSubmit() {
    if (submit) submit.disabled = !sections.some(section => section.querySelector('select')?.value);
  }

  function updateObservation(group) {
    const defective = [...group.querySelectorAll('input[type="radio"][value="0"]:checked')]
      .some(input => !input.closest('[data-tank-row][hidden]'));
    const container = group.querySelector('[data-inspection-observation]');
    const input = container.querySelector('textarea');
    container.hidden = !defective;
    input.disabled = !canSave || !defective;
    input.required = canSave && defective;
  }

  for (const section of sections) {
    const select = section.querySelector('select');
    if (!select) continue;
    const fields = section.querySelector('[data-checklist-fields]');
    const groups = [...fields.querySelectorAll('[data-inspection-group]')];
    const inputs = [...fields.querySelectorAll('input, textarea')];
    const tank = section.querySelector('[data-tank-row]');
    const status = section.querySelector('[data-saved-status]');
    const drafts = new Map();
    let activeId = select.value;

    const posted = draft?.[section.dataset.checklistSection];
    if (posted?.id) drafts.set(posted.id, posted.fields);

    function showSelection() {
      const record = saved[activeId];
      const values = drafts.get(activeId) ?? record?.fields ?? {};
      fields.hidden = !activeId;
      fields.disabled = !activeId || !canSave;
      status.textContent = record ? `Salvo nesta semana em ${record.savedAt} por ${record.responsible}.` : '';

      for (const input of inputs) {
        const value = values[input.name];
        if (input.type === 'radio') {
          input.checked = value === input.value || value === (input.value === '1');
        } else {
          input.value = value ?? '';
        }
      }
      if (tank) {
        tank.hidden = select.selectedOptions[0]?.dataset.hasTank !== 'true';
        for (const radio of tank.querySelectorAll('input')) radio.disabled = tank.hidden;
        section.querySelector('[data-structure-title]').textContent = tank.hidden
          ? 'Trem de pouso e câmeras' : 'Tanque, trem de pouso e câmeras';
      }
      groups.forEach(updateObservation);
      syncSubmit();
    }

    select.addEventListener('change', () => {
      if (activeId && canSave) {
        drafts.set(activeId, Object.fromEntries(inputs
          .filter(input => input.type !== 'radio' || input.checked)
          .map(input => [input.name, input.value])));
      }
      activeId = select.value;
      showSelection();
    });
    fields.addEventListener('change', event => {
      if (event.target.type === 'radio') updateObservation(event.target.closest('[data-inspection-group]'));
    });
    showSelection();
  }

  if (!canSave) return;
  const canvas = form.querySelector('#signature-pad');
  const context = canvas.getContext('2d');
  const input = form.elements.assinatura_piloto;
  const error = form.querySelector('[data-signature-error]');
  let pointer = null;
  let drew = false;

  context.strokeStyle = '#1a365d';
  context.lineWidth = 3;
  context.lineCap = 'round';
  context.lineJoin = 'round';

  if (input.value) {
    const previous = new Image();
    const value = input.value;
    previous.onload = () => {
      if (input.value === value && pointer === null) context.drawImage(previous, 0, 0);
    };
    previous.src = value;
  }

  function point(event) {
    const rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * canvas.width / rect.width,
      (event.clientY - rect.top) * canvas.height / rect.height];
  }

  canvas.addEventListener('pointerdown', event => {
    if (pointer !== null || event.button !== 0) return;
    pointer = event.pointerId;
    drew = false;
    canvas.setPointerCapture(pointer);
    context.beginPath();
    context.moveTo(...point(event));
  });
  canvas.addEventListener('pointermove', event => {
    if (pointer !== event.pointerId) return;
    context.lineTo(...point(event));
    context.stroke();
    drew = true;
  });
  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    canvas.addEventListener(type, event => {
      if (pointer !== event.pointerId) return;
      pointer = null;
      if (drew) {
        input.value = canvas.toDataURL('image/png');
        error.hidden = true;
      }
    });
  }
  form.querySelector('[data-clear-signature]').addEventListener('click', () => {
    context.clearRect(0, 0, canvas.width, canvas.height);
    input.value = '';
    error.hidden = true;
  });
  form.addEventListener('submit', event => {
    if (!input.value) {
      event.preventDefault();
      error.hidden = false;
      error.scrollIntoView({ block: 'nearest' });
    }
  });
})();
