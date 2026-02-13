(function () {
  if (window.__dashboardSidebarBound) {
    return;
  }
  window.__dashboardSidebarBound = true;

  const MOBILE_BREAKPOINT = '(max-width: 980px)';
  const mobileQuery = window.matchMedia(MOBILE_BREAKPOINT);
  const mobileOpenClass = 'layout-mobile-sidebar-open';
  const toggleButton = document.querySelector('[data-sidebar-toggle]');
  const mobileTriggerButton = document.querySelector('[data-sidebar-mobile-trigger]');
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
    if (isMobileViewport()) {
      layoutRoot.classList.remove('layout-collapsed');
      return;
    }
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

  function isMobileViewport() {
    return mobileQuery.matches;
  }

  function isMobileSidebarOpen() {
    return layoutRoot.classList.contains(mobileOpenClass);
  }

  function setMobileSidebarState(isOpen) {
    layoutRoot.classList.toggle(mobileOpenClass, isOpen);
  }

  function closeAllMenuGroups() {
    menuGroups.forEach(function (group) {
      group.classList.remove('is-open');
    });
  }

  function syncSidebarToggleState() {
    if (isMobileViewport()) {
      const isOpen = isMobileSidebarOpen();
      if (toggleButton) {
        toggleButton.setAttribute('aria-expanded', String(isOpen));
        toggleButton.setAttribute(
          'aria-label',
          isOpen ? 'Fechar menu lateral' : 'Abrir menu lateral'
        );
      }
      if (mobileTriggerButton) {
        mobileTriggerButton.setAttribute('aria-expanded', String(isOpen));
        mobileTriggerButton.setAttribute(
          'aria-label',
          isOpen ? 'Fechar menu lateral' : 'Abrir menu lateral'
        );
      }
      return;
    }

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

  function handleViewportChange() {
    if (isMobileViewport()) {
      layoutRoot.classList.remove('layout-collapsed');
      closeAllMenuGroups();
    } else {
      setMobileSidebarState(false);
      applyPersistedSidebarState();
      if (isSidebarCollapsed()) {
        closeAllMenuGroups();
      }
    }
    syncSidebarToggleState();
  }

  applyPersistedSidebarState();
  handleViewportChange();

  if (toggleButton) {
    syncSidebarToggleState();
    toggleButton.addEventListener('click', function () {
      if (isMobileViewport()) {
        setMobileSidebarState(!isMobileSidebarOpen());
        syncSidebarToggleState();
        return;
      }
      layoutRoot.classList.toggle('layout-collapsed');
      if (isSidebarCollapsed()) {
        closeAllMenuGroups();
      }
      persistSidebarState(layoutRoot.classList.contains('layout-collapsed'));
      syncSidebarToggleState();
    });
  }

  if (mobileTriggerButton) {
    mobileTriggerButton.addEventListener('click', function () {
      if (!isMobileViewport()) {
        return;
      }
      setMobileSidebarState(!isMobileSidebarOpen());
      syncSidebarToggleState();
    });
  }

  if (mobileQuery.addEventListener) {
    mobileQuery.addEventListener('change', handleViewportChange);
  } else if (mobileQuery.addListener) {
    mobileQuery.addListener(handleViewportChange);
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

  // Guarantee Cadastros group stays open for GHE/Funcoes routes.
  if (path.startsWith('/ghes/') || path.startsWith('/job-functions/')) {
    const group = document.querySelector('[data-menu-group]');
    if (group) {
      group.classList.add('is-open');
    }
  }

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
    const menuItemLink = event.target.closest('.menu__item[href], .menu__subitem[href]');
    if (menuItemLink && isMobileViewport()) {
      setMobileSidebarState(false);
      closeAllMenuGroups();
      syncSidebarToggleState();
      return;
    }

    if (isMobileViewport() && isMobileSidebarOpen()) {
      if (
        !event.target.closest('.sidebar') &&
        !event.target.closest('[data-sidebar-mobile-trigger]')
      ) {
        setMobileSidebarState(false);
        closeAllMenuGroups();
        syncSidebarToggleState();
      }
      return;
    }

    const submenuLink = event.target.closest('.menu__subitem');
    if (submenuLink && isSidebarCollapsed()) {
      closeAllMenuGroups();
      return;
    }
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
    if (isMobileViewport() && isMobileSidebarOpen()) {
      setMobileSidebarState(false);
      closeAllMenuGroups();
      syncSidebarToggleState();
      return;
    }
    if (!isSidebarCollapsed()) {
      return;
    }
    closeAllMenuGroups();
  });
})();
