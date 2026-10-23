// static/sw.js — servido em /sw.js (escopo raiz). Push em qualquer página + cache do shell do aplicativo (/m/).
const CACHE = "ija-app-movel-v1";
const SHELL = ["/m/", "/static/css/app-movel.css", "/static/js/app-movel.js", "/static/img/logo_oceano_azul_light.png",
  "/static/img/icon-192.png", "/static/img/icon-512.png", "/static/manifest-portal.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {}).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) { event.respondWith(fetch(event.request)); return; }
  if (url.pathname === "/m/" || url.pathname === "/m") {
    // Shell: rede primeiro (token CSRF e versão novos), cache quando sem rede.
    event.respondWith(fetch(event.request).then((response) => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put("/m/", copy)); }
      return response;
    }).catch(() => caches.match("/m/")));
    return;
  }
  if (SHELL.includes(url.pathname)) {
    // Arquivos do shell: cache primeiro; a constante CACHE invalida tudo ao mudar de versão.
    event.respondWith(caches.match(url.pathname).then((hit) => hit || fetch(event.request).then((response) => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put(url.pathname, copy)); }
      return response;
    })));
    return;
  }
  event.respondWith(fetch(event.request)); // /api/ e demais rotas: só rede
});

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || "Alerta de vigilância em saúde";
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || "", icon: "/static/img/icon-192.png", badge: "/static/img/icon-192.png",
    tag: data.tag || "ija-alerta", renotify: true, vibrate: [200, 100, 200], timestamp: Date.now(),
    data: { url: data.url || "/portal-cidadao" },
    actions: [{ action: "abrir", title: "Ver no portal" }],
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/portal-cidadao";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const client of list) { if ("focus" in client) { client.navigate(url); return client.focus(); } }
    return self.clients.openWindow(url);
  }));
});

// O navegador pode trocar a inscrição; reinscreve com a mesma chave e avisa o servidor.
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil((async () => {
    const response = await fetch("/api/push/chave-publica", { cache: "no-store" });
    const { publicKey } = await response.json();
    if (!publicKey) return;
    const padding = "=".repeat((4 - publicKey.length % 4) % 4);
    const raw = atob((publicKey + padding).replace(/-/g, "+").replace(/_/g, "/"));
    const key = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    const subscription = await self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    await fetch("/api/push/inscrever", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canal: "webpush", subscription: subscription.toJSON() }) });
  })());
});
