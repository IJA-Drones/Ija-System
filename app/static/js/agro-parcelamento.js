(() => {
  const mode = document.getElementById('modo_parcelamento');
  if (!mode) return;
  const form = mode.closest('form');
  const amount = form.querySelector('input[name="valor"]');
  const count = form.querySelector('input[name="quantidade_parcelas"]');
  const label = document.getElementById('valor-parcelamento-label');
  const summary = document.getElementById('parcelamento-resumo');
  const money = cents => (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  function update() {
    const repeat = mode.value === 'repetir';
    label.textContent = repeat ? 'Valor de cada parcela *' : 'Valor total *';
    const raw = amount.value.replace(/R\$|\s/g, '').replace(/\./g, '').replace(',', '.');
    const cents = Math.round(Number(raw) * 100);
    const n = Number(count.value);
    if (!Number.isSafeInteger(cents) || cents <= 0 || !Number.isInteger(n) || n < 1 || n > 120) {
      summary.textContent = 'Informe o valor e a quantidade para conferir o total.';
      return;
    }
    const base = repeat ? cents : Math.floor(cents / n);
    const remainder = repeat ? 0 : cents % n;
    const total = repeat ? cents * n : cents;
    if (remainder) {
      summary.textContent = `${remainder} parcela(s) de ${money(base + 1)} e ${n - remainder} de ${money(base)}. Total: ${money(total)}.`;
    } else {
      summary.textContent = `${n} parcela(s) de ${money(base)}. Total: ${money(total)}.`;
    }
  }
  [mode, amount, count].forEach(el => {
    el.addEventListener('input', update);
    el.addEventListener('change', update);
  });
  update();
})();
