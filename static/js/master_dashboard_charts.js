(function () {
  if (window.__masterDashboardChartsBound) return;
  window.__masterDashboardChartsBound = true;

  const colors = ['#1d4ed8', '#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#0f766e'];

  let historyChart = null;
  let segmentChart = null;
  let activeController = null;
  let requestToken = 0;
  let inFlight = false;
  let lastLoadStart = 0;
  let chartReadyAttempts = 0;

  const debounce = (fn, wait) => {
    let timeoutId = null;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => fn(...args), wait);
    };
  };

  const clearLoaders = () => {
    const loaders = document.querySelectorAll('.master-chart-loading.is-visible');
    loaders.forEach((loader) => loader.classList.remove('is-visible'));
  };

  const initCompanyPicker = (content) => {
    const wrapper = content.querySelector('[data-master-company-picker]');
    if (!wrapper || wrapper.dataset.pickerInit === '1') return;

    const optionsUrl = content.getAttribute('data-company-options-url') || '';
    const hiddenInput = wrapper.querySelector('#master_company_id');
    const searchInput = wrapper.querySelector('[data-master-company-search]');
    const menu = wrapper.querySelector('[data-master-company-menu]');
    const optionsContainer = wrapper.querySelector('[data-master-company-options]');
    const statusContainer = wrapper.querySelector('[data-master-company-status]');
    if (!optionsUrl || !hiddenInput || !searchInput || !menu || !optionsContainer || !statusContainer) return;

    wrapper.dataset.pickerInit = '1';

    const state = {
      query: '',
      offset: 0,
      limit: 10,
      loading: false,
      hasMore: true,
      items: [],
      requestId: 0,
    };

    const setStatus = (text) => {
      statusContainer.textContent = text || '';
    };

    const closeMenu = () => {
      menu.hidden = true;
      wrapper.classList.remove('is-open');
    };

    const openMenu = () => {
      menu.hidden = false;
      wrapper.classList.add('is-open');
    };

    const selectCompany = (company) => {
      hiddenInput.value = String(company.id);
      searchInput.value = company.name || '';
      searchInput.setCustomValidity('');
      closeMenu();
      hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const renderOptions = () => {
      optionsContainer.innerHTML = '';
      if (!state.items.length) {
        setStatus('Nenhuma empresa encontrada.');
        return;
      }
      state.items.forEach((company) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'master-company-picker__option';
        button.textContent = company.name || '';
        button.dataset.companyId = String(company.id);
        button.addEventListener('click', () => selectCompany(company));
        optionsContainer.appendChild(button);
      });
      setStatus(state.hasMore ? 'Role para carregar mais.' : '');
    };

    const loadCompanies = async ({ append = false } = {}) => {
      if (state.loading) return;
      if (!append) state.offset = 0;
      state.loading = true;
      const requestId = ++state.requestId;
      setStatus('Carregando...');

      const params = new URLSearchParams();
      params.set('active_only', '1');
      params.set('offset', String(state.offset));
      params.set('limit', String(state.limit));
      if (state.query) params.set('q', state.query);

      try {
        const response = await fetch(optionsUrl + '?' + params.toString(), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error('Falha ao carregar empresas.');
        const data = await response.json();
        if (requestId !== state.requestId) return;

        const companies = Array.isArray(data?.companies) ? data.companies : [];
        state.hasMore = Boolean(data?.has_more);
        state.items = append ? state.items.concat(companies) : companies;
        state.offset = state.items.length;
        renderOptions();
      } catch (err) {
        if (requestId !== state.requestId) return;
        state.items = [];
        state.hasMore = false;
        optionsContainer.innerHTML = '';
        setStatus('Nao foi possivel carregar empresas.');
      } finally {
        if (requestId === state.requestId) state.loading = false;
      }
    };

    const startSearch = debounce(() => {
      state.query = (searchInput.value || '').trim();
      hiddenInput.value = '';
      searchInput.setCustomValidity('Selecione uma empresa da lista.');
      openMenu();
      loadCompanies();
    }, 300);

    searchInput.addEventListener('focus', () => {
      state.query = '';
      openMenu();
      loadCompanies();
    });

    searchInput.addEventListener('click', () => {
      state.query = '';
      openMenu();
      loadCompanies();
    });

    searchInput.addEventListener('input', startSearch);

    optionsContainer.addEventListener('scroll', () => {
      if (!state.hasMore || state.loading) return;
      const threshold = 18;
      const hitBottom =
        optionsContainer.scrollTop + optionsContainer.clientHeight >= optionsContainer.scrollHeight - threshold;
      if (!hitBottom) return;
      loadCompanies({ append: true });
    });

    document.addEventListener('click', (event) => {
      if (wrapper.contains(event.target)) return;
      closeMenu();
    });
  };

  const initCharts = () => {
    const content = document.querySelector('.content[data-page="master-dashboard"]');
    if (!content) return;

    initCompanyPicker(content);
    clearLoaders();

    if (activeController) {
      try {
        activeController.abort();
      } catch (err) {
        // ignore abort failures
      }
      activeController = null;
      inFlight = false;
    }

    const metricsUrl = content.getAttribute('data-master-metrics-url') || '';
    const companyIdInput = document.getElementById('master_company_id');
    if (!metricsUrl || !companyIdInput) {
      delete content.dataset.masterChartsInit;
      return;
    }

    const historyCanvas = document.getElementById('master-eval-history');
    const segmentCanvas = document.getElementById('master-segment-pie');
    const segmentList = document.getElementById('master-segment-list');
    const historyLoading = document.querySelector('[data-master-loading="history"]');
    const segmentsLoading = document.querySelector('[data-master-loading="segments"]');
    if (!historyCanvas || !segmentCanvas || !segmentList) {
      delete content.dataset.masterChartsInit;
      return;
    }

    if (typeof Chart === 'undefined') {
      chartReadyAttempts += 1;
      if (chartReadyAttempts < 30) {
        delete content.dataset.masterChartsInit;
        window.setTimeout(initCharts, 300);
      }
      return;
    }

    if (content.dataset.masterChartsInit === '1') return;
    content.dataset.masterChartsInit = '1';
    chartReadyAttempts = 0;

    const hideLoading = () => {
      clearLoaders();
      if (historyLoading) historyLoading.classList.remove('is-visible');
      if (segmentsLoading) segmentsLoading.classList.remove('is-visible');
    };

    const renderHistory = (labels, values) => {
      if (historyChart) historyChart.destroy();
      historyChart = new Chart(historyCanvas, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: 'Avaliacoes',
              data: values,
              backgroundColor: '#1d4ed8',
              borderRadius: 8,
              maxBarThickness: 28,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { grid: { display: false } },
          },
        },
      });
    };

    const renderSegments = (labels, values) => {
      if (segmentChart) segmentChart.destroy();
      segmentChart = new Chart(segmentCanvas, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: labels.map((_, idx) => colors[idx % colors.length]),
              borderWidth: 0,
              hoverOffset: 6,
            },
          ],
        },
        options: {
          cutout: '62%',
          plugins: { legend: { display: false } },
        },
      });

      segmentList.innerHTML = labels
        .map((label, idx) => {
          const value = Number(values[idx] || 0).toFixed(1);
          const color = colors[idx % colors.length];
          return (
            '<div class="master-segment-item">' +
            '<div><span class="master-segment-chip" style="background:' +
            color +
            ';"></span>' +
            label +
            '</div>' +
            '<strong>' +
            value +
            '%</strong>' +
            '</div>'
          );
        })
        .join('');
    };

    const renderEmpty = () => {
      renderHistory([], []);
      renderSegments([], []);
    };

    const loadMetrics = async (companyId, attempt = 0) => {
      if (!companyId) {
        hideLoading();
        renderEmpty();
        return;
      }
      if (typeof Chart === 'undefined') {
        if (attempt < 8) {
          window.setTimeout(() => loadMetrics(companyId, attempt + 1), 200);
        } else {
          hideLoading();
        }
        return;
      }
      if (activeController) {
        activeController.abort();
      }
      activeController = new AbortController();
      const token = ++requestToken;
      inFlight = true;
      lastLoadStart = Date.now();
      if (historyLoading) historyLoading.classList.add('is-visible');
      if (segmentsLoading) segmentsLoading.classList.add('is-visible');
      const timeoutId = window.setTimeout(() => {
        if (token !== requestToken) return;
        try {
          activeController.abort();
        } catch (err) {
          // ignore abort failures
        }
        inFlight = false;
        hideLoading();
        renderEmpty();
      }, 6000);
      try {
        const resp = await fetch(metricsUrl + '?company_id=' + encodeURIComponent(companyId), {
          signal: activeController.signal,
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (token !== requestToken) return;
        renderHistory(data.history?.labels || [], data.history?.values || []);
        renderSegments(data.segments?.labels || [], data.segments?.values || []);
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        renderEmpty();
      } finally {
        window.clearTimeout(timeoutId);
        inFlight = false;
        hideLoading();
      }
    };

    companyIdInput.addEventListener('change', () => loadMetrics(companyIdInput.value));
    hideLoading();
    window.requestAnimationFrame(() => loadMetrics(companyIdInput.value));
    window.addEventListener('pageshow', () => {
      hideLoading();
      window.requestAnimationFrame(() => loadMetrics(companyIdInput.value));
    });
    window.addEventListener('pagehide', hideLoading);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) hideLoading();
    });
    window.addEventListener('focus', hideLoading);
    window.setInterval(() => {
      if (!inFlight) {
        hideLoading();
        return;
      }
      if (Date.now() - lastLoadStart > 7000) hideLoading();
    }, 2000);
  };

  const onLoad = () => initCharts();

  const observeContent = () => {
    const observer = new MutationObserver(() => {
      initCharts();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  };

  document.addEventListener('DOMContentLoaded', onLoad);
  window.addEventListener('page:load', onLoad);
  document.addEventListener('htmx:afterSwap', onLoad);
  document.addEventListener('htmx:beforeSwap', () => {
    const content = document.querySelector('.content[data-page="master-dashboard"]');
    if (content) {
      delete content.dataset.masterChartsInit;
    }
    if (activeController) {
      try {
        activeController.abort();
      } catch (err) {
        // ignore abort failures
      }
      activeController = null;
      inFlight = false;
    }
    clearLoaders();
  });
  observeContent();
  initCharts();
})();
