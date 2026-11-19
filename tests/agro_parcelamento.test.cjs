const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('app/static/js/agro-parcelamento.js','utf8');
function page(modeValue, value, quantity) {
  const field = value => ({value, addEventListener(name, fn) { this[name] = fn; }});
  const mode=field(modeValue), amount=field(value), count=field(quantity), label={}, summary={};
  mode.closest = () => ({querySelector: selector => selector.includes('quantidade') ? count : amount});
  vm.runInNewContext(source,{document:{getElementById: id => ({modo_parcelamento:mode,'valor-parcelamento-label':label,'parcelamento-resumo':summary})[id]}});
  return {mode,amount,count,label,summary};
}
test('changing mode updates label and total without replacing input',()=>{
 const p=page('dividir','120,00','12');
 assert.match(p.summary.textContent,/12 parcela\(s\) de R\$\s10,00/);
 p.mode.value='repetir';p.mode.change();
 assert.match(p.label.textContent,/cada parcela/);
 assert.match(p.summary.textContent,/Total: R\$\s1\.440,00/);
 assert.equal(p.amount.value,'120,00');
 p.count.value='6';p.count.input();
 assert.match(p.summary.textContent,/Total: R\$\s720,00/);
});
test('division preserves cents and formatted currency is accepted',()=>{
 const p=page('dividir','R$ 100,00','3');
 assert.match(p.summary.textContent,/1 parcela\(s\) de R\$\s33,34 e 2 de R\$\s33,33/);
});
test('invalid count does not show a misleading total',()=>{
 const p=page('repetir','120,00','121');
 assert.match(p.summary.textContent,/Informe o valor/);
});
