const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createPager } = require('../app/static/js/vigilancia_sinan.js');
const city = { ibge: '3550308', name: 'São Paulo — capital', uf: 'SP' };
const otherCity = { ibge: '2610905', name: 'Pesqueira', uf: 'PE' };
function page(ibge, year, offset, total = 10, disease = 'dengue') {
  return { municipality: { ibge }, year, offset, disease, finished: total < 10, limit_reached: false,
    next_offset: total < 10 ? null : offset + 10,
    records: Array.from({ length: total }, () => ({ year, week: `${year}01`, classification: '8', residence: 'local' })),
    summary: { total, classifications: { 8: total }, weeks: { [`${year}01`]: total }, unknown_week: 0, residence: { local: total } },
    retrieved_at: '2026-10-16T12:00:00Z' };
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('next replaces the ten records, previous uses cache, and subsequent next keeps the row offset', async () => {
  const offsets = [];
  const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset, signal, disease) => {
    offsets.push(offset); return page(ibge, year, offset, offset === 20 ? 3 : 10, disease);
  } });
  await pager.start(city, 2026);
  assert.deepEqual(offsets, [0]);
  await pager.next();
  assert.equal(pager.state.data.records.length, 10);
  assert.equal(pager.state.data.offset, 10);
  assert.equal(pager.state.data.summary.total, 10);
  await pager.previous();
  assert.equal(pager.state.data.offset, 0);
  await pager.next();
  await pager.next();
  assert.deepEqual(offsets, [0, 10, 20]);
  assert.equal(pager.state.data.records.length, 3);
  await pager.next();
  assert.deepEqual(offsets, [0, 10, 20]);
});

test('failure on next preserves the displayed page and retries the same offset', async () => {
  const offsets = [];
  let fail = true;
  const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset) => {
    offsets.push(offset);
    if (offset && fail) { fail = false; throw new Error('Timeout'); }
    return page(ibge, year, offset);
  } });
  await pager.start(city, 2026);
  await pager.next();
  assert.equal(pager.state.phase, 'error');
  assert.equal(pager.state.data.offset, 0);
  assert.equal(pager.state.data.records.length, 10);
  await pager.retry();
  assert.deepEqual(offsets, [0, 10, 10]);
  assert.equal(pager.state.data.offset, 10);
});

test('empty final page keeps the last populated page and disables next', async () => {
  const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset) => page(ibge, year, offset, offset ? 0 : 10) });
  await pager.start(city, 2026);
  await pager.next();
  assert.equal(pager.state.data.offset, 0);
  assert.equal(pager.state.data.records.length, 10);
  assert.equal(pager.state.data.next_offset, null);
  assert.equal(pager.state.data.finished, true);
});

test('empty first page is successful but network failure has no data', async () => {
  const empty = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset) => page(ibge, year, offset, 0) });
  await empty.start(city, 2026);
  assert.equal(empty.state.phase, 'ready');
  assert.deepEqual(empty.state.data.records, []);
  const failed = createPager({ onUpdate() {}, fetchPage: async () => { throw new Error('Timeout'); } });
  await failed.start(city, 2026);
  assert.equal(failed.state.phase, 'error');
  assert.equal(failed.state.data, null);
});

test('changing municipality year and disease ignores late responses and starts at page one', async () => {
  const pending = deferred();
  const pager = createPager({ onUpdate() {}, fetchPage: (ibge, year, offset, signal, disease) => disease === 'dengue' ? pending.promise : Promise.resolve(page(ibge, year, offset, 2, disease)) });
  const first = pager.start(city, 2026, 'dengue');
  await pager.start(otherCity, 2025, 'zika');
  pending.resolve(page(city.ibge, 2026, 0)); await first;
  assert.equal(pager.state.city.ibge, otherCity.ibge);
  assert.equal(pager.state.data.disease, 'zika');
  assert.equal(pager.state.data.year, 2025);
  assert.equal(pager.state.data.records.length, 2);
  assert.equal(pager.state.pages.size, 1);
});

test('clear cancels loading and prevents a late result from restoring the table', async () => {
  const pending = deferred();
  const updates = [];
  const pager = createPager({ onUpdate: run => updates.push(run), fetchPage: () => pending.promise });
  const running = pager.start(city, 2026);
  pager.clear(); const count = updates.length;
  pending.resolve(page(city.ibge, 2026, 0)); await running;
  assert.equal(pager.state, null);
  assert.equal(updates.at(-1), null);
  assert.equal(updates.length, count);
});

test('cancel and retry cannot publish an earlier response for the same page', async () => {
  const pending = deferred(); let calls = 0;
  const pager = createPager({ onUpdate() {}, fetchPage: (ibge, year, offset) => ++calls === 1 ? pending.promise : Promise.resolve(page(ibge, year, offset, 3)) });
  const old = pager.start(city, 2026);
  pager.cancel(); await pager.retry();
  pending.resolve(page(city.ibge, 2026, 0)); await old;
  assert.equal(pager.state.data.records.length, 3);
  assert.equal(pager.state.phase, 'ready');
});

test('concurrent next clicks do not start duplicate requests', async () => {
  const pending = deferred(); let calls = 0;
  const pager = createPager({ onUpdate() {}, fetchPage: (ibge, year, offset) => {
    calls++; return offset ? pending.promise : Promise.resolve(page(ibge, year, offset));
  } });
  await pager.start(city, 2026);
  const next = pager.next(); await pager.next();
  assert.equal(calls, 2);
  pending.resolve(page(city.ibge, 2026, 10)); await next;
});

test('mismatched disease municipality year offset or missing records cannot replace valid data', async () => {
  for (const change of [{ disease: 'zika' }, { municipality: otherCity }, { year: 2025 }, { offset: 20 }, { records: undefined }, { next_offset: 11 }]) {
    const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset) => ({ ...page(ibge, year, offset), ...(offset ? change : {}) }) });
    await pager.start(city, 2026); await pager.next();
    assert.equal(pager.state.phase, 'error');
    assert.equal(pager.state.data.offset, 0);
  }
});

test('read limit retains partial data and does not expose a next page', async () => {
  const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset) => ({ ...page(ibge, year, offset), limit_reached: true, next_offset: null }) });
  await pager.start(city, 2026);
  assert.equal(pager.state.data.finished, false);
  assert.equal(pager.state.data.limit_reached, true);
  await pager.next();
  assert.equal(pager.state.pages.size, 1);
});

for (const disease of ['dengue', 'zika', 'chikungunya']) {
  test(`${disease} stays selected when loading the next page`, async () => {
    const requests = [];
    const pager = createPager({ onUpdate() {}, fetchPage: async (ibge, year, offset, signal, selectedDisease) => {
      requests.push([selectedDisease, offset]); return page(ibge, year, offset, 10, selectedDisease);
    } });
    await pager.start(city, 2026, disease); await pager.next();
    assert.deepEqual(requests, [[disease, 0], [disease, 10]]);
  });
}
