const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/solicitacao-focos.js'), 'utf8');

function browser({editing = false, visit = 'Aedes', focus = 'Piscina'} = {}) {
  function element(tagName, value = '') {
    const classes = new Set(), attributes = {};
    return {tagName, value, checked: false, disabled: false, required: false, children: [],
      classList: {toggle(name, active) { if (active) classes.add(name); else classes.delete(name); }, contains: name => classes.has(name)},
      getAttribute(name) { return attributes[name]; }, setAttribute(name, value) { attributes[name] = value; },
      addEventListener(type, fn) { this[type] = fn; }, appendChild(child) { this.children.push(child); }};
  }
  const tipo = element('SELECT', visit), foco = element('SELECT');
  Object.defineProperty(foco, 'innerHTML', {set() { this.children = []; }});
  Object.defineProperty(foco, 'value', {
    get() { return this.children.find(item => item.selected)?.value || ''; },
    set(value) { this.children.forEach(item => { item.selected = item.value === value; }); },
  });
  const initial = element('OPTION', focus === 'QUADRA' ? '' : focus); initial.selected = true; foco.appendChild(initial);
  const checkbox = element('INPUT'), hidden = element('INPUT', 'QUADRA');
  checkbox.type = 'radio';
  checkbox.checked = focus === 'QUADRA'; hidden.disabled = focus !== 'QUADRA';
  const imovel = element('INPUT', 'Imovel Geral'); imovel.checked = true;
  const ops = editing ? [element('SELECT', focus === 'QUADRA' ? '' : 'Monitoramento')]
    : ['Monitoramento', 'Tratamento'].map(value => element('INPUT', value));
  if (!editing) ops[1].checked = true;
  const form = element('FORM');
  form.querySelector = selector => ({'[name="tipo_visita"]': tipo, '[name="foco"]': foco,
    '[data-quadra-focus]': checkbox, '[data-quadra-foco-hidden]': hidden,
  })[selector] || null;
  form.querySelectorAll = selector => selector === '[name="tipo_imovel"]' ? [imovel]
    : selector === '[name="tipo_operacao"]' ? ops : [];
  const window = {};
  vm.runInNewContext(source, {window, document: {
    querySelector: () => form, getElementById: () => null, createElement: tag => element(tag.toUpperCase()),
  }});
  window.initSolicitacaoFocusForm({root: 'form', catalog: {
    aedes: {'Imovel Geral': ['Piscina', 'QUADRA']}, culex: ['Corrego', 'QUADRA'], outro: ['Piscina', 'QUADRA'],
  }});
  return {tipo, foco, ops, checkbox, hidden,
    select(value) { tipo.value = value; tipo.change(); },
    chooseFocus(value) { foco.value = value; foco.change(); },
    toggleQuadra() { checkbox.checked = true; checkbox.click(); },
    submittedFocus() { return [foco, hidden].filter(field => !field.disabled).map(field => field.value); }};
}

for (const editing of [false, true]) {
  test(`Quadra is a single exclusive submitted focus (${editing ? 'edit' : 'create'})`, () => {
    const b = browser({editing});
    assert.equal(b.foco.children.some(option => option.value === 'QUADRA'), false);
    assert.deepEqual(b.submittedFocus(), ['Piscina']);
    b.toggleQuadra();
    assert.equal(b.checkbox.checked, true);
    assert.equal(b.foco.value, ''); assert.equal(b.foco.disabled, true); assert.equal(b.foco.required, false);
    assert.deepEqual(b.submittedFocus(), ['QUADRA']); assert.equal(b.tipo.value, 'Aedes');
    assert.ok(b.ops.every(item => item.disabled));
    b.toggleQuadra();
    assert.equal(b.checkbox.checked, false);
    assert.deepEqual(b.submittedFocus(), ['Piscina']); assert.equal(b.foco.required, true);
    assert.ok(b.ops.every(item => !item.disabled));
    assert.equal(editing ? b.ops[0].value : b.ops.find(item => item.checked).value, editing ? 'Monitoramento' : 'Tratamento');
    b.toggleQuadra(); assert.deepEqual(b.submittedFocus(), ['QUADRA']);
  });
}

test('changing visit keeps Quadra active but never restores an incompatible former focus', () => {
  const b = browser(); b.toggleQuadra(); b.select('Culex');
  assert.deepEqual(b.submittedFocus(), ['QUADRA']); assert.equal(b.tipo.value, 'Culex');
  b.toggleQuadra(); assert.deepEqual(b.submittedFocus(), ['']);
  b.chooseFocus('Corrego'); assert.deepEqual(b.submittedFocus(), ['Corrego']);
  assert.equal(b.foco.children.some(option => option.value === 'QUADRA'), false);
});

test('opening saved Quadra selects the radio and submits the existing canonical value', () => {
  const b = browser({editing: true, focus: 'QUADRA'});
  assert.equal(b.tipo.value, 'Aedes'); assert.equal(b.checkbox.checked, true);
  assert.deepEqual(b.submittedFocus(), ['QUADRA']);
  b.toggleQuadra(); assert.deepEqual(b.submittedFocus(), ['']);
  assert.equal(b.ops[0].value, 'Tratamento');
  b.chooseFocus('Piscina'); assert.deepEqual(b.submittedFocus(), ['Piscina']);
});

test('an existing historical focus survives opening, but not a change of visit', () => {
  const b = browser({focus: 'Foco histórico'}); assert.deepEqual(b.submittedFocus(), ['Foco histórico']);
  b.select('Culex'); assert.deepEqual(b.submittedFocus(), ['']);
  assert.equal(b.foco.children.some(option => option.value === 'Foco histórico'), false);
});
