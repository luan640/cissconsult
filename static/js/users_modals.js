(function () {
  const openButtons = document.querySelectorAll('[data-open-modal]');
  const editButtons = document.querySelectorAll('[data-open-edit]');
  const closeButtons = document.querySelectorAll('[data-close-modal]');
  const editModal = document.querySelector('[data-modal="edit-user-modal"]');
  const editForm = document.querySelector('[data-edit-form]');

  const openModal = (modalName) => {
    const modal = document.querySelector(`[data-modal="${modalName}"]`);
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
      const modalName = button.getAttribute('data-open-modal');
      openModal(modalName);
    });
  });

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      if (!editModal || !editForm) {
        return;
      }

      editForm.action = button.dataset.updateUrl || '';
      editForm.querySelector('#edit_username').value = button.dataset.username || '';
      editForm.querySelector('#edit_first_name').value = button.dataset.firstName || '';
      editForm.querySelector('#edit_last_name').value = button.dataset.lastName || '';
      editForm.querySelector('#edit_email').value = button.dataset.email || '';
      editForm.querySelector('#edit_role').value = button.dataset.role || 'COLABORADOR';
      editForm.querySelector('#edit_password').value = '';

      const activeCheckbox = editForm.querySelector('[data-edit-active]');
      activeCheckbox.checked = button.dataset.isActive === '1';
      openModal('edit-user-modal');
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
})();
