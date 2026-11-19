const test = require('node:test');
const assert = require('node:assert/strict');
const {permitted, fieldBody, actionBody} = require('../app/static/js/screen-guide.js');

function control({disabled = false, blocked = false, denied = false, independent = false, tag = 'FORM'} = {}) {
  return {disabled, getAttribute: () => null, closest(selector) {
    if (selector.startsWith('[data-ti-blocked')) return blocked ? {} : null;
    if (selector === '[data-ti-allowed="false"]') return denied ? {tagName: tag} : null;
    return independent ? {} : null;
  }};
}
test('guide omits disabled controls and denied forms while honoring independent controls', () => {
  assert.equal(permitted(control()), true);
  assert.equal(permitted(control({disabled: true})), false);
  assert.equal(permitted(control({blocked: true, independent: true})), false);
  assert.equal(permitted(control({denied: true})), false);
  assert.equal(permitted(control({denied: true, independent: true})), true);
  assert.equal(permitted(control({denied: true, independent: true, tag: 'DIV'})), false);
});
test('request instructions depend on the options actually available in this form', () => {
  assert.doesNotMatch(fieldBody('tipo_visita', 'select-one', false), /Culex|Aedes/);
  assert.match(fieldBody('tipo_visita', 'select-one', false, {culex: true}), /Culex é apenas uma das opções/);
  assert.doesNotMatch(fieldBody('foco', 'select-one', false), /QUADRA/);
  assert.match(fieldBody('foco', 'select-one', false, {quadra: true}), /escolha QUADRA aqui/);
  assert.doesNotMatch(fieldBody('observacao', 'textarea', false), /quadras/);
});
test('invoice numbers and readonly fields receive appropriate instructions', () => {
  assert.doesNotMatch(fieldBody('numero', 'text', false), /S\/N|endereço/);
  assert.match(fieldBody('numero', 'text', false, {address: true}), /S\/N/);
  assert.match(fieldBody('valor', 'number', true), /edição não está disponível/);
  assert.match(fieldBody('anexo', 'file', false), /não anexa nem envia/);
  assert.match(fieldBody('senha', 'password', false), /não lê o conteúdo/);
});
test('write, delete and export explanations take precedence over GET filter defaults', () => {
  assert.match(actionBody('Excluir', 'get'), /alterar informações reais/);
  assert.match(actionBody('Salvar', 'post'), /quem realiza.*é você/);
  assert.match(actionBody('Baixar relatório', 'get'), /período e os filtros/);
  assert.match(actionBody('Buscar', 'get'), /atualizar a consulta/);
});
