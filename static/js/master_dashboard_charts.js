(function () {
  if (!window.__masterDashboardChartsBound) {
    window.__masterDashboardChartsBound = true;
  }

  const colors = [
    '#1d4ed8',
    '#0ea5e9',
    '#22c55e',
    '#f59e0b',
    '#ef4444',
    '#8b5cf6',
    '#0f766e',
  ];

  let historyChart = null;
  let segmentChart = null;
  let activeController = null;
  let requestToken = 0;
  let inFlight = false;
  let lastLoadStart = 0;

  const initCharts = () => {
    const content = document.querySelector('.content[data-page="master-dashboard"]');
    if (!content) return;
    if (content.dataset.masterChartsInit === '1') return;
    content.dataset.masterChartsInit = '1';
    const metricsUrl = content.getAttribute('data-master-metrics-url') || '';
    const select = document.getElementById('master_company_id');
    if (!metricsUrl || !select) return;

    const historyCanvas = document.getElementById('master-eval-history');
    const segmentCanvas = document.getElementById('master-segment-pie');
    const segmentList = document.getElementById('master-segment-list');
    const historyLoading = document.querySelector('[data-master-loading="history"]');
    const segmentsLoading = document.querySelector('[data-master-loading="segments"]');
    if (!historyCanvas || !segmentCanvas || !segmentList) return;

    const hideLoading = () => {
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
              label: 'Avaliações',
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
        return;
      }
      if (typeof Chart === 'undefined') {
        if (attempt < 8) {
          setTimeout(() => loadMetrics(companyId, attempt + 1), 200);
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
      const timeoutId = setTimeout(() => {
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
        renderHistory(data.history.labels || [], data.history.values || []);
        renderSegments(data.segments.labels || [], data.segments.values || []);
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        renderEmpty();
      } finally {
        clearTimeout(timeoutId);
        inFlight = false;
        hideLoading();
      }
    };

    select.addEventListener('change', () => loadMetrics(select.value));
    hideLoading();
    requestAnimationFrame(() => loadMetrics(select.value));
    window.addEventListener('pageshow', () => {
      hideLoading();
      requestAnimationFrame(() => loadMetrics(select.value));
    });
    window.addEventListener('pagehide', hideLoading);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        hideLoading();
      }
    });
    window.addEventListener('focus', hideLoading);
    setInterval(() => {
      if (!inFlight) {
        hideLoading();
        return;
      }
      if (Date.now() - lastLoadStart > 7000) {
        hideLoading();
      }
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
  observeContent();
})();
