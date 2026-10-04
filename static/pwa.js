// Installation is progressive enhancement; normal browsing needs no worker.
(() => {
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js', {scope: '/', updateViaCache: 'none'})
      .catch(() => console.warn('Budget Bloom installation support is unavailable.'));
  }

  // A visible page or a back/forward snapshot is not a service-worker cache.
  // Remove its private DOM before leaving it and revalidate restored pages.
  function hidePrivatePage() {
    document.body.replaceChildren();
    const message = document.createElement('p');
    message.textContent = 'Budget Bloom — connect to the internet to continue.';
    message.setAttribute('role', 'status');
    document.body.append(message);
  }
  function goOffline() {
    if (location.pathname === '/static/offline.html') return;
    hidePrivatePage();
    location.replace('/static/offline.html');
  }
  // Notify other open tabs after authentication changes. No identity, token,
  // or budget content is sent or persisted; each tab reloads from the server.
  if ('BroadcastChannel' in window) {
    const authChanges = new BroadcastChannel('budget-bloom-auth');
    window.addEventListener('budget-auth-changed', () => authChanges.postMessage('refresh'));
    authChanges.addEventListener('message', event => {
      if (event.data !== 'refresh') return;
      hidePrivatePage();
      location.replace('/');
    });
  }
  window.addEventListener('offline', goOffline);
  window.addEventListener('pagehide', hidePrivatePage);
  window.addEventListener('pageshow', event => {
    if (!navigator.onLine) goOffline();
    else if (event.persisted) {
      hidePrivatePage();
      location.reload();
    }
  });
  if (!navigator.onLine) goOffline();
})();
