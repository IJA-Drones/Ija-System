(() => {
  'use strict';

  const form = document.getElementById('os-opening-form');
  if (!form) return;

  const equipmentSelect = form.querySelector('#equipamento_id');
  const card = form.querySelector('[data-os-open-equipment]');
  const photo = card.querySelector('[data-os-equipment-photo]');
  const icon = card.querySelector('[data-os-equipment-icon]');

  function showEquipment() {
    const option = equipmentSelect.selectedOptions[0];
    card.hidden = !option?.value;
    if (card.hidden) return;

    card.querySelectorAll('[data-os-equipment-field]').forEach(field => {
      field.textContent = option.dataset[field.dataset.osEquipmentField];
    });
    const isVehicle = option.dataset.vehicle === 'true';
    card.querySelector('#os-selected-title').textContent = isVehicle ? 'Dados do veículo' : 'Dados do drone';
    card.querySelector('[data-os-serial-label]').textContent = isVehicle ? 'Placa' : 'Nº de série';
    icon.querySelector('i').className = isVehicle ? 'bi bi-truck' : 'bi bi-airplane-engines';
    const photoUrl = option.dataset.photo;
    photo.hidden = !photoUrl;
    icon.hidden = Boolean(photoUrl);
    if (photoUrl) {
      photo.src = photoUrl;
      photo.alt = `Imagem do modelo ${option.dataset.model}`;
    }
  }

  form.querySelector('[data-change-equipment]')?.addEventListener('click', () => {
    equipmentSelect.focus();
    if (typeof equipmentSelect.showPicker === 'function') equipmentSelect.showPicker();
  });
  equipmentSelect.addEventListener('change', showEquipment);
  showEquipment();
})();
