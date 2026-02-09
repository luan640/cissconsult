(function () {
  if (window.__companiesModalsBound) {
    return;
  }
  window.__companiesModalsBound = true;
  const containerId = 'companies-table-container';
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

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      openModal(openButton.getAttribute('data-open-modal'));
      return;
    }

    const editButton = event.target.closest('[data-open-edit-company]');
    if (editButton) {
      const editForm = document.querySelector('[data-edit-company-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_company_name').value = editButton.dataset.name || '';
      editForm.querySelector('#edit_company_legal_name').value = editButton.dataset.legalName || '';
      editForm.querySelector('#edit_company_legal_representative').value = editButton.dataset.legalRepresentativeName || '';
      editForm.querySelector('#edit_company_cnpj').value = editButton.dataset.cnpj || '';
      editForm.querySelector('#edit_company_employee_count').value = editButton.dataset.employeeCount || '';
      editForm.querySelector('#edit_company_max_users').value = editButton.dataset.maxUsers || '';
      editForm.querySelector('#edit_company_max_totems').value = editButton.dataset.maxTotems || '';
      editForm.querySelector('#edit_company_address_street').value = editButton.dataset.addressStreet || '';
      editForm.querySelector('#edit_company_address_number').value = editButton.dataset.addressNumber || '';
      editForm.querySelector('#edit_company_address_complement').value = editButton.dataset.addressComplement || '';
      editForm.querySelector('#edit_company_address_neighborhood').value = editButton.dataset.addressNeighborhood || '';
      editForm.querySelector('#edit_company_address_city').value = editButton.dataset.addressCity || '';
      editForm.querySelector('#edit_company_address_state').value = editButton.dataset.addressState || '';
      editForm.querySelector('#edit_company_address_zipcode').value = editButton.dataset.addressZipcode || '';
      const activeField = editForm.querySelector('[data-edit-company-active]');
      if (activeField) {
        activeField.checked = editButton.dataset.isActive === '1';
      }
      openModal('edit-company-modal');
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

  const runPageHooks = () => {
    consumeInlineNotices();
  };

  window.addEventListener('page:load', runPageHooks);
  runPageHooks();
})();
