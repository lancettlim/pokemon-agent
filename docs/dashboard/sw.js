/* Offline at the venue (docs/upgrade-plan-2027q2.md, Q5): a service worker
 * that keeps the dashboard usable on bad convention Wi-Fi. pipelines/
 * dashboard/build.py writes this file with BUILD (a hash of the files it
 * precaches, so a deploy that changes nothing keeps the cache) and
 * PRECACHE (the page, its scripts and font, the core shard and the default
 * regulation's shard).
 *
 *   - Pages, scripts and data: network first, so an online visitor always
 *     gets the latest build; each response is saved, and offline the saved
 *     copy answers. Whatever shard a visitor opened (another regulation,
 *     the calculator's head-to-head) is there next time.
 *   - Images: cache first; a sprite never changes under its name.
 *   - Other origins are left alone.
 *
 * A new build's worker takes over at once and deletes older caches. */
"use strict";

var BUILD = "489225398974";
var PREFIX = "champions-data-";
var CACHE = PREFIX + BUILD;
var PRECACHE = ["./", "index.html", "app.js", "matchup.js", "teams.js", "expansions.js", "events.js", "players.js", "ladder.js", "search.js", "fonts/oswald-latin-wght.woff2", "data/core.json", "data/scope-m-c.json"];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(PRECACHE); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (key) {
          return key.indexOf(PREFIX) === 0 && key !== CACHE;
        }).map(function (key) { return caches.delete(key); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

function save(request, response) {
  if (response && response.ok && response.type === "basic") {
    var copy = response.clone();
    caches.open(CACHE).then(function (cache) { cache.put(request, copy); });
  }
  return response;
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;
  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.indexOf("/images/") !== -1) {
    event.respondWith(
      caches.match(request).then(function (hit) {
        return hit || fetch(request).then(function (response) { return save(request, response); });
      })
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then(function (response) { return save(request, response); })
      .catch(function () {
        // A page opened with another ?reg= is still the one page.
        var navigation = request.mode === "navigate";
        return caches.match(request, { ignoreSearch: navigation })
          .then(function (hit) {
            if (hit || !navigation) return hit;
            return caches.match(new URL("index.html", self.registration.scope).href);
          })
          .then(function (hit) { return hit || Response.error(); });
      })
  );
});
