(function () {
  const showAlert = (message) => {
    if (window.PlatformDialog && typeof window.PlatformDialog.alert === 'function') {
      window.PlatformDialog.alert(message);
    }
  };

  const panels = document.querySelectorAll('[data-step]');
  const openStepButtons = document.querySelectorAll('[data-open-step]');
  const backButtons = document.querySelectorAll('[data-back-home]');

  const complaintInput = document.querySelector('[data-selected-complaint]');
  const complaintForm = document.querySelector('form[action*="/complaint/"]');
  const complaintSubmitButton = document.querySelector('[data-complaint-submit]');
  const complaintDepartmentHiddenInput = document.querySelector('[data-selected-complaint-department]');
  const complaintExtraHiddenInput = document.querySelector('[data-selected-complaint-extra]');
  const complaintModal = document.querySelector('[data-complaint-modal]');
  const complaintDepartmentSelect = document.querySelector('[data-complaint-department-select]');
  const complaintExtraInput = document.querySelector('[data-complaint-extra-input]');
  const closeComplaintModalButton = document.querySelector('[data-close-complaint-modal]');
  const confirmComplaintSubmitButton = document.querySelector('[data-confirm-complaint-submit]');
  const moodInput = document.querySelector('[data-selected-mood]');
  const complaintButtons = document.querySelectorAll('[data-complaint-option]');
  const moodButtons = document.querySelectorAll('[data-mood-option]');
  const detailsBox = document.querySelector('[data-complaint-details]');
  const moodForm = document.querySelector('form[action*="/mood/"]');
  const moodDepartmentInput = document.querySelector('[data-selected-mood-department]');
  const openMoodDepartmentModalButton = document.querySelector('[data-open-mood-department-modal]');
  const moodDepartmentModal = document.querySelector('[data-mood-department-modal]');
  const moodDepartmentSelect = document.querySelector('[data-mood-department-select]');
  const closeMoodDepartmentModalButton = document.querySelector('[data-close-mood-department-modal]');
  const confirmMoodSubmitButton = document.querySelector('[data-confirm-mood-submit]');
  const inlineMessagesContainer = document.querySelector('.totem-messages');
  const toastStackId = 'totem-toast-stack';

  const setButtonLoading = (button, isLoading, loadingText) => {
    if (!button) return;
    if (isLoading) {
      if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent || '';
      }
      button.textContent = loadingText || 'Registrando...';
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

  const showStep = (name) => {
    panels.forEach((panel) => {
      const shouldShow = panel.getAttribute('data-step') === name;
      panel.classList.toggle('is-hidden', !shouldShow);
    });
  };

  const showToast = (message, tone = 'success') => {
    let stack = document.getElementById(toastStackId);
    if (!stack) {
      stack = document.createElement('div');
      stack.id = toastStackId;
      stack.className = 'totem-toast-stack';
      document.body.appendChild(stack);
    }
    const toast = document.createElement('div');
    toast.className = `totem-toast totem-toast--${tone}`;
    toast.innerHTML = `<span class="totem-toast__icon">${tone === 'success' ? 'OK' : '!'}</span><span>${message}</span>`;
    stack.appendChild(toast);
    window.setTimeout(() => {
      toast.classList.add('is-visible');
    }, 10);
    window.setTimeout(() => {
      toast.classList.remove('is-visible');
      window.setTimeout(() => toast.remove(), 220);
    }, 2400);
  };

  const consumeInlineMessages = () => {
    if (!inlineMessagesContainer) {
      return;
    }
    inlineMessagesContainer.querySelectorAll('.msg').forEach((messageNode) => {
      const tone = messageNode.classList.contains('msg--success') ? 'success' : 'error';
      showToast(messageNode.textContent.trim(), tone);
    });
    inlineMessagesContainer.remove();
  };

  const clearSelection = (buttons, input) => {
    buttons.forEach((button) => button.classList.remove('is-selected'));
    if (input) {
      input.value = '';
    }
  };

  const openComplaintModal = () => {
    if (!complaintModal) {
      return;
    }
    complaintModal.classList.add('is-open');
    complaintModal.setAttribute('aria-hidden', 'false');
  };

  const closeComplaintModal = () => {
    if (!complaintModal) {
      return;
    }
    complaintModal.classList.remove('is-open');
    complaintModal.setAttribute('aria-hidden', 'true');
  };

  openStepButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const step = button.getAttribute('data-open-step');
      showStep(step);
    });
  });

  backButtons.forEach((button) => {
    button.addEventListener('click', () => {
      clearSelection(complaintButtons, complaintInput);
      clearSelection(moodButtons, moodInput);
      if (moodDepartmentInput) {
        moodDepartmentInput.value = '';
      }
      if (moodDepartmentSelect) {
        moodDepartmentSelect.value = '';
      }
      if (detailsBox) {
        detailsBox.classList.add('is-hidden');
      }
      if (moodDepartmentModal) {
        moodDepartmentModal.classList.remove('is-open');
        moodDepartmentModal.setAttribute('aria-hidden', 'true');
      }
      if (complaintModal) {
        complaintModal.classList.remove('is-open');
        complaintModal.setAttribute('aria-hidden', 'true');
      }
      if (complaintDepartmentHiddenInput) {
        complaintDepartmentHiddenInput.value = '';
      }
      if (complaintExtraHiddenInput) {
        complaintExtraHiddenInput.value = '';
      }
      if (complaintDepartmentSelect) {
        complaintDepartmentSelect.value = '';
      }
      if (complaintExtraInput) {
        complaintExtraInput.value = '';
      }
      showStep('home');
    });
  });

  complaintButtons.forEach((button) => {
    button.addEventListener('click', () => {
      complaintButtons.forEach((item) => item.classList.remove('is-selected'));
      button.classList.add('is-selected');
      if (complaintInput) {
        complaintInput.value = button.getAttribute('data-complaint-option') || '';
      }
      if (detailsBox) {
        const isOther = (button.getAttribute('data-complaint-option') || '') === 'other';
        detailsBox.classList.toggle('is-hidden', !isOther);
      }
    });
  });

  if (complaintSubmitButton) {
    complaintSubmitButton.addEventListener('click', () => {
      const selectedComplaint = complaintInput ? complaintInput.value : '';
      if (!selectedComplaint) {
        showAlert('Selecione uma opcao para continuar.');
        return;
      }
      openComplaintModal();
    });
  }

  if (closeComplaintModalButton) {
    closeComplaintModalButton.addEventListener('click', () => {
      if (confirmComplaintSubmitButton && confirmComplaintSubmitButton.getAttribute('aria-busy') === 'true') {
        return;
      }
      closeComplaintModal();
    });
  }

  if (confirmComplaintSubmitButton) {
    confirmComplaintSubmitButton.addEventListener('click', () => {
      const departmentValue = complaintDepartmentSelect ? complaintDepartmentSelect.value.trim() : '';
      const extraValue = complaintExtraInput ? complaintExtraInput.value.trim() : '';
      if (!departmentValue) {
        showAlert('Selecione o setor.');
        return;
      }
      if (!extraValue) {
        showAlert('Informe detalhes do ocorrido.');
        return;
      }
      if (complaintDepartmentHiddenInput) {
        complaintDepartmentHiddenInput.value = departmentValue;
      }
      if (complaintExtraHiddenInput) {
        complaintExtraHiddenInput.value = extraValue;
      }
      setButtonLoading(confirmComplaintSubmitButton, true, 'Enviando...');
      if (complaintForm) {
        complaintForm.submit();
      }
    });
  }

  moodButtons.forEach((button) => {
    button.addEventListener('click', () => {
      moodButtons.forEach((item) => item.classList.remove('is-selected'));
      button.classList.add('is-selected');
      if (moodInput) {
        moodInput.value = button.getAttribute('data-mood-option') || '';
      }
    });
  });

  const openMoodDepartmentModal = () => {
    if (!moodDepartmentModal) {
      return;
    }
    moodDepartmentModal.classList.add('is-open');
    moodDepartmentModal.setAttribute('aria-hidden', 'false');
  };

  const closeMoodDepartmentModal = () => {
    if (!moodDepartmentModal) {
      return;
    }
    moodDepartmentModal.classList.remove('is-open');
    moodDepartmentModal.setAttribute('aria-hidden', 'true');
  };

  if (openMoodDepartmentModalButton) {
    openMoodDepartmentModalButton.addEventListener('click', () => {
      if (!moodInput || !moodInput.value) {
        showAlert('Selecione uma opcao de humor antes de seguir.');
        return;
      }
      openMoodDepartmentModal();
    });
  }

  if (closeMoodDepartmentModalButton) {
    closeMoodDepartmentModalButton.addEventListener('click', () => {
      closeMoodDepartmentModal();
    });
  }

  if (confirmMoodSubmitButton) {
    confirmMoodSubmitButton.addEventListener('click', async () => {
      if (!moodDepartmentSelect || !moodDepartmentSelect.value) {
        showAlert('Selecione um setor para confirmar.');
        return;
      }
      if (moodDepartmentInput) {
        moodDepartmentInput.value = moodDepartmentSelect.value;
      }
      if (moodForm) {
        try {
          setButtonLoading(confirmMoodSubmitButton, true, 'Registrando...');
          const response = await fetch(moodForm.action, {
            method: 'POST',
            body: new FormData(moodForm),
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
            },
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || 'Nao foi possivel registrar o humor.');
          }

          showToast(payload.message || 'Humor registrado com sucesso.');
          closeMoodDepartmentModal();
          clearSelection(moodButtons, moodInput);
          if (moodDepartmentInput) {
            moodDepartmentInput.value = '';
          }
          if (moodDepartmentSelect) {
            moodDepartmentSelect.value = '';
          }
          showStep('intro');
        } catch (error) {
          showAlert(error.message || 'Nao foi possivel registrar o humor.');
        } finally {
          setButtonLoading(confirmMoodSubmitButton, false);
        }
      }
    });
  }

  if (moodDepartmentModal) {
    moodDepartmentModal.addEventListener('click', (event) => {
      if (event.target === moodDepartmentModal) {
        closeMoodDepartmentModal();
      }
    });
  }

  if (complaintModal) {
    complaintModal.addEventListener('click', (event) => {
      if (event.target === complaintModal) {
        if (confirmComplaintSubmitButton && confirmComplaintSubmitButton.getAttribute('aria-busy') === 'true') {
          return;
        }
        closeComplaintModal();
      }
    });
  }

  consumeInlineMessages();
})();
