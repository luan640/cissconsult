(function () {
  const spinnerMarkup =
    '<div class="table-loading-overlay__inner">' +
    '<div class="app-spinner" role="status" aria-live="polite" aria-label="Carregando">' +
    '<span class="app-spinner__ring"></span>' +
    '</div></div>';

  const ensureLoadingOverlay = (container) => {
    let overlay = container.querySelector('[data-table-loading-overlay]');
    if (overlay) {
      return overlay;
    }
    overlay = document.createElement('div');
    overlay.className = 'table-loading-overlay';
    overlay.setAttribute('data-table-loading-overlay', '1');
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML = spinnerMarkup;
    container.appendChild(overlay);
    return overlay;
  };

  const setLoading = (container, isLoading) => {
    const overlay = ensureLoadingOverlay(container);
    overlay.classList.toggle('is-active', Boolean(isLoading));
  };

  const buildPartialUrl = (href) => {
    const url = new URL(href, window.location.origin);
    url.searchParams.set('partial', '1');
    return url.toString();
  };

  const buildPartialUrlFromForm = (form) => {
    const url = new URL(form.action, window.location.origin);
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      const trimmed = typeof value === 'string' ? value.trim() : value;
      if (trimmed) {
        params.append(key, trimmed);
      }
    });
    params.set('partial', '1');
    url.search = params.toString();
    return url.toString();
  };

  const syncBrowserUrlFromForm = (form) => {
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      const trimmed = typeof value === 'string' ? value.trim() : value;
      if (trimmed) {
        params.append(key, trimmed);
      }
    });
    const nextUrl = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    window.history.replaceState({}, '', nextUrl);
  };

  document.addEventListener('click', async (event) => {
    const link = event.target.closest('.table-pagination__link[href]');
    if (!link || link.classList.contains('is-disabled')) {
      return;
    }

    const container = link.closest('[data-table-container]');
    if (!container) {
      return;
    }

    event.preventDefault();
    setLoading(container, true);
    try {
      const response = await fetch(buildPartialUrl(link.href), {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!response.ok) {
        throw new Error('Falha ao carregar pagina da tabela.');
      }
      container.outerHTML = await response.text();
      window.history.replaceState({}, '', link.href);
    } catch (error) {
      window.location.assign(link.href);
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form.matches('[data-ajax-table-form]')) {
      return;
    }
    const containerId = form.getAttribute('data-table-container-id');
    const container = containerId ? document.getElementById(containerId) : null;
    if (!container) {
      return;
    }
    event.preventDefault();
    setLoading(container, true);
    try {
      const response = await fetch(buildPartialUrlFromForm(form), {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!response.ok) {
        throw new Error('Falha ao carregar filtro da tabela.');
      }
      container.outerHTML = await response.text();
      syncBrowserUrlFromForm(form);
    } catch (error) {
      form.submit();
    }
  });
})();
