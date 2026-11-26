const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync('app/static/js/gestao-ti-save.js', 'utf8'), context);
const {save, matches} = context.window.IjaTiSave;
const selection = {areas: ['prefeitura'], permissions: [], nome_acesso: ''};
const saved = () => ({...selection, configured: true, version: 3});
const timeout = () => Object.assign(new Error('timeout'), {code: 'request_timeout'});

test('a normal successful write is not replayed or followed by unnecessary verification', async () => {
  let writes = 0;
  const result = await save({submitted: selection, previousVersion: 2,
    write: async () => { writes++; return {configuration: saved()}; },
    read: async () => { throw new Error('verification must not run'); }});
  assert.equal(result.configuration.version, 3);
  assert.equal(writes, 1);
});

for (const failure of [timeout(), Object.assign(new Error('network'), {code: 'network_error'}),
  Object.assign(new Error('server'), {status: 503})]) {
  test(`an uncertain ${failure.code || failure.status} write is confirmed by the saved version without resending`, async () => {
    let writes = 0, reads = 0, checks = 0;
    const result = await save({submitted: selection, previousVersion: 2,
      write: async () => { writes++; throw failure; }, read: async () => { reads++; return saved(); },
      onVerify: () => checks++});
    assert.equal(result.recovered, true);
    assert.equal(writes, 1); assert.equal(reads, 1); assert.equal(checks, 1);
  });
}

for (const latest of [{...saved(), version: 2}, {...saved(), configured: false},
  {...saved(), permissions: ['prefeitura.os.consultar']}]) {
  test('an unchanged, inherited or conflicting snapshot never produces false success', async () => {
    let writes = 0;
    const draft = JSON.parse(JSON.stringify(selection));
    await assert.rejects(save({submitted: draft, previousVersion: 2,
      write: async () => { writes++; throw timeout(); }, read: async () => latest}),
    error => error.code === 'save_unconfirmed');
    assert.equal(writes, 1); assert.deepEqual(draft, selection);
  });
}

test('failed verification preserves uncertainty rather than claiming the write was undone', async () => {
  await assert.rejects(save({submitted: selection, previousVersion: 2,
    write: async () => { throw timeout(); }, read: async () => { throw new Error('offline'); }}),
  error => error.code === 'save_unconfirmed' && error.message.includes('alterações continuam'));
});

for (const status of [400, 401, 403, 409]) {
  test(`an explicit HTTP ${status} refusal is reported and never retried`, async () => {
    const failure = Object.assign(new Error('refused'), {status});
    await assert.rejects(save({submitted: selection, previousVersion: 2,
      write: async () => { throw failure; }, read: async () => { assert.fail('must not verify a refusal'); }}),
    error => error === failure);
  });
}

test('verification compares the complete selection, independent of ordering', () => {
  assert.equal(matches({...saved(), areas: ['sistema', 'prefeitura'], nome_acesso: 'Teste '},
    {...selection, areas: ['prefeitura', 'sistema'], nome_acesso: 'Teste'}, 2), true);
});
