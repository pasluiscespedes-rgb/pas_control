const CACHE_NAME = "fortex-v1";

self.addEventListener("install", () => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
    // Por ahora dejamos que FORTEX trabaje siempre online.
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();

    event.waitUntil(
        clients.openWindow("/whatsapp/")
    );
});



self.addEventListener("push", (event) => {
    const data = event.data
        ? event.data.json()
        : {};

    const title = data.title || "FORTEX WhatsApp";

    const options = {
        body: data.body || "Tenés un nuevo mensaje de WhatsApp.",
        icon: "/static/principal/img/icon-192.png",
        badge: "/static/principal/img/icon-192.png",
        data: {
            url: data.url || "/whatsapp/"
        }
    };

    event.waitUntil(
        self.registration.showNotification(
            title,
            options
        )
    );
});