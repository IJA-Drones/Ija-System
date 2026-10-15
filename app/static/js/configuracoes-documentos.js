(() => {
  'use strict';
  const selector = document.getElementById('prefeitura-selector');
  selector?.addEventListener('change', () => {
    if (!selector.value) return;
    const target = new URL(selector.value, window.location.origin);
    if (target.origin === window.location.origin) window.location.assign(target.href);
  });
  const form = document.getElementById('document-settings-form');
  if (!form) return;
  const enabled = document.getElementById('watermark-enabled');
  const opacity = document.getElementById('watermark-opacity');
  const width = document.getElementById('watermark-width');
  const identify = document.getElementById('watermark-user');
  const file = document.getElementById('watermark-image');
  const remove = document.getElementById('watermark-remove');
  const preview = document.getElementById('watermark-preview');
  const image = document.getElementById('watermark-preview-image');
  const error = document.getElementById('watermark-file-error');
  const savedSource = image.getAttribute('src');
  let objectUrl = null;
  const update = () => {
    preview.hidden = !enabled.checked;
    preview.style.opacity = Number(opacity.value) / 100;
    preview.style.width = `${width.value}%`;
    document.getElementById('opacity-value').textContent = `${opacity.value}%`;
    document.getElementById('width-value').textContent = `${width.value}%`;
    document.getElementById('watermark-preview-user').hidden = !identify.checked;
    const source = remove?.checked ? null : (objectUrl || savedSource);
    image.hidden = !source;
    if (source) image.src = source;
    document.getElementById('watermark-preview-status').textContent = !enabled.checked
      ? 'Marca d’água desabilitada.'
      : (!source && !identify.checked ? 'Selecione uma imagem ou habilite a identificação do usuário.' : 'Prévia das preferências selecionadas.');
  };
  [enabled, opacity, width, identify, remove].filter(Boolean).forEach(el => el.addEventListener('input', update));
  file.addEventListener('change', () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    error.hidden = true;
    const selected = file.files[0];
    if (selected && (selected.size > 5 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp'].includes(selected.type))) {
      error.textContent = 'Selecione uma imagem PNG, JPG ou WebP de até 5 MB.';
      error.hidden = false;
      file.value = '';
    } else if (selected) {
      objectUrl = URL.createObjectURL(selected);
      if (remove) remove.checked = false;
    }
    update();
  });
  remove?.addEventListener('change', () => {
    if (remove.checked) {
      file.value = '';
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
    update();
  });
  window.addEventListener('pagehide', () => { if (objectUrl) URL.revokeObjectURL(objectUrl); });
  update();
})();
