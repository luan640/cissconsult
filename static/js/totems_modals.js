(function () {
  if (window.__totemsModalsBound) {
    return;
  }
  window.__totemsModalsBound = true;
  const containerId = 'totems-table-container';
  const toastStackId = 'floating-toast-stack';

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

  const setLoadingState = (form, isLoading) => {
    if (!form) return;
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    if (isLoading) {
      const loadingText = button.getAttribute('data-loading-text') || 'Salvando...';
      if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent || '';
      }
      button.textContent = loadingText;
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      return;
    }
    if (button.dataset.originalText) {
      button.textContent = button.dataset.originalText;
    }
    button.disabled = false;
    button.removeAttribute('aria-busy');
  };

  const restoreSubmitButton = (form) => {
    setLoadingState(form, false);
  };

  const replaceTable = (html) => {
    const container = document.getElementById(containerId);
    if (container) {
      container.outerHTML = html;
    }
    consumeInlineNotices();
  };

  const submitAjaxForm = async (form) => {
    const response = await fetch(form.action, {
      method: form.method || 'POST',
      body: new FormData(form),
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao atualizar totens.');
    }
    replaceTable(await response.text());
  };

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      openModal(openButton.getAttribute('data-open-modal'));
      return;
    }

    const editButton = event.target.closest('[data-open-edit-totem]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-totem-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_totem_name').value = editButton.dataset.name || '';
      editForm.querySelector('#edit_totem_location').value = editButton.dataset.location || '';
      restoreSubmitButton(editForm);
      openModal('edit-totem-modal');
      return;
    }

    const closeButton = event.target.closest('[data-close-modal]');
    if (closeButton) {
      const modal = closeButton.closest('.modal-backdrop');
      if (modal) {
        const form = modal.querySelector('form');
        restoreSubmitButton(form);
        closeModal(modal);
      }
      return;
    }

    const backdrop = event.target.closest('.modal-backdrop');
    if (backdrop && event.target === backdrop) {
      const form = backdrop.querySelector('form');
      restoreSubmitButton(form);
      closeModal(backdrop);
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    const shouldHandle =
      form.matches('[data-totem-create-form]') ||
      form.matches('[data-edit-totem-form]') ||
      form.matches('[data-totem-delete-form]');
    if (!shouldHandle) return;
    if (event.defaultPrevented) return;

    event.preventDefault();
    setLoadingState(form, true);
    try {
      await submitAjaxForm(form);
      document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
    } catch (error) {
      form.submit();
    } finally {
      restoreSubmitButton(form);
    }
  });

  const runPageHooks = () => {
    consumeInlineNotices();
  };

  window.addEventListener('page:load', runPageHooks);
  runPageHooks();
})();
