const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/piloto-os-situacao.js'), 'utf8');

function browser({situation = '', readOnly = false, loading = false} = {}) {
  const fields = {};
  const listeners = {};
  function field(value = '') {
    return {value, disabled: readOnly, required: true, hidden: false,
      addEventListener(type, callback) { this[type] = callback; }};
  }
  fields.situacao_aplicacao = field(situation);
  fields.motivo_nao_realizacao = field();
  const observations = ['larva_visualizada', 'criadouro_os_tipo_volume', 'tratamento_adicional_realizado'];
  observations.forEach(name => {
    fields[name] = field();
    fields['marker-' + name] = field();
  });
  const application = {disabled: false, hidden: false};
  const note = {hidden: true, textContent: ''};
  const marker = {hidden: true};
  const form = {querySelector(selector) {
    const name = selector.match(/\[name="([^"]+)"\]/)?.[1];
    const markerName = selector.match(/\[data-obrigatorio-observacao="([^"]+)"\]/)?.[1];
    return fields[name || ('marker-' + markerName)];
  }};
  const elements = {'os-form-main': form, 'os-campos-aplicacao': application,
    'os-sem-aplicacao-aviso': note, 'os-motivo-obrigatorio': marker,
    'os-execucao-regras': {textContent: JSON.stringify({
      situacoes_sem_aplicacao: ['APENAS MONITORADO', 'NENHUM VOO REALIZADO'],
      situacao_sem_voo: 'NENHUM VOO REALIZADO', campos_observacao: observations,
    })}};
  const context = {document: {
    readyState: loading ? 'loading' : 'complete',
    getElementById: id => elements[id],
    addEventListener(type, callback) { listeners[type] = callback; },
  }};
  vm.runInNewContext(source, context);
  return {fields, application, note, marker, listeners,
    select(value) {
      fields.situacao_aplicacao.value = value;
      fields.situacao_aplicacao.change();
    }};
}

test('no flight asks for a reason, skips application and does not invent observations', () => {
  const b = browser({situation: 'NENHUM VOO REALIZADO'});
  assert.equal(b.application.hidden, true);
  assert.equal(b.application.disabled, true);
  assert.equal(b.fields.motivo_nao_realizacao.required, true);
  assert.equal(b.marker.hidden, false);
  assert.equal(b.fields.larva_visualizada.required, false);
  assert.equal(b.fields.larva_visualizada.value, '');
  assert.equal(b.fields.tratamento_adicional_realizado.value, '');
  assert.equal(b.note.hidden, false);
  assert.match(b.note.textContent, /informe o motivo/);
});

test('monitoring still requires observations and dispenses product and dose', () => {
  const b = browser({situation: 'APENAS MONITORADO'});
  assert.equal(b.application.disabled, true);
  assert.equal(b.fields.larva_visualizada.required, true);
  assert.equal(b.fields.criadouro_os_tipo_volume.required, true);
  assert.equal(b.fields.motivo_nao_realizacao.required, false);
  assert.match(b.note.textContent, /Apenas monitorado/);
});

test('switching situations retains unsaved field values and restores application requirements', () => {
  const b = browser({situation: 'MONITORADO E LARVICIDA APLICADO'});
  b.fields.larva_visualizada.value = 'SIM';
  b.select('NENHUM VOO REALIZADO');
  assert.equal(b.application.disabled, true);
  assert.equal(b.fields.larva_visualizada.value, 'SIM');
  b.select('APENAS LARVICIDA APLICADO (FALTA DE SEGURANÇA)');
  assert.equal(b.application.disabled, false);
  assert.equal(b.application.hidden, false);
  assert.equal(b.note.hidden, true);
  assert.equal(b.fields.larva_visualizada.required, true);
  assert.equal(b.fields.motivo_nao_realizacao.required, false);
});

test('situation rules never unlock read-only inputs or inputs locked by an edit reservation', () => {
  const b = browser({situation: 'NENHUM VOO REALIZADO', readOnly: true});
  b.select('MONITORADO E LARVICIDA APLICADO');
  Object.entries(b.fields).filter(([key]) => !key.startsWith('marker-')).forEach(([, field]) => {
    assert.equal(field.disabled, true);
  });
});

test('rules initialize after the document loads', () => {
  const b = browser({situation: 'NENHUM VOO REALIZADO', loading: true});
  assert.equal(b.application.disabled, false);
  b.listeners.DOMContentLoaded();
  assert.equal(b.application.disabled, true);
});
