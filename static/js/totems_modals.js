(function () {
  const containerId = 'totems-table-container';
  const toastStackId = 'floating-toast-stack';
  const openButtons = document.querySelectorAll('[data-open-modal]');
  const editButtons = document.querySelectorAll('[data-open-edit-totem]');
  const closeButtons = document.querySelectorAll('[data-close-modal]');
  const editForm = document.querySelector('[data-edit-totem-form]');

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

  openButtons.forEach((button) => {
    button.addEventListener('click', () => {
      openModal(button.getAttribute('data-open-modal'));
    });
  });

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      if (!editForm) {
        return;
      }
      editForm.action = button.dataset.updateUrl || '';
      editForm.querySelector('#edit_totem_name').value = button.dataset.name || '';
      editForm.querySelector('#edit_totem_location').value = button.dataset.location || '';
      openModal('edit-totem-modal');
    });
  });

  closeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const modal = button.closest('.modal-backdrop');
      if (modal) {
        closeModal(modal);
      }
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach((modal) => {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal(modal);
      }
    });
  });

  consumeInlineNotices();
})();
