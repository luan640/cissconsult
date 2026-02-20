(function () {
  if (window.__companiesFiltersBound) return;
  window.__companiesFiltersBound = true;

  const debounce = (fn, wait) => {
    let timeoutId = null;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => fn(...args), wait);
    };
  };

  const runPageHooks = () => {
    const content = document.querySelector('.content[data-page="companies"]');
    if (!content) return;

    const picker = content.querySelector('[data-companies-name-picker]');
    if (!picker || picker.dataset.pickerInit === '1') return;

    const optionsUrl = content.getAttribute('data-company-options-url') || '';
    const hiddenInput = picker.querySelector('[data-companies-name-hidden]');
    const searchInput = picker.querySelector('[data-companies-name-search]');
    const menu = picker.querySelector('[data-companies-name-menu]');
    const optionsContainer = picker.querySelector('[data-companies-name-options]');
    const statusContainer = picker.querySelector('[data-companies-name-status]');
    const form = content.querySelector('form[data-ajax-table-form]');

    if (!optionsUrl || !hiddenInput || !searchInput || !menu || !optionsContainer || !statusContainer) return;

    picker.dataset.pickerInit = '1';

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

    const openMenu = () => {
      menu.hidden = false;
    };

    const closeMenu = () => {
      menu.hidden = true;
    };

    const selectCompany = (company) => {
      const name = company?.name || '';
      searchInput.value = name;
      hiddenInput.value = name;
      closeMenu();
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
        button.addEventListener('click', () => selectCompany(company));
        optionsContainer.appendChild(button);
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
      params.set('offset', String(state.offset));
      params.set('limit', String(state.limit));
      if (state.query) params.set('q', state.query);

      fetch(`${optionsUrl}?${params.toString()}`, {
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
          optionsContainer.innerHTML = '';
          setStatus('Nao foi possivel carregar empresas.');
        })
        .finally(() => {
          if (requestId === state.requestId) state.loading = false;
        });
    };

    const startSearch = debounce(() => {
      state.query = (searchInput.value || '').trim();
      hiddenInput.value = state.query;
      openMenu();
      loadCompanies(false);
    }, 300);

    searchInput.addEventListener('focus', () => {
      state.query = '';
      openMenu();
      loadCompanies(false);
    });

    searchInput.addEventListener('click', () => {
      state.query = '';
      openMenu();
      loadCompanies(false);
    });

    searchInput.addEventListener('input', startSearch);

    optionsContainer.addEventListener('scroll', () => {
      if (!state.hasMore || state.loading) return;
      const threshold = 18;
      const hitBottom =
        optionsContainer.scrollTop + optionsContainer.clientHeight >= optionsContainer.scrollHeight - threshold;
      if (!hitBottom) return;
      loadCompanies(true);
    });

    document.addEventListener('click', (event) => {
      if (picker.contains(event.target)) return;
      closeMenu();
    });

    if (form && form.dataset.companiesNameSubmitBound !== '1') {
      form.dataset.companiesNameSubmitBound = '1';
      form.addEventListener('submit', () => {
        hiddenInput.value = (searchInput.value || '').trim();
      });
    }
  };

  document.addEventListener('DOMContentLoaded', runPageHooks);
  window.addEventListener('page:load', runPageHooks);
  document.addEventListener('htmx:afterSwap', runPageHooks);
  runPageHooks();
})();
