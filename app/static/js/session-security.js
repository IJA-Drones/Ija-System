(() => {
  "use strict";
  const element = document.getElementById("ija-security-config");
  if (!element) return;
  const config = JSON.parse(element.textContent);
  let deadline = Date.now() + config.expires_in * 1000;
  let absolute = config.absolute;
  let pendingActivityAt = 0;
  let lastRequestAt = 0;
  let inFlight = false;
  let leaving = false;

  const warning = document.createElement("div");
  warning.className = "alert alert-warning shadow position-fixed bottom-0 start-50 translate-middle-x mb-3";
  warning.style.zIndex = "1090";
  warning.style.width = "min(92vw, 560px)";
  warning.setAttribute("role", "status");
  warning.hidden = true;
  const message = document.createElement("span");
  const continueButton = document.createElement("button");
  continueButton.type = "button";
  continueButton.className = "btn btn-sm btn-primary ms-2";
  continueButton.textContent = "Continuar conectado";
  warning.append(message, continueButton);
  document.body.append(warning);

  function goToLogin() {
    if (leaving) return;
    leaving = true;
    window.location.assign(config.login_url);
  }

  async function sync(activity = false) {
    if (inFlight || leaving) return;
    inFlight = true;
    lastRequestAt = Date.now();
    const sentActivityAt = pendingActivityAt;
    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(activity ? config.activity_url : config.status_url, {
        method: activity ? "POST" : "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: activity ? { "X-Session-CSRF": config.csrf, Accept: "application/json" } : { Accept: "application/json" },
        signal: controller.signal,
      });
      if (response.status === 401) {
        goToLogin();
        return;
      }
      if (!response.ok) throw new Error("Session status unavailable");
      const data = await response.json();
      if (!Number.isFinite(data.expires_in)) throw new Error("Invalid session status");
      deadline = Date.now() + data.expires_in * 1000;
      absolute = data.absolute;
      if (activity && pendingActivityAt === sentActivityAt) pendingActivityAt = 0;
      warning.hidden = data.expires_in > 60;
      continueButton.hidden = absolute;
    } catch (_) {
      if (Date.now() >= deadline) goToLogin();
    } finally {
      clearTimeout(abortTimer);
      inFlight = false;
    }
  }

  function recordActivity(event) {
    if (!event.isTrusted || document.visibilityState !== "visible") return;
    pendingActivityAt = Date.now();
    if (Date.now() - lastRequestAt >= 15000 || deadline - Date.now() <= 15000) sync(true);
  }
  for (const eventName of ["pointerdown", "keydown", "input", "wheel", "touchstart"]) {
    document.addEventListener(eventName, recordActivity, { passive: true });
  }
  continueButton.addEventListener("click", (event) => {
    if (!event.isTrusted) return;
    pendingActivityAt = Date.now();
    sync(true);
  });
  document.addEventListener("visibilitychange", () => {
    // Returning to a tab checks the server before attempting to renew anything.
    if (document.visibilityState === "visible") sync(false);
  });

  setInterval(() => {
    if (leaving) return;
    const now = Date.now();
    const seconds = Math.max(0, Math.ceil((deadline - now) / 1000));
    warning.hidden = seconds > 60;
    continueButton.hidden = absolute;
    message.textContent = absolute
      ? `Sua sessão atinge o limite de duração em ${seconds} segundos.`
      : `Sua sessão expira em ${seconds} segundos por inatividade.`;
    // Other tabs share the cookie. Confirm expiry with the server before leaving.
    if (seconds === 0) sync(false);
    else if (pendingActivityAt && now - pendingActivityAt < 15000 && now - lastRequestAt >= 15000) sync(true);
    else if (now - lastRequestAt >= 30000) sync(false);
  }, 1000);

  const policy = config.password;
  const rules = [
    [`Pelo menos ${policy.min_length} caracteres`, value => Array.from(value).length >= policy.min_length],
    [`No máximo ${policy.max_length} caracteres`, value => Array.from(value).length <= policy.max_length],
  ];
  if (policy.uppercase) rules.push(["Uma letra maiúscula", value => /\p{Uppercase}/u.test(value)]);
  if (policy.lowercase) rules.push(["Uma letra minúscula", value => /\p{Lowercase}/u.test(value)]);
  if (policy.digit) rules.push(["Um número", value => /\p{Nd}/u.test(value)]);
  if (policy.symbol) rules.push(["Um símbolo (ex.: !, @, #)", value => /[^\p{L}\p{N}\s]/u.test(value)]);

  document.querySelectorAll('input[name="senha"], input[name="senha_equipe"]').forEach((input, index) => {
    const list = document.createElement("ul");
    list.id = `ija-password-rules-${index}`;
    list.className = "small text-muted mt-2 mb-0 ps-3";
    input.autocomplete = "new-password";
    input.setAttribute("aria-describedby", `${input.getAttribute("aria-describedby") || ""} ${list.id}`.trim());
    const items = rules.map(([label]) => {
      const item = document.createElement("li");
      item.textContent = label;
      list.append(item);
      return item;
    });
    const parent = input.closest(".input-group") || input;
    parent.insertAdjacentElement("afterend", list);
    // Let Unicode code points, rather than HTML's UTF-16 length, determine length.
    input.removeAttribute("minlength");
    input.removeAttribute("maxlength");
    input.addEventListener("input", () => {
      const missing = [];
      rules.forEach(([label, check], i) => {
        const passed = check(input.value);
        items[i].className = input.value && passed ? "text-success" : "";
        items[i].textContent = input.value && passed ? `✓ ${label}` : label;
        if (!passed) missing.push(label);
      });
      input.setCustomValidity(input.value && missing.length ? missing.join(". ") + "." : "");
    });
  });
})();
