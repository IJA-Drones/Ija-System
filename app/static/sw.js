// static/sw.js — sem cache: só mantém o app instalável e recebe push.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => { event.respondWith(fetch(event.request)); });

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || "Alerta de vigilância em saúde";
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || "", icon: "/static/img/icon-192.png", badge: "/static/img/icon-192.png",
    tag: data.tag || "ija-alerta", renotify: true, data: { url: data.url || "/portal-cidadao" },
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
