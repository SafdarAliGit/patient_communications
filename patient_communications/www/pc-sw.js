// Minimal service worker — satisfies Chrome's PWA installability requirement.
// No caching: all requests pass through to the network unchanged.
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(clients.claim()); });
