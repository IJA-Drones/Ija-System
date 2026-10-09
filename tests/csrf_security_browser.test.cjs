const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../app/static/js/csrf-security.js"), "utf8");

function browser(enabled = true) {
  const events = {};
  const document = {
    querySelector: () => enabled ? { content: "test-csrf-token" } : null,
    createElement: () => ({ remove() { this.owner?.fields.splice(this.owner.fields.indexOf(this), 1); } }),
    addEventListener: (name, listener) => { events[name] = listener; },
  };
  class HTMLFormElement {
    constructor(method = "POST", action = "https://example.test/change") {
      this.method = method;
      this.action = action;
      this.fields = [];
      this.submitted = false;
    }
    querySelector() { return this.fields.find(field => field.name === "_csrf_token"); }
    appendChild(field) { field.owner = this; this.fields.push(field); }
    submit() { this.submitted = true; }
  }
  class XMLHttpRequest {
    constructor() { this.headers = {}; }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send() { this.sent = true; }
  }
  const fetchCalls = [];
  const window = {
    location: { href: "https://example.test/page", origin: "https://example.test" },
    fetch: (input, options) => { fetchCalls.push({ input, options }); return Promise.resolve({ ok: true }); },
  };
  vm.runInNewContext(source, { document, window, HTMLFormElement, XMLHttpRequest, URL, Request, Headers, Set });
  return { events, HTMLFormElement, XMLHttpRequest, fetchCalls, window };
}

test("does nothing unless CSRF is enabled", () => {
  const page = browser(false);
  assert.equal(page.events.submit, undefined);
  assert.equal(page.HTMLFormElement.prototype.submit.name, "submit");
});

test("adds a token before a normal same-origin form submission", () => {
  const page = browser();
  const form = new page.HTMLFormElement();
  page.events.submit({ target: form });
  assert.equal(form.fields[0].name, "_csrf_token");
  assert.equal(form.fields[0].value, "test-csrf-token");
  page.events.submit({ target: form });
  assert.equal(form.fields.length, 1);
});

test("covers programmatic submit and formmethod override", () => {
  const page = browser();
  const scripted = new page.HTMLFormElement();
  scripted.submit();
  assert.equal(scripted.submitted, true);
  assert.equal(scripted.fields[0].value, "test-csrf-token");
  const override = new page.HTMLFormElement("GET");
  page.events.submit({ target: override, submitter: { formMethod: "POST" } });
  assert.equal(override.fields[0].value, "test-csrf-token");
});

test("does not leak token to external or ordinary GET forms", () => {
  const page = browser();
  const external = new page.HTMLFormElement("POST", "https://outside.test/receive");
  const get = new page.HTMLFormElement("GET");
  page.events.submit({ target: external });
  page.events.submit({ target: get });
  assert.equal(external.fields.length, 0);
  assert.equal(get.fields.length, 0);
  const changingMethod = new page.HTMLFormElement("POST");
  page.events.submit({ target: changingMethod });
  page.events.submit({ target: changingMethod, submitter: { formMethod: "GET" } });
  assert.equal(changingMethod.fields.length, 0);
  const changingAction = new page.HTMLFormElement("POST");
  page.events.submit({ target: changingAction });
  page.events.submit({ target: changingAction,
    submitter: { formMethod: "POST", formAction: "https://outside.test/receive" } });
  assert.equal(changingAction.fields.length, 0);
});

test("fetch adds the header only for same-origin unsafe requests", async () => {
  const page = browser();
  await page.window.fetch("/change", { method: "POST", headers: { Accept: "application/json" } });
  const headers = page.fetchCalls[0].options.headers;
  assert.equal(headers.get("X-CSRFToken"), "test-csrf-token");
  assert.equal(headers.get("Accept"), "application/json");
  await page.window.fetch("https://outside.test/change", { method: "POST" });
  assert.equal(page.fetchCalls[1].options.headers, undefined);
  await page.window.fetch("/view", { method: "GET" });
  assert.equal(page.fetchCalls[2].options.headers, undefined);
});

test("XHR adds the header only to same-origin unsafe calls", () => {
  const page = browser();
  const local = new page.XMLHttpRequest();
  local.open("POST", "/upload");
  local.send();
  assert.equal(local.headers["X-CSRFToken"], "test-csrf-token");
  const external = new page.XMLHttpRequest();
  external.open("POST", "https://outside.test/upload");
  external.send();
  assert.equal(external.headers["X-CSRFToken"], undefined);
});
