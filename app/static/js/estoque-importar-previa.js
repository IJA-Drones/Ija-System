(() => {
  'use strict';
  const rows = Array.from(document.querySelectorAll('[data-import-row]'));
  const size = document.getElementById('import-page-size');
  const onlyErrors = document.getElementById('import-only-errors');
  const previous = document.getElementById('import-prev');
  const next = document.getElementById('import-next');
  const confirm = document.getElementById('confirmar-importacao');
  if (!size || !onlyErrors || !previous || !next) return;
  let page = 0;
  function render() {
    const filtered = rows.filter(row => !onlyErrors.checked || row.dataset.hasErrors === 'true');
    const perPage = Number(size.value);
    const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
    page = Math.max(0, Math.min(page, totalPages - 1));
    rows.forEach(row => { row.hidden = true; });
    filtered.slice(page * perPage, (page + 1) * perPage).forEach(row => { row.hidden = false; });
    previous.disabled = page === 0;
    next.disabled = page + 1 >= totalPages;
    document.getElementById('import-page-label').textContent = `Página ${page + 1} de ${totalPages}`;
    document.getElementById('import-page-count').textContent = filtered.length
      ? `${page * perPage + 1}–${Math.min((page + 1) * perPage, filtered.length)} de ${filtered.length} linhas`
      : 'Nenhuma pendência encontrada';
  }
  size.addEventListener('change', () => { page = 0; render(); });
  onlyErrors.addEventListener('change', () => { page = 0; render(); });
  previous.addEventListener('click', () => { page -= 1; render(); });
  next.addEventListener('click', () => { page += 1; render(); });
  document.querySelectorAll('.stock-import-quantity').forEach(input => {
    input.addEventListener('input', () => {
      if (confirm) {
        confirm.disabled = true;
        confirm.textContent = 'Valide as quantidades para continuar';
      }
    });
  });
  render();
})();
