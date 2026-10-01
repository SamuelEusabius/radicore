/* ============================================================
   Sidebar — collapse (desktop), mobile drawer, active state
   ============================================================ */
(function() {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('sidebarToggle');
  const backdrop = document.getElementById('mobileBackdrop');

  if (!sidebar || !toggle) return;

  const STORAGE_KEY = 'sidebar-collapsed';
  const isMobile = () => window.innerWidth <= 768;

  // Restore collapsed state (desktop only)
  if (!isMobile() && localStorage.getItem(STORAGE_KEY) === 'true') {
    sidebar.classList.add('collapsed');
  }

  toggle.addEventListener('click', () => {
    if (isMobile()) {
      sidebar.classList.toggle('mobile-open');
      backdrop.classList.toggle('open');
    } else {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem(STORAGE_KEY, sidebar.classList.contains('collapsed'));
    }
  });

  // Close mobile drawer on backdrop click
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('mobile-open');
      backdrop.classList.remove('open');
    });
  }

  // Mark active link based on current URL
  const currentPath = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href && href !== '/' && currentPath.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // Auto-close mobile drawer on resize to desktop
  window.addEventListener('resize', () => {
    if (!isMobile()) {
      sidebar.classList.remove('mobile-open');
      if (backdrop) backdrop.classList.remove('open');
    }
  });
})();