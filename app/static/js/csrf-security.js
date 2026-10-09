(() => {
  "use strict";
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta || !meta.content) return;
  const token = meta.content;
  const unsafe = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  function sameOrigin(url) {
    try {
      return new URL(url, window.location.href).origin === window.location.origin;
    } catch (_) {
      return false;
    }
  }

  function prepareForm(form, method, action = form.action) {
    let field = form.querySelector('input[name="_csrf_token"]');
    if (!unsafe.has(String(method || form.method || "GET").toUpperCase()) || !sameOrigin(action)) {
      if (field) field.remove();
      return;
    }
    if (!field) {
      field = document.createElement("input");
      field.type = "hidden";
      field.name = "_csrf_token";
      form.appendChild(field);
    }
    field.value = token;
  }

  document.addEventListener("submit", event => {
    const form = event.target;
    if (form instanceof HTMLFormElement) {
      prepareForm(form, event.submitter?.formMethod || form.method,
        event.submitter?.formAction || form.action);
    }
  }, true);

  const originalSubmit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function (...args) {
    prepareForm(this, this.method);
    return originalSubmit.apply(this, args);
  };

  const originalFetch = window.fetch;
  if (typeof originalFetch === "function") {
    window.fetch = function (input, options = {}) {
      const method = String(options.method || input?.method || "GET").toUpperCase();
      const url = input instanceof Request ? input.url : input;
      if (unsafe.has(method) && sameOrigin(url)) {
        const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
        headers.set("X-CSRFToken", token);
        return originalFetch.call(this, input, { ...options, headers });
      }
      return originalFetch.call(this, input, options);
    };
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._ijaCsrfRequired = unsafe.has(String(method).toUpperCase()) && sameOrigin(url);
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    if (this._ijaCsrfRequired) this.setRequestHeader("X-CSRFToken", token);
    return originalSend.apply(this, args);
  };
})();
