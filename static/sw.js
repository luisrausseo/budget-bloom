// Rendered by /sw.js with a content-derived version and an exact public allowlist.
const CACHE_PREFIX = 'budget-bloom-static-';
const CACHE_NAME = `${CACHE_PREFIX}__PWA_VERSION__`;
const ASSETS = __PWA_ASSETS__;
const OFFLINE_URL = ASSETS.find(path => path.startsWith('/static/offline.html?'));
const assetURLs = new Set(ASSETS.map(path => new URL(path, self.location.origin).href));
const unversionedAssets = new Map(ASSETS.map(path => [path.split('?')[0], path]));

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    // Cookies are unnecessary for public assets. Check types and redirects so
    // an upstream login/error HTML response cannot be saved as CSS/JS/an icon.
    for (const path of ASSETS) {
      const response = await fetch(path, {credentials: 'omit', cache: 'no-store'});
      const type = response.headers.get('Content-Type') || '';
      const expected = path.includes('.css?') ? 'text/css' : path.includes('.js?') ? 'javascript' :
        path.includes('.png?') ? 'image/png' : 'text/html';
      if (!response.ok || response.redirected || !type.includes(expected)) {
        throw new Error('Public PWA asset unavailable');
      }
      await cache.put(path, response);
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    // NEVER put navigations in Cache Storage, including login, account pages,
    // redirects and errors. Bypass the HTTP cache as well.
    event.respondWith((async () => {
      try {
        return await fetch(request, {cache: 'no-store'});
      } catch {
        const cache = await caches.open(CACHE_NAME);
        const offline = await cache.match(OFFLINE_URL);
        return new Response(offline ? await offline.text() : 'Budget Bloom is offline. Connect to the internet to continue.', {
          status: 503,
          headers: {
            'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
          },
        });
      }
    })());
    return;
  }

  // No runtime writes. Unknown static paths, query strings, APIs, and Supabase
  // requests are untouched. Listed assets may use their current version or no
  // query string (the self-contained offline page uses unversioned stylesheets).
  const publicAsset = assetURLs.has(url.href) ? url.href :
    !url.search ? unversionedAssets.get(url.pathname) : null;
  if (publicAsset) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      return await cache.match(publicAsset) || fetch(request, {credentials: 'omit', cache: 'no-store'});
    })());
  }
});
