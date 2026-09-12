(() => {
  const t = text => window.budgetTranslate ? window.budgetTranslate(text) : text;
  const storageKey = 'budget-bloom-theme';
  let saved = null;
  try { saved = localStorage.getItem(storageKey); } catch (error) { /* Use device preference. */ }
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const apply = theme => {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('.theme-toggle').forEach(button => {
      const dark = theme === 'dark';
      button.textContent = dark ? '☀' : '☾';
      button.setAttribute('aria-label', dark ? t('Switch to light mode') : t('Switch to dark mode'));
      button.title = dark ? t('Light mode') : t('Dark mode');
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
