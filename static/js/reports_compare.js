(function () {
  if (window.__reportsCompareBound) return;
  window.__reportsCompareBound = true;

  const debounce = (fn, wait) => {
    let timeoutId = null;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => fn(...args), wait);
    };
  };

  const runPageHooks = () => {
    const content = document.querySelector('.content[data-page="reports-compare"]');
    if (!content) return;

    const companySelect = content.querySelector('[data-company-select]');
    const reportSelects = Array.from(content.querySelectorAll('[data-report-select]'));
    const companyOptionsUrl = content.getAttribute('data-company-options-url') || '';
    const companySearch = content.querySelector('[data-master-company-search]');
    const companyPicker = content.querySelector('[data-master-company-picker]');
    const companyMenu = content.querySelector('[data-master-company-menu]');
    const companyOptionsContainer = content.querySelector('[data-master-company-options]');
    const companyStatus = content.querySelector('[data-master-company-status]');
    const form = content.querySelector('.compare-form__grid');

    const setReportSelectsDisabled = (disabled) => {
      reportSelects.forEach((select) => {
        select.disabled = disabled;
      });
    };

    const clearReportOptions = (message) => {
      reportSelects.forEach((select) => {
        select.innerHTML = `<option value="">${message || 'Selecione'}</option>`;
      });
    };

    const hasSelectedCompany = companySelect ? Boolean(companySelect.value) : true;
    setReportSelectsDisabled(!hasSelectedCompany);

    const loadCampaigns = (companyId) => {
      if (!companyId) {
        clearReportOptions('Selecione');
        setReportSelectsDisabled(true);
        return;
      }

      clearReportOptions('Carregando...');
      setReportSelectsDisabled(true);

      fetch(`${window.location.pathname}?load_campaigns=1&company_id=${encodeURIComponent(companyId)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((response) => {
          if (!response.ok) throw new Error('Falha ao carregar campanhas');
          return response.json();
        })
        .then((data) => {
          const campaigns = Array.isArray(data?.campaigns) ? data.campaigns : [];
          reportSelects.forEach((select) => {
            select.innerHTML = '<option value="">Selecione</option>';
            campaigns.forEach((campaign) => {
              const option = document.createElement('option');
              option.value = String(campaign.id);
              option.textContent = campaign.label;
              select.appendChild(option);
            });
            select.disabled = campaigns.length === 0;
          });
        })
        .catch(() => {
          clearReportOptions('Erro ao carregar');
          setReportSelectsDisabled(true);
        });
    };

    if (companySelect && companySelect.dataset.compareBound !== '1') {
      companySelect.dataset.compareBound = '1';
      companySelect.addEventListener('change', () => {
        loadCampaigns(companySelect.value);
      });
    }

    if (
      companyPicker &&
      companySearch &&
      companySelect &&
      companyMenu &&
      companyOptionsContainer &&
      companyStatus &&
      companyOptionsUrl &&
      companyPicker.dataset.pickerInit !== '1'
    ) {
      companyPicker.dataset.pickerInit = '1';

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
        companyStatus.textContent = text || '';
      };

      const openMenu = () => {
        companyMenu.hidden = false;
      };

      const closeMenu = () => {
        companyMenu.hidden = true;
      };

      const selectCompany = (company) => {
        companySelect.value = String(company.id);
        companySearch.value = company.name || '';
        companySearch.setCustomValidity('');
        closeMenu();
        companySelect.dispatchEvent(new Event('change', { bubbles: true }));
      };

      const renderOptions = () => {
        companyOptionsContainer.innerHTML = '';
        if (!state.items.length) {
          setStatus('Nenhuma empresa encontrada.');
          return;
        }
        state.items.forEach((company) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'master-company-picker__option';
          button.textContent = company.name || '';
          button.addEventListener('click', () => selectCompany(company));
          companyOptionsContainer.appendChild(button);
        });
        setStatus(state.hasMore ? 'Role para carregar mais.' : '');
      };

      const loadCompanies = (append = false) => {
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

        fetch(`${companyOptionsUrl}?${params.toString()}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then((response) => {
            if (!response.ok) throw new Error('Falha ao carregar empresas.');
            return response.json();
          })
          .then((data) => {
            if (requestId !== state.requestId) return;
            const companies = Array.isArray(data?.companies) ? data.companies : [];
            state.hasMore = Boolean(data?.has_more);
            state.items = append ? state.items.concat(companies) : companies;
            state.offset = state.items.length;
            renderOptions();
          })
          .catch(() => {
            if (requestId !== state.requestId) return;
            state.items = [];
            state.hasMore = false;
            companyOptionsContainer.innerHTML = '';
            setStatus('Nao foi possivel carregar empresas.');
          })
          .finally(() => {
            if (requestId === state.requestId) state.loading = false;
          });
      };

      const startSearch = debounce(() => {
        state.query = (companySearch.value || '').trim();
        companySelect.value = '';
        companySearch.setCustomValidity('Selecione uma empresa da lista.');
        clearReportOptions('Selecione');
        setReportSelectsDisabled(true);
        openMenu();
        loadCompanies(false);
      }, 300);

      companySearch.addEventListener('focus', () => {
        state.query = '';
        openMenu();
        loadCompanies(false);
      });

      companySearch.addEventListener('click', () => {
        state.query = '';
        openMenu();
        loadCompanies(false);
      });

      companySearch.addEventListener('input', startSearch);

      companyOptionsContainer.addEventListener('scroll', () => {
        if (!state.hasMore || state.loading) return;
        const threshold = 18;
        const hitBottom =
          companyOptionsContainer.scrollTop + companyOptionsContainer.clientHeight >=
          companyOptionsContainer.scrollHeight - threshold;
        if (!hitBottom) return;
        loadCompanies(true);
      });

      document.addEventListener('click', (event) => {
        if (companyPicker.contains(event.target)) return;
        closeMenu();
      });
    }

    if (form && form.dataset.compareSubmitBound !== '1') {
      form.dataset.compareSubmitBound = '1';
      form.addEventListener('submit', (event) => {
        if (companySearch && companySelect && !companySelect.value) {
          companySearch.setCustomValidity('Selecione uma empresa da lista.');
          companySearch.reportValidity();
          event.preventDefault();
          return;
        }
        const submitBtn = form.querySelector('[data-compare-submit]');
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Carregando...';
        }
      });
    }
  };

  document.addEventListener('DOMContentLoaded', runPageHooks);
  window.addEventListener('page:load', runPageHooks);
  document.addEventListener('htmx:afterSwap', runPageHooks);
  runPageHooks();
})();
