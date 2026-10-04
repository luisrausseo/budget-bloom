// Execute the actual worker with fake Fetch/Cache APIs; no private response may
// reach Cache.put, even for redirects, errors, unknown paths or query strings.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const origin = 'https://budget.example';
const assets = ['/static/styles.css?v=test', '/static/app.js?v=test', '/static/icons/icon-192.png?v=test', '/static/offline.html?v=test'];
const source = fs.readFileSync('static/sw.js', 'utf8').replaceAll('__PWA_VERSION__', 'test').replace('__PWA_ASSETS__', JSON.stringify(assets));
const handlers = {}, saved = new Map(), calls = [], removed = [];
const cache = {put: async (url, response) => saved.set(new URL(url, origin).href, response),
  match: async request => saved.get(new URL(typeof request === 'string' ? request : request.url, origin).href)?.clone()};
let offline = false, redirect = false;
const context = {URL, Response, Set, Map, self: {location: {origin}, addEventListener: (event, fn) => handlers[event] = fn,
  skipWaiting: async () => {}, clients: {claim: async () => {}}},
  caches: {open: async () => cache, keys: async () => ['budget-bloom-static-old', 'unrelated-cache', 'budget-bloom-static-test'], delete: async name => removed.push(name)},
  fetch: async (request, options) => {
    calls.push({request, options});
    if (offline) throw new Error('Network offline');
    const path = typeof request === 'string' ? request : request.url;
    const type = path.includes('.css?') ? 'text/css' : path.includes('.js?') ? 'application/javascript' : path.includes('.png?') ? 'image/png' : 'text/html';
    const response = new Response(path.includes('offline.html') ? 'Generic offline message' : 'synthetic-private-response', {headers: {'Content-Type': type}});
    if (redirect) Object.defineProperty(response, 'redirected', {value: true});
    return response;
  }};
vm.runInNewContext(source, context);
const run = async event => {let promise; handlers[event]({waitUntil: p => promise = p}); await promise;};
const request = (path, mode = 'cors', method = 'GET') => ({url: new URL(path, origin).href, mode, method});
const dispatch = async req => {let response; handlers.fetch({request: req, respondWith: p => response = p}); return response ? await response : null;};
(async () => {
  await run('install');
  assert.deepEqual([...saved.keys()], assets.map(path => new URL(path, origin).href));
  assert(calls.every(call => call.options.credentials === 'omit' && call.options.cache === 'no-store'));
  await run('activate');
  assert.deepEqual(removed, ['budget-bloom-static-old']);
  for (const path of ['/', '/?month=2026-01', '/security', '/groceries', '/login', '/register?code=secret']) {
    const response = await dispatch(request(path, 'navigate'));
    assert.equal(await response.text(), 'synthetic-private-response');
    assert.equal(calls.at(-1).options.cache, 'no-store');
    assert.equal(saved.size, assets.length);
  }
  for (const req of [request('/api/budget'), request('/security'), request('/static/unknown.js'),
    request('/static/app.js?token=secret'), request('/static/app.js?v=old'),
    request('https://supabase.example/rest/v1/entries'), request('/entries', 'cors', 'POST')]) {
    const before = calls.length;
    assert.equal(await dispatch(req), null);
    assert.equal(calls.length, before);
  }
  offline = true;
  for (const path of ['/', '/security', '/groceries', '/login']) {
    const response = await dispatch(request(path, 'navigate'));
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
    assert.equal(await response.text(), 'Generic offline message');
  }
  assert(await dispatch(request('/static/app.js?v=test')));
  assert(await dispatch(request('/static/styles.css')));
  assert.equal(saved.size, assets.length);
  offline = false; redirect = true; saved.clear();
  await assert.rejects(run('install'), /Public PWA asset unavailable/);
  assert.equal(saved.size, 0);
  console.log('PWA worker checks passed: exact allowlist, no private writes, offline fallback, cache cleanup, redirect rejection.');
})().catch(error => {console.error(error); process.exitCode = 1;});
