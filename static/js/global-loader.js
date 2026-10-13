/* ==========================================================
   ELIMUCORE — Global Loading System
   Public API:
     ElimuCoreLoader.show()      — show loader
     ElimuCoreLoader.hide()      — hide loader
     ElimuCoreLoader.wrap(p)     — show while promise runs, hide in finally

   Auto-wiring:
     - Internal link clicks
     - Form submissions (except data-skip-loader="true")
     - Browser back/forward cache (pageshow) — auto-hide
   ========================================================== */

(function (window, document) {
  'use strict';

  var LOADER_ID = 'ec-loader';
  var ACTIVE_CLASS = 'ec-active';
  var SAFETY_TIMEOUT_MS = 30000; // auto-hide after 30s to prevent permanent freeze

  var activeCount = 0;
  var safetyTimer = null;
  var pendingHideTimer = null;

  function getLoader() {
    return document.getElementById(LOADER_ID);
  }

  function clearTimers() {
    if (safetyTimer) {
      clearTimeout(safetyTimer);
      safetyTimer = null;
    }
    if (pendingHideTimer) {
      clearTimeout(pendingHideTimer);
      pendingHideTimer = null;
    }
  }

  function show() {
    var loader = getLoader();
    if (!loader) return;

    // Cancel any pending hide
    if (pendingHideTimer) {
      clearTimeout(pendingHideTimer);
      pendingHideTimer = null;
    }

    activeCount += 1;

    if (activeCount === 1) {
      loader.classList.add(ACTIVE_CLASS);
      loader.setAttribute('aria-hidden', 'false');

      // Safety: auto-hide after 30s
      if (safetyTimer) clearTimeout(safetyTimer);
      safetyTimer = setTimeout(function () {
        activeCount = 0;
        hide(true);
      }, SAFETY_TIMEOUT_MS);
    }
  }

  function hide(force) {
    var loader = getLoader();
    if (!loader) return;

    if (force) {
      activeCount = 0;
    } else {
      activeCount = Math.max(0, activeCount - 1);
    }

    if (activeCount === 0) {
      // Small delay so it doesn't flash on very fast navigations
      pendingHideTimer = setTimeout(function () {
        loader.classList.remove(ACTIVE_CLASS);
        loader.setAttribute('aria-hidden', 'true');
        clearTimers();
      }, 180);
    }
  }

  function wrap(promise) {
    show();
    return Promise.resolve(promise).finally(function () {
      hide();
    });
  }

  // ---------- AUTO-WIRING: internal link clicks ----------
  document.addEventListener('click', function (e) {
    // Ignore clicks with modifier keys (open in new tab, etc.)
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    var link = e.target.closest ? e.target.closest('a') : null;
    if (!link) return;

    // Skip links we should not intercept
    if (link.target === '_blank') return;
    if (link.hasAttribute('download')) return;

    var href = link.getAttribute('href');
    if (!href) return;
    if (href.charAt(0) === '#') return;
    if (/^(javascript|mailto|tel|sms):/i.test(href)) return;

    // External link?
    try {
      var url = new URL(link.href, window.location.href);
      if (url.hostname !== window.location.hostname) return;
      // Same hostname but no navigation (same page)
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
    } catch (err) {
      return;
    }

    // It's an internal navigation — show loader
    show();
  }, true);

  // ---------- AUTO-WIRING: form submissions ----------
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;

    // Respect the opt-out attribute
    if (form.dataset && form.dataset.skipLoader === 'true') return;

    // Skip if form uses GET (e.g. filters) — those don't need a loader
    if ((form.method || '').toLowerCase() === 'get') return;

    show();
  }, true);

  // ---------- BACK / FORWARD CACHE ----------
  window.addEventListener('pageshow', function (e) {
    // If restored from bfcache, force-hide the loader
    if (e.persisted) {
      hide(true);
    }
  });

  // ---------- PAGE UNLOAD SAFETY ----------
  window.addEventListener('beforeunload', function () {
    clearTimers();
  });

  // ---------- PUBLIC API ----------
  window.ElimuCoreLoader = {
    show: show,
    hide: function () { hide(true); },
    wrap: wrap
  };

})(window, document);