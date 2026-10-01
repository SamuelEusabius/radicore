/* ============================================================
   Theme — light/dark mode toggle
   ============================================================ */
(function() {
  const STORAGE_KEY = 'theme';
  const html = document.documentElement;

  // Restore saved theme
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'dark' || saved === 'light') {
    html.setAttribute('data-theme', saved);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    html.setAttribute('data-theme', 'dark');
  }

  // Expose global toggle
  window.toggleTheme = function() {
    const current = html.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem(STORAGE_KEY, next);
  };
})();