(function () {
  if (window.PlatformDialog) {
    return;
  }

  const createDialog = () => {
    const backdrop = document.createElement('div');
    backdrop.className = 'platform-dialog-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    backdrop.innerHTML = [
      '<div class="platform-dialog-card" role="dialog" aria-modal="true" aria-live="assertive">',
      '  <h2 class="platform-dialog-title"></h2>',
      '  <p class="platform-dialog-message"></p>',
      '  <div class="platform-dialog-actions">',
      '    <button type="button" class="btn btn--light" data-dialog-cancel>Cancelar</button>',
      '    <button type="button" class="btn btn--primary" data-dialog-confirm>Confirmar</button>',
      '  </div>',
      '</div>',
    ].join('');
    document.body.appendChild(backdrop);
    return {
      backdrop,
      title: backdrop.querySelector('.platform-dialog-title'),
      message: backdrop.querySelector('.platform-dialog-message'),
      cancel: backdrop.querySelector('[data-dialog-cancel]'),
      confirm: backdrop.querySelector('[data-dialog-confirm]'),
    };
  };

  let nodes = null;
  let resolver = null;

  const ensureNodes = () => {
    if (!nodes) {
      nodes = createDialog();
    }
    return nodes;
  };

  const closeDialog = (result) => {
    const current = ensureNodes();
    current.backdrop.classList.remove('is-open');
    current.backdrop.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('modal-open');
    if (resolver) {
      const fn = resolver;
      resolver = null;
      fn(result);
    }
  };

  const openDialog = (options) => {
    const current = ensureNodes();
    const title = (options && options.title) || 'Confirmar';
    const message = (options && options.message) || '';
    const confirmLabel = (options && options.confirmText) || 'Confirmar';
    const cancelLabel = (options && options.cancelText) || 'Cancelar';
    const showCancel = !!(options && options.showCancel);

    current.title.textContent = title;
    current.message.textContent = message;
    current.confirm.textContent = confirmLabel;
    current.cancel.textContent = cancelLabel;
    current.cancel.style.display = showCancel ? '' : 'none';

    current.backdrop.classList.add('is-open');
    current.backdrop.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('modal-open');
    current.confirm.focus();

    return new Promise((resolve) => {
      resolver = resolve;
    });
  };

  const onKeyDown = (event) => {
    const current = ensureNodes();
    if (!current.backdrop.classList.contains('is-open')) {
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      closeDialog(false);
    }
  };

  const onBackdropClick = (event) => {
    const current = ensureNodes();
    if (!current.backdrop.classList.contains('is-open')) {
      return;
    }
    if (event.target === current.backdrop) {
      closeDialog(false);
    }
  };

  const bindEvents = () => {
    const current = ensureNodes();
    current.cancel.addEventListener('click', () => closeDialog(false));
    current.confirm.addEventListener('click', () => closeDialog(true));
    current.backdrop.addEventListener('click', onBackdropClick);
    document.addEventListener('keydown', onKeyDown);
  };

  window.PlatformDialog = {
    confirm(message, options) {
      return openDialog({
        title: (options && options.title) || 'Confirmar ação',
        message: message || '',
        confirmText: (options && options.confirmText) || 'Confirmar',
        cancelText: (options && options.cancelText) || 'Cancelar',
        showCancel: true,
      });
    },
    alert(message, options) {
      return openDialog({
        title: (options && options.title) || 'Aviso',
        message: message || '',
        confirmText: (options && options.confirmText) || 'OK',
        showCancel: false,
      });
    },
  };

  bindEvents();

  document.addEventListener(
    'submit',
    async (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) {
        return;
      }
      const message = form.getAttribute('data-platform-confirm');
      if (!message) {
        return;
      }

      if (form.dataset.platformConfirmBypass === '1') {
        form.dataset.platformConfirmBypass = '';
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const confirmed = await window.PlatformDialog.confirm(message, {
        title: form.getAttribute('data-platform-confirm-title') || 'Confirmar ação',
      });
      if (!confirmed) {
        return;
      }

      form.dataset.platformConfirmBypass = '1';
      if (typeof form.requestSubmit === 'function') {
        if (event.submitter) {
          form.requestSubmit(event.submitter);
        } else {
          form.requestSubmit();
        }
        return;
      }
      form.submit();
    },
    true
  );
})();
