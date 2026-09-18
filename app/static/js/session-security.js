(() => {
  "use strict";
  const element = document.getElementById("ija-security-config");
  if (!element) return;
  const config = JSON.parse(element.textContent);
  let deadline = Date.now() + config.expires_in * 1000;
  let confirmedDeadline = deadline;
  let absoluteDeadline = Number.isFinite(config.absolute_expires_in)
    ? Date.now() + config.absolute_expires_in * 1000 : Infinity;
  let absolute = config.absolute;
  let pendingActivityAt = 0;
  let inFlight = false;
  let leaving = false;
  const idleSeconds = Number(config.idle_timeout_seconds) || 900;
  const idleMs = idleSeconds * 1000;
  const activityIntervalMs = Math.min(45000, Math.max(1000, Math.floor(idleMs / 3)));
  const statusIntervalMs = Math.min(300000, Math.max(30000, Math.floor(idleMs / 3)));
  const warningMs = 15000;
  let lastRequestAt = Date.now();
  let activitySent = false;
  const devSessionCountdown = document.getElementById("devSessionCountdown");

  const warning = document.createElement("div");
  warning.className = "ija-session-warning position-fixed top-50 start-50 translate-middle p-4 text-center";
  warning.setAttribute("role", "alert");
  warning.setAttribute("aria-live", "polite");
  warning.hidden = true;
  const title = document.createElement("h2");
  title.className = "ija-session-warning-title h4 fw-bold mb-2";
  title.textContent = "Você ainda está aí?";
  const message = document.createElement("p");
  message.className = "mb-2";
  const countdown = document.createElement("strong");
  countdown.className = "ija-session-warning-countdown d-block display-5 fw-bold mb-3";
  countdown.setAttribute("aria-hidden", "true");
  const continueButton = document.createElement("button");
  continueButton.type = "button";
  continueButton.className = "btn btn-primary fw-semibold px-4";
  continueButton.textContent = "Continuar conectado";
  warning.append(title, message, countdown, continueButton);
  document.body.append(warning);

  function renderSessionState() {
    const remainingMs = Math.max(0, deadline - Date.now());
    const seconds = Math.ceil(remainingMs / 1000);
    warning.hidden = remainingMs > warningMs || leaving;
    continueButton.hidden = absolute;
    const warningMessage = absolute
      ? "Sua sessão atingirá o limite de duração em até 15 segundos."
      : "Sua sessão será encerrada por inatividade em até 15 segundos.";
    if (message.textContent !== warningMessage) message.textContent = warningMessage;
    const countdownLabel = `00:${String(seconds).padStart(2, "0")}`;
    if (countdown.textContent !== countdownLabel) countdown.textContent = countdownLabel;
    if (devSessionCountdown) {
      const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
      const remainder = String(seconds % 60).padStart(2, "0");
      const label = `${minutes}:${remainder}`;
      if (devSessionCountdown.textContent !== label) devSessionCountdown.textContent = label;
    }
  }

  renderSessionState();

  function goToLogin() {
    if (leaving) return;
    leaving = true;
    window.location.assign(config.login_url);
  }

  async function sync(activity = false) {
    if (inFlight || leaving) return;
    inFlight = true;
    if (activity) activitySent = true;
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
      const now = Date.now();
      confirmedDeadline = now + data.expires_in * 1000;
      absoluteDeadline = Number.isFinite(data.absolute_expires_in)
        ? now + data.absolute_expires_in * 1000 : Infinity;
      const newerActivity = pendingActivityAt && (!activity || pendingActivityAt > sentActivityAt);
      deadline = newerActivity
        ? Math.min(absoluteDeadline, Math.max(deadline, confirmedDeadline))
        : confirmedDeadline;
      absolute = Number.isFinite(absoluteDeadline) && absoluteDeadline <= deadline;
      if (activity && pendingActivityAt === sentActivityAt) pendingActivityAt = 0;
      renderSessionState();
    } catch (_) {
      deadline = confirmedDeadline;
      renderSessionState();
      if (Date.now() >= deadline) goToLogin();
    } finally {
      clearTimeout(abortTimer);
      inFlight = false;
      if (!leaving && !activity && pendingActivityAt && Date.now() < confirmedDeadline) sync(true);
    }
  }

  function recordActivity(event, forceRenewal = false) {
    if (!event.isTrusted || document.visibilityState !== "visible") return;
    const now = Date.now();
    if (now >= deadline && !inFlight) {
      sync(false);
      return;
    }
    const warningVisible = !warning.hidden;
    pendingActivityAt = now;
    deadline = Math.min(absoluteDeadline, Math.max(deadline, now + idleMs));
    absolute = Number.isFinite(absoluteDeadline) && absoluteDeadline <= deadline;
    if (!warning.hidden) warning.hidden = true;
    if (devSessionCountdown) renderSessionState();
    if (!activitySent || forceRenewal || warningVisible || shouldSendActivity(now)) sync(true);
  }
  function shouldSendActivity(now) {
    return now - lastRequestAt >= activityIntervalMs ||
      (confirmedDeadline - now <= Math.max(activityIntervalMs, 5000) && now - lastRequestAt >= 1000);
  }
  for (const eventName of ["pointerdown", "pointermove", "click", "keydown", "input", "change", "wheel", "touchstart", "touchmove"]) {
    document.addEventListener(eventName, recordActivity, { passive: true });
  }
  continueButton.addEventListener("click", (event) => {
    if (!event.isTrusted) return;
    recordActivity(event, true);
  });
  document.addEventListener("visibilitychange", () => {
    // Returning to a tab checks the server before attempting to renew anything.
    if (document.visibilityState === "visible") sync(false);
  });

  setInterval(() => {
    if (leaving) return;
    const now = Date.now();
    const warningWasHidden = warning.hidden;
    renderSessionState();
    // Other tabs share the cookie. Confirm expiry with the server before leaving.
    if (now >= deadline) sync(false);
    else if (warningWasHidden && !warning.hidden) sync(false);
    else if (pendingActivityAt && shouldSendActivity(now)) sync(true);
    else if (document.visibilityState === "visible" && now - lastRequestAt >= statusIntervalMs) sync(false);
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
