const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/piloto-os-equipamentos.js'), 'utf8');

function browser({automatic = true, readOnly = false, loading = false, saved = false,
                  situation = 'MONITORADO E LARVICIDA APLICADO'} = {}) {
  const elements = {};
  const listeners = {};
  const field = (value = '') => ({value, dataset: {},
    addEventListener(type, fn) { this[type] = fn; }});
  const status = field(situation);
  elements['os-form-main'] = {
    dataset: {equipmentReadonly: String(readOnly)}, querySelector: () => status,
  };
  const groups = {};
  for (const [id, suffix, kind] of [['drone_id', 'pulv', 'pulverizacao'],
                                  ['drone_monitoramento_id', 'monit', 'monitoramento']]) {
    const options = ['', '1', '2'].map(value => ({value, dataset: value ? {
      serie: `serie-${value}`, modelo: `modelo-${value}`, renomacao: `prefixo-${value}`,
      anatel: `anatel-${value}`, anac: `anac-${value}`,
    } : {}}));
    const select = field(automatic || saved ? '1' : '');
    select.dataset.autoSelected = String(automatic);
    Object.defineProperty(select, 'selectedOptions', {get: () => options.filter(o => o.value === select.value)});
    const fields = {};
    for (const name of ['serie', 'modelo', 'renomacao', 'anatel', 'anac']) {
      const part = ['anatel', 'anac'].includes(name) ? `registro_${name}` : name;
      fields[name] = elements[`drone_${part}_${suffix}`] = field(saved ? `registrado-${name}` : '');
    }
    fields.prefixo = elements[`prefixo_${kind}`] = field(saved ? 'prefixo-registrado' : '');
    const note = elements[`drone-${suffix}-autofill-note`] = {hidden: false};
    elements[id] = select;
    groups[kind] = {select, fields, note, change(value) { select.value = value; select.change(); }};
  }
  vm.runInNewContext(source, {document: {
    readyState: loading ? 'loading' : 'complete', getElementById: id => elements[id],
    addEventListener(type, fn) { listeners[type] = fn; },
  }});
  return {...groups, listeners, status, changeSituation(value) { status.value = value; status.change?.(); }};
}

test('unique suggestions populate all drone identifiers, including ANATEL and ANAC', () => {
  const b = browser();
  for (const group of [b.pulverizacao, b.monitoramento]) {
    assert.equal(group.fields.serie.value, 'serie-1');
    assert.equal(group.fields.modelo.value, 'modelo-1');
    assert.equal(group.fields.renomacao.value, 'prefixo-1');
    assert.equal(group.fields.prefixo.value, 'prefixo-1');
    assert.equal(group.fields.anatel.value, 'anatel-1');
    assert.equal(group.fields.anac.value, 'anac-1');
    assert.equal(group.note.hidden, false);
  }
});

test('saved identification survives load and switching away and back', () => {
  const b = browser({automatic: false, saved: true});
  const p = b.pulverizacao;
  assert.equal(p.fields.serie.value, 'registrado-serie');
  assert.equal(p.fields.prefixo.value, 'prefixo-registrado');
  p.change('2');
  assert.equal(p.fields.serie.value, 'serie-2');
  p.change('1');
  assert.equal(p.fields.serie.value, 'registrado-serie');
  assert.equal(p.fields.prefixo.value, 'prefixo-registrado');
  assert.equal(p.note.hidden, true);
});

test('manual changes refresh metadata and an explicit blank stays blank', () => {
  const b = browser();
  b.pulverizacao.change('2');
  assert.equal(b.pulverizacao.fields.anac.value, 'anac-2');
  assert.equal(b.pulverizacao.note.hidden, true);
  b.pulverizacao.change('');
  assert.ok(Object.values(b.pulverizacao.fields).every(node => node.value === ''));
  b.changeSituation('NENHUM VOO REALIZADO');
  b.changeSituation('MONITORADO E LARVICIDA APLICADO');
  assert.equal(b.pulverizacao.select.value, '');
});

test('no flight removes only automatic suggestions and restores them when applicable', () => {
  const b = browser();
  b.changeSituation('APENAS MONITORADO');
  assert.equal(b.pulverizacao.select.value, '');
  assert.equal(b.monitoramento.select.value, '1');
  b.changeSituation('NENHUM VOO REALIZADO');
  assert.equal(b.monitoramento.select.value, '');
  b.changeSituation('MONITORADO E LARVICIDA APLICADO');
  assert.equal(b.pulverizacao.select.value, '1');
  assert.equal(b.monitoramento.select.value, '1');
  assert.equal(b.pulverizacao.fields.serie.value, 'serie-1');
  const historical = browser({automatic: false, saved: true});
  historical.changeSituation('NENHUM VOO REALIZADO');
  assert.equal(historical.pulverizacao.select.value, '1');
  assert.equal(historical.pulverizacao.fields.serie.value, 'registrado-serie');
});

test('ambiguous equipment remains empty until a manual selection', () => {
  const b = browser({automatic: false});
  assert.equal(b.pulverizacao.select.value, '');
  assert.equal(b.pulverizacao.fields.serie.value, '');
  b.pulverizacao.change('2');
  assert.equal(b.pulverizacao.fields.serie.value, 'serie-2');
});

test('read-only forms remain unchanged and initialization waits for the DOM', () => {
  const readOnly = browser({readOnly: true, saved: true});
  assert.equal(readOnly.pulverizacao.fields.serie.value, 'registrado-serie');
  assert.equal(readOnly.pulverizacao.select.change, undefined);
  const b = browser({loading: true});
  assert.equal(b.pulverizacao.fields.serie.value, '');
  b.listeners.DOMContentLoaded();
  assert.equal(b.pulverizacao.fields.serie.value, 'serie-1');
});
