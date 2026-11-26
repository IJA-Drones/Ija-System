(() => {
  'use strict';

  const form = document.getElementById('os-opening-form');
  if (!form) return;

  const droneSelect = form.querySelector('#drone_id');
  const card = form.querySelector('[data-os-open-equipment]');
  const photo = card.querySelector('[data-os-equipment-photo]');
  const icon = card.querySelector('[data-os-equipment-icon]');

  function showEquipment() {
    const option = droneSelect.selectedOptions[0];
    card.hidden = !option?.value;
    if (card.hidden) return;

    card.querySelectorAll('[data-os-equipment-field]').forEach(field => {
      field.textContent = option.dataset[field.dataset.osEquipmentField];
    });
    const photoUrl = option.dataset.photo;
    photo.hidden = !photoUrl;
    icon.hidden = Boolean(photoUrl);
    if (photoUrl) {
      photo.src = photoUrl;
      photo.alt = `Imagem do modelo ${option.dataset.model}`;
    }
  }

  form.querySelector('[data-change-drone]').addEventListener('click', () => {
    droneSelect.focus();
    if (typeof droneSelect.showPicker === 'function') droneSelect.showPicker();
  });
  droneSelect.addEventListener('change', showEquipment);
  showEquipment();
})();
