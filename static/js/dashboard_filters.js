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
    if (!container) {
      return;
    }
    const overlay = ensureLoadingOverlay(container);
    overlay.classList.toggle('is-active', Boolean(isLoading));
  };

  const bindDashboardFilter = () => {
    const container = document.getElementById('dashboard-data-container');
    if (!container) {
      return;
    }

    const form = container.querySelector('.period-filter');
    if (!form || form.dataset.ajaxBound === '1') {
      return;
    }

    form.dataset.ajaxBound = '1';
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      setLoading(container, true);

      const url = new URL(window.location.href);
      const params = new URLSearchParams(new FormData(form));
      params.set('partial', '1');
      url.search = params.toString();

      try {
        const response = await fetch(url.toString(), {
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        });
        if (!response.ok) {
          throw new Error('Falha ao atualizar dashboard');
        }

        const html = await response.text();
        container.outerHTML = html;

        const cleanUrl = new URL(window.location.href);
        params.delete('partial');
        cleanUrl.search = params.toString();
        window.history.replaceState({}, '', cleanUrl.toString());

        if (typeof window.initDashboardCharts === 'function') {
          window.initDashboardCharts();
        }
        bindDashboardFilter();
      } catch (error) {
        setLoading(container, false);
        form.submit();
      }
    });
  };

  bindDashboardFilter();
})();
