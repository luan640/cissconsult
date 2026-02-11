(function () {
  if (window.__companiesModalsBound) {
    return;
  }
  window.__companiesModalsBound = true;
  const containerId = 'companies-table-container';
  const toastStackId = 'floating-toast-stack';
  const createCompanyModalName = 'create-company-modal';

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

  const consumeInlineNoticesFromDoc = (doc) => {
    if (!doc) return;
    const notices = doc.querySelectorAll('.notice');
    if (!notices.length) return;
    notices.forEach((notice) => {
      const tone = notice.classList.contains('notice--error')
        ? 'error'
        : notice.classList.contains('notice--info')
          ? 'info'
          : 'success';
      showToast(notice.textContent.trim(), tone);
    });
  };

  const openModal = (name) => {
    const modal = document.querySelector(`[data-modal="${name}"]`);
    if (!modal) {
      return;
    }
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('modal-open');
    if (name === createCompanyModalName) {
      resetCompanyWizard(modal);
    }
  };

  const closeModal = (modal) => {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-backdrop.is-open')) {
      document.documentElement.classList.remove('modal-open');
    }
  };

  const getCompanyWizard = (root) => (root ? root.querySelector('[data-company-wizard]') : null);

  const updateDocumentLabel = (wizard, value) => {
    if (!wizard) return;
    const label = wizard.querySelector('[data-document-label]');
    if (!label) return;
    label.textContent = value === 'cpf' ? 'CPF' : 'CNPJ';
  };

  const updateUnitNameVisibility = (wizard, value) => {
    if (!wizard) return;
    const unitField = wizard.querySelector('[data-unit-name]');
    if (!unitField) return;
    const shouldShow = value && value !== 'matriz';
    unitField.classList.toggle('is-visible', shouldShow);
    if (!shouldShow) {
      const input = unitField.querySelector('input');
      if (input) input.value = '';
    }
  };

  const setWizardStep = (wizard, step) => {
    if (!wizard) return;
    const nextStep = Math.max(1, Math.min(step, 3));
    wizard.dataset.step = String(nextStep);
    const panels = wizard.querySelectorAll('.company-wizard__panel');
    panels.forEach((panel) => {
      panel.classList.toggle('is-active', panel.dataset.step === String(nextStep));
    });
    const indicators = wizard.querySelectorAll('[data-step-indicator]');
    indicators.forEach((indicator) => {
      const index = Number(indicator.dataset.stepIndicator || 0);
      indicator.classList.toggle('is-active', index === nextStep);
      indicator.classList.toggle('is-complete', index < nextStep);
    });
    const modalForm = wizard.closest('.modal-form');
    if (modalForm) {
      modalForm.scrollTop = 0;
    }
  };

  const resetCompanyWizard = (modal) => {
    const wizard = getCompanyWizard(modal);
    if (!wizard) return;
    const checked = wizard.querySelector('input[name="document_type"]:checked');
    const first = wizard.querySelector('input[name="document_type"]');
    const selected = checked || first;
    if (selected) {
      selected.checked = true;
      updateDocumentLabel(wizard, selected.value);
    }
    const unitChecked = wizard.querySelector('input[name="unit_type"]:checked');
    const unitFirst = wizard.querySelector('input[name="unit_type"]');
    const unitSelected = unitChecked || unitFirst;
    if (unitSelected) {
      unitSelected.checked = true;
      updateUnitNameVisibility(wizard, unitSelected.value);
    }
    setWizardStep(wizard, 1);
  };

  const setRadioValue = (form, name, value, fallbackValue) => {
    if (!form) return;
    const selector = `input[name="${name}"]`;
    const inputs = Array.from(form.querySelectorAll(selector));
    if (!inputs.length) return;
    const targetValue = value || fallbackValue;
    const target = inputs.find((input) => input.value === targetValue) || inputs[0];
    inputs.forEach((input) => {
      input.checked = input === target;
    });
    return target ? target.value : '';
  };

  document.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-open-modal]');
    if (openButton) {
      openModal(openButton.getAttribute('data-open-modal'));
      return;
    }

    const nextButton = event.target.closest('[data-company-step-next]');
    if (nextButton) {
      const wizard = nextButton.closest('[data-company-wizard]');
      if (!wizard) return;
      const current = Number(wizard.dataset.step || 1);
      setWizardStep(wizard, current + 1);
      return;
    }

    const prevButton = event.target.closest('[data-company-step-prev]');
    if (prevButton) {
      const wizard = prevButton.closest('[data-company-wizard]');
      if (!wizard) return;
      const current = Number(wizard.dataset.step || 1);
      setWizardStep(wizard, current - 1);
      return;
    }

    const editButton = event.target.closest('[data-open-edit-company]');
    if (editButton) {
      event.preventDefault();
      event.stopPropagation();
      const editForm = document.querySelector('[data-edit-company-form]');
      if (!editForm) return;
      editForm.action = editButton.dataset.updateUrl || '';
      editForm.querySelector('#edit_company_name').value = editButton.dataset.name || '';
      editForm.querySelector('#edit_company_legal_representative').value = editButton.dataset.legalRepresentativeName || '';
      editForm.querySelector('#edit_company_cnpj').value = editButton.dataset.cnpj || '';
      editForm.querySelector('#edit_company_employee_count').value = editButton.dataset.employeeCount || '';
      editForm.querySelector('#edit_company_address_street').value = editButton.dataset.addressStreet || '';
      editForm.querySelector('#edit_company_address_number').value = editButton.dataset.addressNumber || '';
      editForm.querySelector('#edit_company_address_complement').value = editButton.dataset.addressComplement || '';
      editForm.querySelector('#edit_company_address_neighborhood').value = editButton.dataset.addressNeighborhood || '';
      editForm.querySelector('#edit_company_address_city').value = editButton.dataset.addressCity || '';
      editForm.querySelector('#edit_company_address_state').value = editButton.dataset.addressState || '';
      editForm.querySelector('#edit_company_address_zipcode').value = editButton.dataset.addressZipcode || '';
      editForm.querySelector('#edit_company_responsible_email').value = editButton.dataset.responsibleEmail || '';
      editForm.querySelector('#edit_company_assessment_type').value = editButton.dataset.assessmentType || 'setor';
      editForm.querySelector('#edit_company_cnae').value = editButton.dataset.cnae || '';
      editForm.querySelector('#edit_company_risk_level').value = editButton.dataset.riskLevel || '1';
      editForm.querySelector('#edit_company_unit_name').value = editButton.dataset.unitName || '';

      const wizard = getCompanyWizard(editForm.closest('.modal-backdrop'));
      const rawCnpj = editButton.dataset.cnpj || '';
      const digits = rawCnpj.replace(/\D/g, '');
      const docType = digits.length === 11 ? 'cpf' : 'cnpj';
      const selectedDocType = setRadioValue(editForm, 'document_type', docType, 'cnpj');
      updateDocumentLabel(wizard, selectedDocType);
      const selectedUnitType = setRadioValue(editForm, 'unit_type', editButton.dataset.unitType || '', 'matriz');
      updateUnitNameVisibility(wizard, selectedUnitType);
      if (wizard) {
        setWizardStep(wizard, 1);
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

  const submitCompaniesForm = async (form, container) => {
    const response = await fetch(form.action, {
      method: form.method || 'POST',
      body: new FormData(form),
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) {
      throw new Error('Falha ao salvar empresa.');
    }
    return await response.text();
  };

  const setButtonLoading = (button) => {
    if (!button) return null;
    const existingOriginal = button.dataset ? button.dataset.originalText : '';
    const original = existingOriginal || button.textContent || '';
    if (button.dataset && !button.dataset.originalText) {
      button.dataset.originalText = original;
    }
    button.textContent = button.getAttribute('data-loading-text') || 'Salvando...';
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    return () => {
      const restored = button.dataset && button.dataset.originalText ? button.dataset.originalText : original;
      button.textContent = restored;
      button.disabled = false;
      button.removeAttribute('aria-busy');
    };
  };

  const accessOverlayId = 'company-access-overlay';
  const showAccessOverlay = () => {
    let overlay = document.getElementById(accessOverlayId);
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = accessOverlayId;
      overlay.className = 'company-access-overlay';
      overlay.innerHTML =
        '<div class="company-access-overlay__content">' +
        '<div class="app-spinner app-spinner--lg" role="status" aria-live="polite"></div>' +
        '<p>Acessando...</p>' +
        '</div>';
      document.body.appendChild(overlay);
    }
    overlay.classList.add('is-visible');
  };

  const setLoading = (container, isLoading) => {
    if (!container) return;
    let overlay = container.querySelector('[data-table-loading-overlay]');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'table-loading-overlay';
      overlay.setAttribute('data-table-loading-overlay', '1');
      overlay.setAttribute('aria-hidden', 'true');
      overlay.innerHTML =
        '<div class="table-loading-overlay__inner">' +
        '<div class="app-spinner" role="status" aria-live="polite" aria-label="Carregando">' +
        '<span class="app-spinner__ring"></span>' +
        '</div></div>';
      container.appendChild(overlay);
    }
    overlay.classList.toggle('is-active', Boolean(isLoading));
  };

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    const isToggleForm = form.matches('[action*="/master/companies/"][action$="/delete/"]');
    const isCreateForm = form.matches('[action$="/master/companies/new/"]');
    const isEditForm = form.matches('[data-edit-company-form]');
    const isAccessForm = form.matches('[action$="/auth/select-company/"]');
    if (isAccessForm) {
      showAccessOverlay();
      return;
    }
    if (!isCreateForm && !isEditForm && !isToggleForm) return;
    event.preventDefault();
    const container = document.getElementById('companies-table-container');
    const restoreButton = setButtonLoading(event.submitter);
    if (!isToggleForm) {
      setLoading(container, true);
    } else {
      const card = form.closest('.company-card');
      if (card) {
        card.setAttribute('aria-busy', 'true');
        card.style.opacity = '0.6';
      }
    }
    try {
      const html = await submitCompaniesForm(form, container);
      if (!isToggleForm) {
        const responseDoc = new DOMParser().parseFromString(html, 'text/html');
        consumeInlineNoticesFromDoc(responseDoc);
        const nextContainer = responseDoc.querySelector(`#${containerId}`);
        if (nextContainer) {
          nextContainer.querySelectorAll('.notice, .stack-gap').forEach((node) => node.remove());
        }
        if (container) {
          container.outerHTML = nextContainer ? nextContainer.outerHTML : html;
        }
      } else {
        const responseDoc = new DOMParser().parseFromString(html, 'text/html');
        consumeInlineNoticesFromDoc(responseDoc);
        const newCard = responseDoc.querySelector(`[data-company-card-id="${form.dataset.companyId}"]`);
        const currentCard = form.closest('.company-card');
        if (newCard && currentCard) {
          currentCard.outerHTML = newCard.outerHTML;
        } else if (container) {
          container.outerHTML = html;
        }
      }
      const modal = form.closest('.modal-backdrop');
      if (modal) closeModal(modal);
    } catch (error) {
      form.submit();
    } finally {
      if (restoreButton) restoreButton();
      if (!isToggleForm) {
        setLoading(container, false);
      } else {
        const card = form.closest('.company-card');
        if (card) {
          card.removeAttribute('aria-busy');
          card.style.opacity = '';
        }
      }
    }
  });

  document.addEventListener('change', (event) => {
    const docTypeInput = event.target.closest('input[name="document_type"]');
    if (!docTypeInput) return;
    const wizard = docTypeInput.closest('[data-company-wizard]');
    updateDocumentLabel(wizard, docTypeInput.value);
  });

  document.addEventListener('change', (event) => {
    const unitTypeInput = event.target.closest('input[name="unit_type"]');
    if (!unitTypeInput) return;
    const wizard = unitTypeInput.closest('[data-company-wizard]');
    updateUnitNameVisibility(wizard, unitTypeInput.value);
  });

  const runPageHooks = () => {
    consumeInlineNotices();
  };

  window.addEventListener('page:load', runPageHooks);
  runPageHooks();
})();
