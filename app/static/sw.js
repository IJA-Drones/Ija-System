// static/sw.js — servido em /sw.js (escopo raiz). Sem cache de páginas: só instalação e push.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => { event.respondWith(fetch(event.request)); });

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
