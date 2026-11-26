(() => {
  const prefeitura = document.getElementById('estoque-prefeitura');
  const groups = document.querySelectorAll('[data-compatibility-group]');
  function filter(group, clearOtherCities = false) {
    const search = group.querySelector('[data-compatibility-search]').value.trim().toLocaleLowerCase('pt-BR');
    let visible = 0;
    group.querySelectorAll('[data-compatibility-option]').forEach(option => {
      const sameCity = !prefeitura?.value || option.dataset.prefeituras.split(',').includes(prefeitura.value);
      if (clearOtherCities && !sameCity) option.querySelector('input').checked = false;
      option.hidden = !sameCity || !option.textContent.toLocaleLowerCase('pt-BR').includes(search);
      if (!option.hidden) visible++;
    });
    group.querySelector('[data-compatibility-empty]').hidden = visible > 0;
  }
  groups.forEach(group => {
    group.querySelector('[data-compatibility-search]').addEventListener('input', () => filter(group));
    // Enter in a search field filters the list; it must not save the piece.
    group.querySelector('[data-compatibility-search]').addEventListener('keydown', event => {
      if (event.key === 'Enter') event.preventDefault();
    });
    filter(group);
  });
  prefeitura?.addEventListener('change', () => groups.forEach(group => filter(group, true)));
})();
