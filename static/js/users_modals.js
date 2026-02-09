(function () {
  if (window.__usersModalsBound) {
    return;
  }
  window.__usersModalsBound = true;

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

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      const modalName = openButton.getAttribute('data-open-modal');
      openModal(modalName);
      return;
    }

    const editButton = event.target.closest('[data-open-edit]');
    if (editButton) {
      const editModal = document.querySelector('[data-modal="edit-user-modal"]');
      const editForm = document.querySelector('[data-edit-form]');
      if (!editModal || !editForm) {
        return;
      }

      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_username').value = editButton.dataset.username || '';
      editForm.querySelector('#edit_first_name').value = editButton.dataset.firstName || '';
      editForm.querySelector('#edit_last_name').value = editButton.dataset.lastName || '';
      editForm.querySelector('#edit_email').value = editButton.dataset.email || '';
      editForm.querySelector('#edit_role').value = editButton.dataset.role || 'COLABORADOR';
      editForm.querySelector('#edit_password').value = '';

      const activeCheckbox = editForm.querySelector('[data-edit-active]');
      activeCheckbox.checked = editButton.dataset.isActive === '1';
      openModal('edit-user-modal');
      return;
    }

    const closeButton = event.target.closest('[data-close-modal]');
    if (closeButton) {
      const modal = closeButton.closest('.modal-backdrop');
      if (modal) {
        closeModal(modal);
      }
      return;
    }

    const backdrop = event.target.closest('.modal-backdrop');
    if (backdrop && event.target === backdrop) {
      closeModal(backdrop);
    }
  });
})();
