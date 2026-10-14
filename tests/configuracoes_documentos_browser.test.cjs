const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/js/configuracoes-documentos.js'), 'utf8');

function browser({ saved = true, form = true } = {}) {
  const ids = ['prefeitura-selector', 'document-settings-form', 'watermark-enabled', 'watermark-opacity', 'watermark-width', 'watermark-user', 'watermark-image', 'watermark-remove', 'watermark-preview', 'watermark-preview-image', 'watermark-file-error', 'opacity-value', 'width-value', 'watermark-preview-user', 'watermark-preview-status'];
  const elements = Object.fromEntries(ids.map(id => [id, { value: '', checked: false, style: {}, files: [], events: {},
    addEventListener(event, fn) { this.events[event] = fn; }, getAttribute() { return saved ? '/configuracoes/documentos/1/imagem' : null; },
    fire(event = 'input') { this.events[event]?.(); },
  }]));
  if (!form) delete elements['document-settings-form'];
  elements['watermark-opacity'].value = '12';
  elements['watermark-width'].value = '55';
  const revoked = [], navigated = [];
  class MockURL extends URL {
    static createObjectURL() { return 'blob:preview'; }
    static revokeObjectURL(value) { revoked.push(value); }
  }
  vm.runInNewContext(source, {
    document: { getElementById: id => elements[id] }, URL: MockURL,
    window: { location: { origin: 'https://ija.test', assign: value => navigated.push(value) }, addEventListener() {} },
  });
  return { get: id => elements[id], revoked, navigated };
}

test('live preview follows activation, intensity, size and emitter selection', () => {
  const { get } = browser();
  assert.equal(get('watermark-preview').hidden, true);
  get('watermark-enabled').checked = true;
  get('watermark-opacity').value = '25';
  get('watermark-width').value = '80';
  get('watermark-user').checked = true;
  get('watermark-enabled').fire();
  assert.equal(get('watermark-preview').hidden, false);
  assert.equal(get('watermark-preview').style.opacity, 0.25);
  assert.equal(get('watermark-preview').style.width, '80%');
  assert.equal(get('watermark-preview-user').hidden, false);
});

test('replacement cancels removal; removal clears pending upload and preview', () => {
  const { get, revoked } = browser();
  get('watermark-remove').checked = true;
  get('watermark-image').files = [{ size: 100, type: 'image/png' }];
  get('watermark-image').fire('change');
  assert.equal(get('watermark-remove').checked, false);
  assert.equal(get('watermark-preview-image').src, 'blob:preview');
  get('watermark-remove').checked = true;
  get('watermark-remove').fire('change');
  assert.equal(get('watermark-image').value, '');
  assert.equal(get('watermark-preview-image').hidden, true);
  assert.deepEqual(revoked, ['blob:preview']);
  get('watermark-remove').checked = false;
  get('watermark-remove').fire('input');
  assert.equal(get('watermark-preview-image').src, '/configuracoes/documentos/1/imagem');
});

test('unsupported or oversized uploads are rejected in the preview', () => {
  for (const selected of [{ size: 1, type: 'image/svg+xml' }, { size: 6 * 1024 * 1024, type: 'image/png' }]) {
    const { get } = browser({ saved: false });
    get('watermark-image').files = [selected];
    get('watermark-image').fire('change');
    assert.equal(get('watermark-file-error').hidden, false);
    assert.equal(get('watermark-image').value, '');
    assert.equal(get('watermark-preview-image').hidden, true);
  }
});

test('dev municipality selector works on empty state and only navigates same origin', () => {
  const { get, navigated } = browser({ form: false });
  get('prefeitura-selector').value = '/configuracoes/documentos/2';
  get('prefeitura-selector').fire('change');
  get('prefeitura-selector').value = 'https://external.test/';
  get('prefeitura-selector').fire('change');
  assert.deepEqual(navigated, ['https://ija.test/configuracoes/documentos/2']);
});
