const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('versioned Azul assets bypass an old unversioned cache and reuse their own cache', async () => {
  const handlers = {};
  const path = '/static/js/azul-tutorial-launcher.js';
  const entries = new Map([[path, {body: 'old'}]]);
  const key = request => typeof request === 'string' ? request : request.url;
  let fetches = 0;
  const cache = {
    match: async request => entries.get(key(request)),
    put: async (request, response) => entries.set(key(request), response),
  };
  vm.runInNewContext(fs.readFileSync('app/static/sw.js', 'utf8'), {
    self: {location: {origin: 'https://system.test'}, addEventListener: (type, handler) => {handlers[type] = handler;}},
    caches: {...cache, open: async () => cache}, URL,
    fetch: async () => {fetches++; return {ok: true, body: 'fixed', clone() {return this;}};},
  });
  const request = {method: 'GET', url: `https://system.test${path}?v=20261119-1`};
  let response;
  handlers.fetch({request, respondWith: promise => {response = promise;}});
  assert.equal((await response).body, 'fixed');
  await Promise.resolve();
  handlers.fetch({request, respondWith: promise => {response = promise;}});
  assert.equal((await response).body, 'fixed');
  assert.equal(fetches, 1);
  assert.equal(entries.get(path).body, 'old');
});
