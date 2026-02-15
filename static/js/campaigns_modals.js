(function () {
  const confirmDialog = (message) => {
    if (window.PlatformDialog && typeof window.PlatformDialog.confirm === 'function') {
      return window.PlatformDialog.confirm(message);
    }
    return Promise.resolve(false);
  };

  const containerId = 'campaigns-table-container';
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

  const replaceTable = (html) => {
    const container = document.getElementById(containerId);
    if (container) {
      container.outerHTML = html;
    }
    consumeInlineNotices();
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

  const submitAjaxForm = async (form) => {
    const response = await fetch(form.action, {
      method: form.method || 'POST',
      body: new FormData(form),
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao atualizar campanhas.');
    }
    replaceTable(await response.text());
  };

  const resetForm = (form) => {
    if (!form) return;
    form.reset();
    const selectEls = form.querySelectorAll('select');
    selectEls.forEach((select) => {
      if (select.options.length) {
        select.selectedIndex = 0;
      }
    });
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

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      openModal(openButton.getAttribute('data-open-modal'));
      return;
    }

    const qrButton = event.target.closest('[data-open-qr]');
    if (qrButton) {
      const modal = document.querySelector('[data-modal="qr-preview-modal"]');
      if (!modal) return;
      const img = modal.querySelector('[data-qr-image]');
      const loading = modal.querySelector('[data-qr-loading]');
      const download = modal.querySelector('[data-qr-download]');
      const url = qrButton.getAttribute('data-qr-url') || '';
      if (!img || !loading || !download) return;

      img.style.display = 'none';
      img.removeAttribute('src');
      loading.style.display = 'block';
      download.setAttribute('href', url || '#');

      if (url) {
        img.onload = () => {
          loading.style.display = 'none';
          img.style.display = 'block';
        };
        img.onerror = () => {
          loading.textContent = 'Nao foi possivel carregar o QR Code.';
        };
        img.src = url;
      } else {
        loading.textContent = 'QR Code indisponivel.';
      }

      openModal('qr-preview-modal');
      return;
    }

    const editButton = event.target.closest('[data-open-edit-campaign]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-campaign-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_campaign_title').value = editButton.dataset.title || '';
      editForm.querySelector('#edit_campaign_company').value = editButton.dataset.companyId || '';
      editForm.querySelector('#edit_campaign_start').value = editButton.dataset.startDate || '';
      editForm.querySelector('#edit_campaign_end').value = editButton.dataset.endDate || '';
      editForm.querySelector('#edit_campaign_status').value = editButton.dataset.status || '';
      editForm.dataset.responseCount = editButton.dataset.responseCount || '0';
      editForm.dataset.employeeCount = editButton.dataset.employeeCount || '0';
      const forceField = editForm.querySelector('input[name="force_finish"]');
      if (forceField) {
        forceField.value = '';
      }
      openModal('edit-campaign-modal');
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
      form.matches('[data-campaign-create-form]') ||
      form.matches('[data-edit-campaign-form]') ||
      form.matches('[data-campaign-delete-form]');
    if (!shouldHandle) return;
    if (event.defaultPrevented) return;

    event.preventDefault();

    if (form.matches('[data-edit-campaign-form]')) {
      const statusField = form.querySelector('#edit_campaign_status');
      const statusValue = (statusField?.value || '').toUpperCase();
      const responsesCount = Number.parseInt(form.dataset.responseCount || '0', 10) || 0;
      const employeeCount = Number.parseInt(form.dataset.employeeCount || '0', 10) || 0;
      const hasPendingResponses = responsesCount !== employeeCount;
      const forceField = form.querySelector('input[name="force_finish"]');

      if (forceField) {
        forceField.value = '';
      }

      if (statusValue === 'FINISHED' && hasPendingResponses) {
        const confirmed = await confirmDialog(
          'Ainda faltam funcionario responder o questionario, deseja encerrar mesmo assim?'
        );
        if (!confirmed) {
          return;
        }
        if (forceField) {
          forceField.value = '1';
        }
      }
    }
    const restoreButton = setButtonLoading(event.submitter);
    try {
      await submitAjaxForm(form);
      document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
      if (form.matches('[data-campaign-create-form]')) {
        resetForm(form);
      }
    } catch (error) {
      form.submit();
      return;
    } finally {
      if (restoreButton) restoreButton();
    }
  });

  consumeInlineNotices();
})();
