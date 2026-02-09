(function () {
  if (window.__departmentsModalsBound) {
    return;
  }
  window.__departmentsModalsBound = true;
  const containerId = 'departments-table-container';
  const toastStackId = 'floating-toast-stack';
  const filterFormSelector = '[data-departments-filter-form]';
  const gheOptionsUrl = (() => {
    const container = document.querySelector('[data-ghe-options-url]');
    return container ? container.getAttribute('data-ghe-options-url') : '';
  })();

  const openModal = (name) => {
    const modal = document.querySelector(`[data-modal="${name}"]`);
    if (!modal) return;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('modal-open');
  };

  const closeModal = (modal) => {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-backdrop.is-open')) {
      document.documentElement.classList.remove('modal-open');
    }
  };

  const getToastStack = () => {
    let stack = document.getElementById(toastStackId);
    if (!stack) {
      stack = document.createElement('div');
      stack.id = toastStackId;
      stack.className = 'floating-toast-stack';
      document.body.appendChild(stack);
    }
    return stack;
  };

  const showToast = (message, tone = 'success') => {
    const stack = getToastStack();
    const toast = document.createElement('div');
    toast.className = `floating-toast floating-toast--${tone}`;
    toast.textContent = message;
    stack.appendChild(toast);
    window.setTimeout(() => toast.classList.add('is-visible'), 10);
    window.setTimeout(() => {
      toast.classList.remove('is-visible');
      window.setTimeout(() => toast.remove(), 220);
    }, 2500);
  };

  const consumeInlineNotices = () => {
    const container = document.getElementById(containerId);
    if (!container) return;
    const notices = container.querySelectorAll('.notice');
    if (!notices.length) return;
    notices.forEach((notice) => {
      const tone = notice.classList.contains('notice--error')
        ? 'error'
        : notice.classList.contains('notice--info')
          ? 'info'
          : 'success';
      showToast(notice.textContent.trim(), tone);
    });
    const stackGap = container.querySelector('.stack-gap');
    if (stackGap) {
      stackGap.remove();
    }
  };

  const replaceTable = (html) => {
    const container = document.getElementById(containerId);
    if (container) {
      container.outerHTML = html;
    }
    consumeInlineNotices();
  };

  const getActiveFilterQuery = () => {
    const params = new URLSearchParams(window.location.search);
    params.delete('partial');
    return params.toString();
  };

  const submitAjaxForm = async (form) => {
    const updateUrl = new URL(form.action, window.location.origin);
    const filterQuery = getActiveFilterQuery();
    if (filterQuery) {
      updateUrl.search = filterQuery;
    }
    const response = await fetch(updateUrl.toString(), {
      method: form.method || 'POST',
      body: new FormData(form),
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao atualizar setores.');
    }
    replaceTable(await response.text());
  };

  const setButtonLoading = (button) => {
    if (!button || button.disabled) return null;
    const original = button.textContent || '';
    button.textContent = button.getAttribute('data-loading-text') || 'Salvando...';
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    return () => {
      button.textContent = original;
      button.disabled = false;
      button.removeAttribute('aria-busy');
    };
  };

  const buildFilterFetchUrl = (form) => {
    const formData = new FormData(form);
    const params = new URLSearchParams();
    formData.forEach((value, key) => {
      const trimmed = typeof value === 'string' ? value.trim() : value;
      if (trimmed) {
        params.append(key, trimmed);
      }
    });
    params.set('partial', '1');
    return `${form.action}?${params.toString()}`;
  };

  const syncBrowserUrlFromFilterForm = (form) => {
    const formData = new FormData(form);
    const params = new URLSearchParams();
    formData.forEach((value, key) => {
      const trimmed = typeof value === 'string' ? value.trim() : value;
      if (trimmed) {
        params.append(key, trimmed);
      }
    });
    const nextUrl = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    window.history.replaceState({}, '', nextUrl);
  };

  const applyFilters = async (form) => {
    const response = await fetch(buildFilterFetchUrl(form), {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao filtrar setores.');
    }
    replaceTable(await response.text());
    syncBrowserUrlFromFilterForm(form);
  };

  const refreshGheOptions = async (selectedId = '') => {
    if (!gheOptionsUrl) return;
    const response = await fetch(gheOptionsUrl, {
      cache: 'no-store',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) return;
    const payload = await response.json();
    const ghes = Array.isArray(payload.ghes) ? payload.ghes : [];
    const buildOptions = (activeSelected) => {
      if (!ghes.length) {
        return '<option value="">Nenhum GHE ativo</option>';
      }
      return ghes
        .map((ghe) => {
          const value = String(ghe.id);
          const isSelected = activeSelected && value === String(activeSelected);
          return `<option value="${value}"${isSelected ? ' selected' : ''}>${ghe.name}</option>`;
        })
        .join('');
    };
    const createSelect = document.querySelector('#create_department_ghe');
    if (createSelect) {
      createSelect.innerHTML = buildOptions('');
    }
    const editSelect = document.querySelector('#edit_department_ghe');
    if (editSelect) {
      editSelect.innerHTML = buildOptions(selectedId);
    }
  };

  const setGheLoading = (select) => {
    if (!select) return;
    select.innerHTML = '<option value="">Carregando...</option>';
  };

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      const modalName = openButton.getAttribute('data-open-modal');
      if (modalName === 'create-department-modal') {
        const createSelect = document.querySelector('#create_department_ghe');
        setGheLoading(createSelect);
        refreshGheOptions();
      }
      openModal(modalName);
      return;
    }

    const editButton = event.target.closest('[data-open-edit-department]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-department-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_department_name').value = editButton.dataset.name || '';
      const selectedGheId = editButton.dataset.gheId || '';
      const gheSelect = editForm.querySelector('#edit_department_ghe');
      setGheLoading(gheSelect);
      refreshGheOptions(selectedGheId);
      if (gheSelect) {
        gheSelect.value = selectedGheId;
      }
      editForm.querySelector('[data-edit-department-active]').checked = editButton.dataset.isActive === '1';
      openModal('edit-department-modal');
      return;
    }

    const closeButton = event.target.closest('[data-close-modal]');
    if (closeButton) {
      const modal = closeButton.closest('.modal-backdrop');
      if (modal) closeModal(modal);
      return;
    }

    const backdrop = event.target.closest('.modal-backdrop');
    if (backdrop && event.target === backdrop) {
      closeModal(backdrop);
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (form.matches(filterFormSelector)) {
      if (form.hasAttribute('data-ajax-table-form')) {
        return;
      }
      event.preventDefault();
      try {
        await applyFilters(form);
      } catch (error) {
        window.location.assign(form.action);
      }
      return;
    }
    const shouldHandle =
      form.matches('[data-department-create-form]') ||
      form.matches('[data-edit-department-form]') ||
      form.matches('[data-department-toggle-form]');
    if (!shouldHandle) return;
    event.preventDefault();
    const restoreButton = setButtonLoading(event.submitter);
    try {
      await submitAjaxForm(form);
      document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
    } catch (error) {
      form.submit();
      return;
    } finally {
      if (restoreButton) restoreButton();
    }
  });

  document.addEventListener('click', async (event) => {
    const clearButton = event.target.closest('[data-departments-clear-filters]');
    if (!clearButton) return;
    event.preventDefault();
    const form = document.querySelector(filterFormSelector);
    if (!form) {
      window.location.assign(clearButton.href);
      return;
    }
    form.reset();
    try {
      await applyFilters(form);
    } catch (error) {
      window.location.assign(clearButton.href);
    }
  });

  const runPageHooks = () => {
    consumeInlineNotices();
  };

  window.addEventListener('page:load', runPageHooks);
  runPageHooks();
})();
