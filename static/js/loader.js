/* ==========================================================
   SCHOOL MS — Page Loader (v2)
   Loader HTML is already in the page. This script just hides it.
   ========================================================== */

(function () {
  'use strict';

  function hideLoader() {
    const loader = document.getElementById('page-loader');
    if (!loader) return;
    loader.classList.add('hidden');
  }

  function showLoader() {
    const loader = document.getElementById('page-loader');
    if (!loader) {
      // Loader HTML missing — inject it now
      injectLoader();
      return;
    }
    loader.classList.remove('hidden');
  }

  function injectLoader() {
    if (document.getElementById('page-loader')) return;
    const loader = document.createElement('div');
    loader.id = 'page-loader';
    loader.innerHTML = `
      <div class="loader-spinner"></div>
      <div class="loader-brand">
        <div class="loader-logo">SM</div>
        <div>
          <div class="loader-text">School MS</div>
          <div class="loader-subtext">Loading...</div>
        </div>
      </div>
      <div class="loader-progress">
        <div class="loader-progress-bar"></div>
      </div>
    `;
    document.body.appendChild(loader);
  }

  // Hide loader as soon as the DOM is ready
  // (unless it's the very first paint — then slightly delay for polish)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(hideLoader, 200);
    });
  } else {
    setTimeout(hideLoader, 200);
  }

  // Ensure loader is hidden on window load (after all assets)
  window.addEventListener('load', function () {
    setTimeout(hideLoader, 150);
  });

  // Handle browser back/forward cache
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) hideLoader();
  });

  // Show loader when clicking internal links
  document.addEventListener('click', function (e) {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (
      !href ||
      href.startsWith('#') ||
      href.startsWith('javascript:') ||
      href.startsWith('mailto:') ||
      href.startsWith('tel:') ||
      link.target === '_blank' ||
      link.hasAttribute('download') ||
      link.hostname !== window.location.hostname
    ) {
      return;
    }

    showLoader();
  });

  // Show loader on form submits (except ones marked to skip)
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (form.dataset.skipLoader === 'true') return;
    showLoader();
  });

  // Handle admin logout form (POST submits) — same as above

})();