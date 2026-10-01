/* ============================================================
   Toast — programmatic notifications
   ============================================================ */
(function() {
  const container = () => {
    let el = document.getElementById('toastContainer');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toastContainer';
      el.className = 'toast-container';
      document.body.appendChild(el);
    }
    return el;
  };

  window.toast = function(message, type = 'info', title = '') {
    const titles = { success: 'Success', error: 'Error', warning: 'Warning', info: 'Notice' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <div class="toast-content">
        <div class="toast-title">${title || titles[type]}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button type="button" class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    container().appendChild(el);
    setTimeout(() => el.remove(), 5000);
  };
})();