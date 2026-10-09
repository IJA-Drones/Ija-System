const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/portal-chatbot.js'), 'utf8');
class Element {
  constructor(tag = '') { this.tag = tag; this.children = []; this.listeners = {}; this.value = ''; }
  set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  set textContent(text) { this.text = text; this.children = []; }
  get textContent() { return this.text; }
  append(child) { this.children.push(child); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute() {}
  focus() {}
  replaceChildren() { this.children = []; }
}
function setup(data, fetchResult) {
  const selectors = ['.portal-chat-toggle', '.portal-chat-panel', '[role="log"]', 'form', 'textarea', '[data-clear]', '[data-status]', '[data-close]'];
  const elements = Object.fromEntries(selectors.map(key => [key, new Element()]));
  const root = new Element();
  root.dataset = {url: '/portal-cidadao/chatbot', token: 'token'};
  root.querySelector = key => elements[key];
  const send = new Element();
  send.textContent = 'Enviar mensagem';
  elements.form.querySelector = () => send;
  elements['.portal-chat-panel'].hidden = true;
  const requests = [];
  const events = [];
  root.dispatchEvent = event => events.push(event.type);
  const document = {querySelector: key => key === '[data-portal-chat]' ? root : null,
    createElement: tag => new Element(tag), createTextNode: text => ({text})};
  vm.runInNewContext(source, {document, URL, AbortController, setTimeout, clearTimeout, CustomEvent: class { constructor(type) { this.type = type; } },
    fetch: async (url, options) => { requests.push(JSON.parse(options.body)); return fetchResult ? fetchResult(options) : {ok: true, json: async () => data}; }});
  return {elements, requests, send, events};
}
test('renders inline citations as safe links and never interprets HTML', async () => {
  const {elements, requests} = setup({answer: 'Texto fonte', parts: [
    {text: '<img src=x onerror=alert(1)>'},
    {text: '[1]', title: 'Fonte', url: 'https://www.gov.br/saude'},
    {text: 'malicious', url: 'javascript:alert(1)'}]});
  elements.textarea.value = 'Como prevenir?';
  await elements.form.listeners.submit({preventDefault() {}});
  const message = elements['[role="log"]'].children.at(-1);
  assert.equal(message.children[0].text, '<img src=x onerror=alert(1)>');
  assert.equal(message.children[1].tag, 'a');
  assert.equal(message.children[1].href, 'https://www.gov.br/saude');
  assert.equal(message.children[1].rel, 'noopener noreferrer');
  assert.equal(message.children[2].tag, undefined);
  assert.equal(requests[0].history.length, 0);
  elements['[data-clear]'].listeners.click();
  elements.textarea.value = 'Nova pergunta';
  await elements.form.listeners.submit({preventDefault() {}});
  assert.equal(requests[1].history.length, 0);
});

for (const outcome of ['success', 'http-error', 'network-error', 'timeout']) {
  test(`restores send button after ${outcome}`, async () => {
    let finish;
    const pending = new Promise(resolve => { finish = resolve; });
    const {elements, send} = setup(null, async () => {
      await pending;
      if (outcome === 'network-error') throw new Error('Failed to fetch');
      if (outcome === 'timeout') throw Object.assign(new Error('timeout'), {name: 'AbortError'});
      return {ok: outcome === 'success', json: async () => outcome === 'success' ? {answer: 'Pronto'} : {error: 'Indisponível'}};
    });
    elements.textarea.value = 'Pergunta';
    const submit = elements.form.listeners.submit({preventDefault() {}});
    assert.equal(send.disabled, true);
    assert.equal(send.textContent, 'Aguarde…');
    finish();
    await submit;
    assert.equal(send.disabled, false);
    assert.equal(send.textContent, 'Enviar mensagem');
    assert.equal(elements['[data-clear]'].disabled, false);
    assert.equal(elements['[data-status]'].textContent, '');
  });
}

test('chat form opts out of the global loading handler', () => {
  const template = fs.readFileSync(path.join(__dirname, '../app/templates/_portal_chatbot.html'), 'utf8');
  assert.match(template, /<form class="form-no-loading">/);
  const base = fs.readFileSync(path.join(__dirname, '../app/templates/base.html'), 'utf8');
  assert.ok(base.includes(':not(.form-no-loading)'));
});

test('turns known portal paths into named local links', async () => {
  const {elements} = setup({answer: 'Abra /portal-cidadao#portal-relato ou /portal-cidadao/boletim-dengue.'});
  elements.textarea.value = 'Onde encontro?';
  await elements.form.listeners.submit({preventDefault() {}});
  const links = elements['[role="log"]'].children.at(-1).children.filter(child => child.tag === 'a');
  assert.equal(links.length, 2);
  assert.equal(links[0].textContent, 'Registrar relato');
  assert.equal(links[0].href, '/portal-cidadao#portal-relato');
  assert.equal(links[1].textContent, 'Consultar boletim');
});


test('a direct request to register starts the local form without calling AI', async () => {
  const {elements, requests, events} = setup({answer: 'unused'});
  elements.textarea.value = 'quero registrar um relato';
  await elements.form.listeners.submit({preventDefault() {}});
  assert.deepEqual(events, ['portal:start-report']);
  assert.equal(requests.length, 0);
});
