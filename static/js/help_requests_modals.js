(function () {
  const containerId = 'help-requests-table-container';
  const toastStackId = 'floating-toast-stack';
  const filterFormSelector = '[data-help-requests-filter-form]';

  const openModal = (name) => {
    const modal = document.querySelector(`[data-modal="${name}"]`);
    if (!modal) {
      return;
    }
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
      throw new Error('Falha ao atualizar pedido de ajuda.');
    }
    replaceTable(await response.text());
  };

  const loadHistory = async (url) => {
    const container = document.getElementById('help-request-history-container');
    if (!container) return;
    container.innerHTML = '<p style="margin:0; color:#475569;">Carregando historico...</p>';
    const response = await fetch(url, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao carregar historico.');
    }
    container.innerHTML = await response.text();
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
      throw new Error('Falha ao filtrar pedidos de ajuda.');
    }
    replaceTable(await response.text());
    syncBrowserUrlFromFilterForm(form);
  };

  document.addEventListener('click', (event) => {
    const historyButton = event.target.closest('[data-open-help-request-history]');
    if (historyButton) {
      const historyUrl = historyButton.dataset.historyUrl || '';
      if (!historyUrl) return;
      loadHistory(historyUrl)
        .then(() => openModal('help-request-history-modal'))
        .catch(() => showToast('Falha ao carregar historico do pedido.', 'error'));
      return;
    }

    const editButton = event.target.closest('[data-open-edit-help-request]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-help-request-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_help_request_status').value = editButton.dataset.status || 'OPEN';
      editForm.querySelector('#edit_help_request_notes').value = '';
      openModal('edit-help-request-modal');
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
      event.preventDefault();
      try {
        await applyFilters(form);
      } catch (error) {
        window.location.assign(form.action);
      }
      return;
    }
    if (!form.matches('[data-edit-help-request-form]')) return;
    event.preventDefault();
    try {
      await submitAjaxForm(form);
      document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
    } catch (error) {
      form.submit();
    }
  });

  document.addEventListener('click', async (event) => {
    const clearButton = event.target.closest('[data-help-requests-clear-filters]');
    if (!clearButton) return;
    event.preventDefault();
    const form = document.querySelector(filterFormSelector);
    if (!form) {
      window.location.assign(clearButton.href);
      return;
    }
    form.querySelectorAll('select').forEach((select) => {
      select.value = '';
    });
    try {
      await applyFilters(form);
    } catch (error) {
      window.location.assign(clearButton.href);
    }
  });

  consumeInlineNotices();
})();
