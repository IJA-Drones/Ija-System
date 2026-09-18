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

function browser({ enabled = true, expiresIn = 60, idleSeconds = expiresIn, absoluteExpiresIn = null, devTimer = false } = {}) {
  let now = 100000;
  const startedAt = now;
  const config = {
    expires_in: expiresIn, idle_timeout_seconds: idleSeconds, absolute_expires_in: absoluteExpiresIn,
    absolute: absoluteExpiresIn !== null && absoluteExpiresIn <= expiresIn,
    csrf: "csrf-test", login_url: "/agro/login",
    status_url: "/auth/session-status", activity_url: "/auth/session-activity",
    password: { min_length: 15, max_length: 128, uppercase: true, lowercase: true, digit: true, symbol: true },
  };
  const inputs = [new Element(), new Element()];
  const document = new Element();
  document.body = new Element();
  document.visibilityState = "visible";
  const timer = new Element();
  document.getElementById = id => id === "ija-security-config" && enabled
    ? { textContent: JSON.stringify(config) }
    : id === "devSessionCountdown" && devTimer ? timer : null;
  document.createElement = () => new Element();
  document.querySelectorAll = () => inputs;
  const requests = [];
  const redirects = [];
  const intervals = [];
  let serverDeadline = now + expiresIn * 1000;
  let respond = request => {
    if (now >= serverDeadline) return { status: 401 };
    if (request.method === "POST") serverDeadline = now + idleSeconds * 1000;
    return { status: 200, ok: true, json: async () => ({
      expires_in: (serverDeadline - now) / 1000,
      absolute_expires_in: absoluteExpiresIn === null ? null : Math.max(0, absoluteExpiresIn - (now - startedAt) / 1000),
    }) };
  };
  vm.runInNewContext(source, {
    document,
    window: { location: { assign: url => redirects.push(url) } },
    Date: { now: () => now },
    AbortController,
    setInterval: fn => intervals.push(fn),
    setTimeout: () => 1,
    clearTimeout: () => {},
    fetch: async (url, options) => {
      const request = { url, ...options };
      requests.push(request);
      return respond(request);
    },
  });
  const flush = () => new Promise(resolve => setImmediate(resolve));
  return {
    document, requests, redirects, inputs, timer,
    respond: fn => { respond = fn; },
    async tick(seconds) { now += seconds * 1000; intervals.forEach(fn => fn()); await flush(); },
    async event(name, trusted = true) {
      document.listeners[name]?.({ isTrusted: trusted });
      await flush();
    },
    async continueSession(trusted = true) {
      document.body.children[0].children[3].listeners.click?.({ isTrusted: trusted });
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
  const page = browser({ expiresIn: 900 });
  await page.tick(299);
  assert.equal(page.requests.length, 0);
  await page.tick(1);
  assert.equal(page.requests.length, 1);
  assert.ok(page.requests.every(request => request.method === "GET"));
});

test("hidden tabs do not make periodic status requests", async () => {
  const page = browser({ expiresIn: 900 });
  page.document.visibilityState = "hidden";
  await page.tick(300);
  assert.equal(page.requests.length, 0);
  page.document.visibilityState = "visible";
  await page.event("visibilitychange");
  assert.equal(page.requests.at(-1).method, "GET");
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

test("active sessions renew at most every forty-five seconds under steady use", async () => {
  const page = browser({ expiresIn: 900, idleSeconds: 900 });
  await page.event("pointermove");
  await page.tick(44);
  await page.event("pointermove");
  assert.equal(page.requests.length, 1);
  await page.tick(1);
  assert.deepEqual(page.requests.map(request => request.method), ["POST", "POST"]);
});

test("thirty-second test timeout renews activity without one request per keystroke", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30 });
  page.respond(() => ({ status: 200, ok: true, json: async () => ({ expires_in: 30, absolute: false }) }));
  await page.event("input");
  await page.event("input");
  assert.equal(page.requests.length, 1);
  await page.tick(12);
  await page.event("keydown");
  assert.equal(page.requests.length, 2);
  assert.ok(page.requests.every(request => request.method === "POST"));
});

test("thirty seconds without interaction warns at fifteen seconds and ends the session", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30, devTimer: true });
  await page.tick(14);
  assert.equal(page.document.body.children[0].hidden, true);
  await page.tick(1);
  assert.equal(page.document.body.children[0].hidden, false);
  assert.equal(page.document.body.children[0].children[2].textContent, "00:15");
  await page.tick(15);
  assert.equal(page.timer.textContent, "00:00");
  assert.deepEqual(page.redirects, ["/agro/login"]);
  assert.deepEqual(page.requests.map(request => request.method), ["GET", "GET"]);
});

test("pointer activity resets the visible timer and sustained use keeps the session", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30, devTimer: true });
  await page.tick(15);
  assert.equal(page.document.body.children[0].hidden, false);
  await page.event("pointermove");
  assert.equal(page.document.body.children[0].hidden, true);
  assert.equal(page.timer.textContent, "00:30");
  for (let i = 0; i < 8; i++) {
    await page.tick(4);
    await page.event("pointermove");
    assert.equal(page.redirects.length, 0);
    assert.equal(page.document.body.children[0].hidden, true);
  }
  assert.ok(page.requests.some(request => request.method === "POST"));
  page.respond(() => ({ status: 401 }));
  await page.tick(31);
  assert.deepEqual(page.redirects, ["/agro/login"]);
});

test("activity is sent promptly when the server deadline is near", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30 });
  page.respond(() => ({ status: 200, ok: true, json: async () => ({
    expires_in: page.requests.at(-1).method === "GET" ? 5 : 30,
    absolute_expires_in: null,
  }) }));
  await page.tick(15);
  await page.event("visibilitychange");
  assert.equal(page.requests.at(-1).method, "GET");
  await page.tick(1);
  await page.event("pointermove");
  assert.equal(page.requests.at(-1).method, "POST");
  assert.equal(page.redirects.length, 0);
});

test("warning shows a prominent countdown and Continue button", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30 });
  await page.tick(15);
  const warning = page.document.body.children[0];
  assert.equal(warning.hidden, false);
  assert.match(warning.children[0].textContent, /ainda está aí/);
  assert.equal(warning.children[2].textContent, "00:15");
  assert.equal(warning.children[3].textContent, "Continuar conectado");
});

test("activity in another tab clears a warning after the server check", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30 });
  page.respond(() => ({ status: 200, ok: true, json: async () => ({ expires_in: 30, absolute_expires_in: null }) }));
  await page.tick(15);
  assert.equal(page.requests.at(-1).method, "GET");
  assert.equal(page.document.body.children[0].hidden, true);
});

test("Continue button renews the session and dismisses the warning", async () => {
  const page = browser({ expiresIn: 30, idleSeconds: 30, devTimer: true });
  await page.tick(15);
  await page.continueSession();
  assert.equal(page.requests.at(-1).method, "POST");
  assert.equal(page.document.body.children[0].hidden, true);
  assert.equal(page.timer.textContent, "00:30");
});

test("synthetic events and hidden tabs do not renew the session", async () => {
  const page = browser();
  await page.event("input", false);
  await page.event("pointermove", false);
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
  const page = browser({ expiresIn: 50, absoluteExpiresIn: 50 });
  page.respond(() => ({ status: 200, ok: true, json: async () => ({ expires_in: 5, absolute_expires_in: 5, absolute: true }) }));
  await page.tick(35);
  const warning = page.document.body.children[0];
  assert.equal(warning.children[3].hidden, true);
  assert.match(warning.children[1].textContent, /limite de duração/);
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
