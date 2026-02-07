(function () {
  const containerId = 'complaints-table-container';
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

  const submitAjaxForm = async (form) => {
    const response = await fetch(form.action, {
      method: form.method || 'POST',
      body: new FormData(form),
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao atualizar denúncia.');
    }
    replaceTable(await response.text());
  };

  const loadHistory = async (url) => {
    const container = document.getElementById('complaint-history-container');
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

  document.addEventListener('click', (event) => {
    const historyButton = event.target.closest('[data-open-complaint-history]');
    if (historyButton) {
      const historyUrl = historyButton.dataset.historyUrl || '';
      if (!historyUrl) return;
      loadHistory(historyUrl)
        .then(() => openModal('complaint-history-modal'))
        .catch(() => showToast('Falha ao carregar historico da denuncia.', 'error'));
      return;
    }

    const editButton = event.target.closest('[data-open-edit-complaint]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-complaint-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_complaint_status').value = editButton.dataset.status || 'RECEIVED';
      editForm.querySelector('#edit_complaint_action_note').value = '';
      openModal('edit-complaint-modal');
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
    if (!form.matches('[data-edit-complaint-form]')) return;
    event.preventDefault();
    try {
      await submitAjaxForm(form);
      document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
    } catch (error) {
      form.submit();
    }
  });

  consumeInlineNotices();
})();
