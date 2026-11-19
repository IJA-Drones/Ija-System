const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('text guide navigation does not reopen the practice room through the root state attribute', () => {
  const events = {};
  const root = {
    dataset: { tutorialUrl: '/azul/tutorial', guideOpen: '1' },
    addEventListener: (name, handler) => { events[name] = handler; },
    contains: () => true,
    dispatchEvent: () => { throw new Error('Text guide must remain open'); },
  };
  vm.runInNewContext(fs.readFileSync('app/static/js/azul-tutorial-launcher.js', 'utf8'), {
    document: {querySelectorAll: selector => selector === '[data-azul-help]' ? [root] : []},
    window: {addEventListener() {}}, HTMLDialogElement: function () {}, URL,
    location: {origin: 'https://system.test'},
  });
  // dataset.guideOpen creates data-guide-open on the root; closest() from Next resolves it.
  let intercepted = false;
  events.click({target: {closest: () => root}, preventDefault() {intercepted = true;}, stopImmediatePropagation() {}});
  assert.equal(intercepted, false);
  assert.equal(root.dataset.guideOpen, '1');
});
