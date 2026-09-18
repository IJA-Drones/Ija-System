const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../app/static/js/session-security.js"), "utf8");

class Element {
  constructor() {
    this.children = [];
    this.listeners = {};
    this.attributes = {};
    this.style = {};
    this.value = "";
  }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] || null; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  closest() { return null; }
  insertAdjacentElement(_, element) { this.hint = element; }
  setCustomValidity(message) { this.validationMessage = message; }
}

function browser({ enabled = true, expiresIn = 60 } = {}) {
  let now = 100000;
  const config = {
    expires_in: expiresIn, absolute: false, csrf: "csrf-test", login_url: "/agro/login",
    status_url: "/auth/session-status", activity_url: "/auth/session-activity",
    password: { min_length: 15, max_length: 128, uppercase: true, lowercase: true, digit: true, symbol: true },
  };
  const inputs = [new Element(), new Element()];
  const document = new Element();
  document.body = new Element();
  document.visibilityState = "visible";
  document.getElementById = () => enabled ? { textContent: JSON.stringify(config) } : null;
  document.createElement = () => new Element();
  document.querySelectorAll = () => inputs;
  const requests = [];
  const redirects = [];
  const intervals = [];
  let respond = () => ({ status: 200, ok: true, json: async () => ({ expires_in: 60 }) });
  vm.runInNewContext(source, {
    document,
    window: { location: { assign: url => redirects.push(url) } },
    Date: { now: () => now },
    AbortController,
    setInterval: fn => intervals.push(fn),
    setTimeout: () => 1,
    clearTimeout: () => {},
    fetch: async (url, options) => {
      requests.push({ url, ...options });
      return respond();
    },
  });
  const flush = () => new Promise(resolve => setImmediate(resolve));
  return {
    document, requests, redirects, inputs,
    respond: fn => { respond = fn; },
    async tick(seconds) { now += seconds * 1000; intervals.forEach(fn => fn()); await flush(); },
    async event(name, trusted = true) {
      document.listeners[name]?.({ isTrusted: trusted });
      await flush();
    },
  };
}

test("feature is inert without its configuration", async () => {
  const page = browser({ enabled: false });
  await page.tick(120);
  assert.equal(page.document.body.children.length, 0);
  assert.equal(page.requests.length, 0);
});

test("idle timers only check status and never send keep-alive POSTs", async () => {
  const page = browser();
  await page.tick(1);
  await page.tick(30);
  assert.equal(page.requests.length, 2);
  assert.ok(page.requests.every(request => request.method === "GET"));
});

test("trusted interaction renews activity with the session token", async () => {
  const page = browser();
  await page.event("input");
  assert.equal(page.requests.length, 1);
  assert.equal(page.requests[0].method, "POST");
  assert.equal(page.requests[0].headers["X-Session-CSRF"], "csrf-test");
  await page.event("input");
  assert.equal(page.requests.length, 1);
});

test("synthetic events and hidden tabs do not renew the session", async () => {
  const page = browser();
  await page.event("input", false);
  page.document.visibilityState = "hidden";
  await page.event("keydown");
  assert.equal(page.requests.length, 0);
});

test("local expiry checks another tab's activity before redirecting", async () => {
  const page = browser();
  page.respond(() => ({ status: 200, ok: true, json: async () => ({ expires_in: 120 }) }));
  await page.tick(61);
  assert.equal(page.requests[0].method, "GET");
  assert.equal(page.redirects.length, 0);
  assert.equal(page.document.body.children[0].hidden, true);
});

test("server expiry redirects to the correct login", async () => {
  const page = browser();
  page.respond(() => ({ status: 401 }));
  await page.tick(61);
  assert.deepEqual(page.redirects, ["/agro/login"]);
});

test("absolute timeout warns without offering renewal", async () => {
  const page = browser({ expiresIn: 50 });
  page.respond(() => ({ status: 200, ok: true, json: async () => ({ expires_in: 45, absolute: true }) }));
  await page.tick(30);
  await page.tick(1);
  const warning = page.document.body.children[0];
  assert.equal(warning.children[1].hidden, true);
  assert.match(warning.children[0].textContent, /limite de duração/);
});

test("network errors cannot extend a locally expired session", async () => {
  const page = browser();
  page.respond(() => { throw new Error("offline"); });
  await page.tick(61);
  assert.deepEqual(page.redirects, ["/agro/login"]);
});

test("returning from suspension checks status instead of sending old activity", async () => {
  const page = browser();
  await page.event("visibilitychange");
  assert.equal(page.requests[0].method, "GET");
});

test("password hints accept Unicode, flag weak input and allow empty edits", () => {
  const page = browser();
  for (const input of page.inputs) {
    assert.equal(input.hint.children.length, 6);
    input.value = "1234";
    input.listeners.input();
    assert.match(input.validationMessage, /15 caracteres/);
    input.value = "Árvore azul ٧! seguro";
    input.listeners.input();
    assert.equal(input.validationMessage, "");
    input.value = "";
    input.listeners.input();
    assert.equal(input.validationMessage, "");
  }
});
