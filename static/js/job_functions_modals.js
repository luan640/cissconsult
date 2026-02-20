(function () {
  if (window.__jobFunctionsModalsBound) {
    return;
  }
  window.__jobFunctionsModalsBound = true;
  const containerId = 'job-functions-table-container';
  const toastStackId = 'floating-toast-stack';

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
      throw new Error('Falha ao atualizar funções.');
    }
    return await response.text();
  };

  const setCheckboxGroupValues = (container, values) => {
    if (!container) return;
    const valueSet = new Set(values);
    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach((checkbox) => {
      checkbox.checked = valueSet.has(checkbox.value);
    });
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
      throw new Error('Falha ao filtrar funções.');
    }
    replaceTable(await response.text());
    syncBrowserUrlFromFilterForm(form);
  };

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      openModal(openButton.getAttribute('data-open-modal'));
      return;
    }

    const editButton = event.target.closest('[data-open-edit-job-function]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-job-function-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_job_function_name').value = editButton.dataset.name || '';
      const gheValues = (editButton.dataset.ghes || '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      const departmentValues = (editButton.dataset.departments || '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      setCheckboxGroupValues(editForm.querySelector('#edit_job_function_ghes'), gheValues);
      setCheckboxGroupValues(editForm.querySelector('#edit_job_function_departments'), departmentValues);
      openModal('edit-job-function-modal');
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
    const shouldHandle =
      form.matches('[data-job-function-create-form]') ||
      form.matches('[data-edit-job-function-form]') ||
      form.matches('[data-job-function-toggle-form]');
    if (!shouldHandle) return;
    if (event.defaultPrevented) return;
    event.preventDefault();
    const restoreButton = setButtonLoading(event.submitter);
    try {
      const html = await submitAjaxForm(form);
      replaceTable(html);
      if (!html.includes('notice--error')) {
        document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
      }
    } catch (error) {
      form.submit();
      return;
    } finally {
      if (restoreButton) restoreButton();
    }
  });

  document.addEventListener('click', async (event) => {
    const clearButton = event.target.closest('[data-job-functions-clear-filters]');
    if (!clearButton) return;
    event.preventDefault();
    const form = document.querySelector('[data-job-functions-filter-form]');
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
