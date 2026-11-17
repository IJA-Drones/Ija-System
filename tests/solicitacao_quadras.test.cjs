const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/solicitacao-focos.js'), 'utf8');
const QUADRA = 'Tratamento e monitoramento de quadra';

function browser({editing = false, visit = 'Aedes', focus = 'Piscina'} = {}) {
  function element(tagName, value = '') {
    return {tagName, value, checked: false, disabled: false, required: false,
      children: [], classList: {toggle() {}},
      setAttribute() {}, addEventListener(type, fn) { this[type] = fn; },
      appendChild(child) { this.children.push(child); child.remove = () => {
        this.children = this.children.filter(item => item !== child);
      }; }};
  }
  const tipo = element('SELECT', visit);
  const foco = element('SELECT');
  // Model native select selection, including the disabled placeholder.
  Object.defineProperty(foco, 'innerHTML', {set() { this.children = []; }});
  Object.defineProperty(foco, 'value', {
    get() { return this.children.find(item => item.selected)?.value || ''; },
    set(value) { this.children.forEach(item => { item.selected = item.value === value; }); },
  });
  const initial = element('OPTION', focus); initial.selected = true; foco.appendChild(initial);
  const imovel = element('INPUT', 'Imovel Geral'); imovel.checked = true;
  const ops = editing ? [element('SELECT', 'Monitoramento')]
    : ['Monitoramento', 'Tratamento', QUADRA].map(value => element('INPUT', value));
  if (!editing) ops[1].checked = true;
  const form = element('FORM');
  form.querySelector = selector => ({'[name="tipo_visita"]': tipo, '[name="foco"]': foco,
    '[data-quadra-foco-hidden]': form.children.find(item => item.name === 'foco'),
  })[selector] || null;
  form.querySelectorAll = selector => selector === '[name="tipo_imovel"]' ? [imovel]
    : selector === '[name="tipo_operacao"]' ? ops : [];
  const window = {};
  vm.runInNewContext(source, {window, document: {
    querySelector: () => form, getElementById: () => null, createElement: tag => element(tag.toUpperCase()),
  }});
  window.initSolicitacaoFocusForm({root: 'form', catalog: {
    aedes: {'Imovel Geral': ['Piscina']}, culex: ['Corrego'], outro: ['Piscina'],
  }});
  return {tipo, foco, ops, form, select(value) { tipo.value = value; tipo.change(); }};
}

for (const editing of [false, true]) {
  test(`Quadra visibly selects canonical focus and operation (${editing ? 'edit' : 'create'})`, () => {
    const b = browser({editing});
    b.select('Quadra');
    assert.equal(b.foco.value, 'QUADRA');
    assert.equal(b.foco.disabled, true);
    assert.equal(b.form.children.filter(item => item.name === 'foco').length, 1);
    assert.equal(b.form.children[0].value, 'QUADRA');
    assert.ok(b.ops.every(item => item.disabled));
    assert.equal(editing ? b.ops[0].value : b.ops.find(item => item.checked).value, QUADRA);
    b.select('Culex');
    assert.equal(b.foco.value, '');
    assert.equal(b.foco.disabled, false);
    assert.equal(b.form.children.length, 0);
    assert.ok(b.ops.every(item => !item.disabled));
    assert.equal(editing ? b.ops[0].value : b.ops.find(item => item.checked).value,
      editing ? 'Monitoramento' : 'Tratamento');
    b.select('Quadra');
    assert.equal(b.form.children.length, 1);
    assert.equal(b.foco.value, 'QUADRA');
  });
}

test('initial Quadra does not retain a different focus in the visible selector', () => {
  const b = browser({visit: 'Quadra', focus: 'Piscina'});
  assert.equal(b.foco.value, 'QUADRA');
  assert.equal(b.foco.children.some(option => option.value === 'Piscina'), false);
});

test('an existing historical focus survives loading, but not a change of visit', () => {
  const b = browser({focus: 'Foco histórico'});
  assert.equal(b.foco.value, 'Foco histórico');
  b.select('Culex');
  assert.equal(b.foco.value, '');
  assert.equal(b.foco.children.some(option => option.value === 'Foco histórico'), false);
});
