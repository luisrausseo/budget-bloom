(() => {
  const storageKey = 'budget-bloom-theme';
  let saved = null;
  try { saved = localStorage.getItem(storageKey); } catch (error) { /* Use device preference. */ }
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const apply = theme => {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('.theme-toggle').forEach(button => {
      const dark = theme === 'dark';
      button.textContent = dark ? '☀' : '☾';
      button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
      button.title = dark ? 'Light mode' : 'Dark mode';
    });
  };

  apply(saved === 'dark' || saved === 'light' ? saved : preferred);
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.theme);
    document.querySelectorAll('.theme-toggle').forEach(button => button.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(storageKey, next); } catch (error) { /* Theme still applies for this page. */ }
      apply(next);
    }));
  });
})();
