(function () {
  if (window.__dashboardSidebarBound) {
    return;
  }
  window.__dashboardSidebarBound = true;

  const toggleButton = document.querySelector('[data-sidebar-toggle]');
  const layoutRoot = document.documentElement;
  const sidebarStateKey = 'nr1_sidebar_collapsed';
  const menuLinks = document.querySelectorAll('.menu__item[data-match-path]');
  const submenuLinks = document.querySelectorAll('.menu__subitem[data-match-path]');
  const groupToggles = document.querySelectorAll('[data-menu-group-toggle]');
  const menuGroups = document.querySelectorAll('[data-menu-group]');

  function getPersistedSidebarState() {
    try {
      return window.localStorage.getItem(sidebarStateKey);
    } catch (error) {
      return null;
    }
  }

  function persistSidebarState(isCollapsed) {
    try {
      window.localStorage.setItem(sidebarStateKey, isCollapsed ? '1' : '0');
    } catch (error) {
      // Ignore storage failures (privacy mode, blocked storage, etc.).
    }
  }

  function applyPersistedSidebarState() {
    const persistedState = getPersistedSidebarState();
    if (persistedState === '1') {
      layoutRoot.classList.add('layout-collapsed');
      return;
    }
    if (persistedState === '0') {
      layoutRoot.classList.remove('layout-collapsed');
    }
  }

  function isSidebarCollapsed() {
    return layoutRoot.classList.contains('layout-collapsed');
  }

  function closeAllMenuGroups() {
    menuGroups.forEach(function (group) {
      group.classList.remove('is-open');
    });
  }

  function syncSidebarToggleState() {
    if (!toggleButton) {
      return;
    }
    const isCollapsed = layoutRoot.classList.contains('layout-collapsed');
    toggleButton.setAttribute('aria-expanded', String(!isCollapsed));
    toggleButton.setAttribute(
      'aria-label',
      isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'
    );
  }

  applyPersistedSidebarState();

  if (toggleButton) {
    syncSidebarToggleState();
    toggleButton.addEventListener('click', function () {
      layoutRoot.classList.toggle('layout-collapsed');
      if (isSidebarCollapsed()) {
        closeAllMenuGroups();
      }
      persistSidebarState(layoutRoot.classList.contains('layout-collapsed'));
      syncSidebarToggleState();
    });
  }

  const path = window.location.pathname;
  menuLinks.forEach(function (link) {
    const matchPath = link.getAttribute('data-match-path');
    if (matchPath && path.startsWith(matchPath)) {
      link.classList.add('is-active');
    }
  });

  submenuLinks.forEach(function (link) {
    const matchPath = link.getAttribute('data-match-path');
    if (matchPath && path.startsWith(matchPath)) {
      link.classList.add('is-active');
      const group = link.closest('[data-menu-group]');
      if (group) {
        group.classList.add('is-open');
      }
    }
  });

  if (isSidebarCollapsed()) {
    closeAllMenuGroups();
  }

  groupToggles.forEach(function (button) {
    button.addEventListener('click', function () {
      const group = button.closest('[data-menu-group]');
      if (group) {
        if (isSidebarCollapsed()) {
          const shouldOpen = !group.classList.contains('is-open');
          closeAllMenuGroups();
          if (shouldOpen) {
            group.classList.add('is-open');
          }
          return;
        }
        group.classList.toggle('is-open');
      }
    });
  });

  document.addEventListener('click', function (event) {
    if (!isSidebarCollapsed()) {
      return;
    }
    if (event.target.closest('[data-menu-group]')) {
      return;
    }
    closeAllMenuGroups();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') {
      return;
    }
    if (!isSidebarCollapsed()) {
      return;
    }
    closeAllMenuGroups();
  });
})();
