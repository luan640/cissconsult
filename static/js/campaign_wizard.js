(function () {
  const root = document.querySelector('.campaign-step');
  const form = document.getElementById('wizard-form');
  if (!root || !form) return;

  const campaignUuid = root.dataset.campaignUuid;
  const storageKey = `campaign:${campaignUuid}:responses`;
  const initialStep = parseInt(root.dataset.initialStep || '1', 10) || 1;
  const totalSteps = 10;

  const loadState = () => {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || '{}');
    } catch (err) {
      return {};
    }
  };

  const saveState = (state) => {
    localStorage.setItem(storageKey, JSON.stringify(state));
  };

  const showStep = (step) => {
    const sections = Array.from(document.querySelectorAll('.wizard-step'));
    sections.forEach((section) => {
      section.classList.toggle('is-active', Number(section.dataset.step) === step);
    });
    const badge = document.querySelector('[data-step-badge]');
    const progress = document.querySelector('[data-step-progress]');
    if (badge) badge.textContent = `Etapa ${step} de ${totalSteps}`;
    if (progress) progress.style.width = `${Math.min(100, Math.max(0, step * 10))}%`;
  };

  const stripQuestionNumber = (text) =>
    (text || '').replace(/^\s*\d+\.\s*/, '').trim();

  const restoreMeta = (state) => {
    const meta = state.meta || {};
    const cpfInput = form.querySelector('#cpf');
    const ageInput = form.querySelector('#age');
    const firstNameInput = form.querySelector('#first_name');
    const sexSelect = form.querySelector('#sex');
    const gheSelect = form.querySelector('#ghe_id');
    const departmentSelect = form.querySelector('#department_id');
    const jobFunctionSelect = form.querySelector('#job_function_id');

    if (cpfInput && meta.cpf) cpfInput.value = meta.cpf;
    if (ageInput && meta.age) ageInput.value = meta.age;
    if (firstNameInput && meta.first_name) firstNameInput.value = meta.first_name;
    if (sexSelect && meta.sex) sexSelect.value = meta.sex;

    const waitForOption = (select, value, attempts = 15) => {
      if (!select || !value) return;
      const trySet = () => {
        const option = select.querySelector(`option[value="${value}"]`);
        if (option) {
          select.value = value;
          return true;
        }
        return false;
      };
      let tries = 0;
      const timer = setInterval(() => {
        tries += 1;
        if (trySet() || tries >= attempts) {
          clearInterval(timer);
        }
      }, 200);
    };

    if (gheSelect && meta.ghe_id) {
      gheSelect.value = String(meta.ghe_id);
      gheSelect.dispatchEvent(new Event('change'));
      waitForOption(departmentSelect, String(meta.department_id));
    } else if (departmentSelect && meta.department_id) {
      departmentSelect.value = String(meta.department_id);
      departmentSelect.dispatchEvent(new Event('change'));
      waitForOption(jobFunctionSelect, String(meta.job_function_id));
    }
    scheduleCpfCheck();
  };

  const restoreStepAnswers = (state) => {
    const responses = state.responses || {};
    Object.keys(responses).forEach((stepKey) => {
      const stepNumber = parseInt(stepKey.replace('step', ''), 10);
      const section = document.querySelector(`.wizard-step[data-step="${stepNumber}"]`);
      if (!section) return;
      const saved = responses[stepKey] || [];
      saved.forEach((item, index) => {
        const selector = `input[name="step${stepNumber}q${index + 1}"][value="${item.answer}"]`;
        const input = section.querySelector(selector);
        if (input) input.checked = true;
      });
    });
  };

  const restoreComment = (state) => {
    const textarea = form.querySelector('#comments');
    const counter = document.querySelector('.comment-card__footer');
    if (textarea && state.comments) {
      textarea.value = state.comments;
    }
    if (textarea && counter) {
      counter.textContent = `${textarea.value.length}/1000 caracteres`;
    }
  };

  const validateStep1 = () => {
    const cpfInput = form.querySelector('#cpf');
    const ageInput = form.querySelector('#age');
    const gheSelect = form.querySelector('#ghe_id');
    const departmentSelect = form.querySelector('#department_id');
    const jobFunctionSelect = form.querySelector('#job_function_id');
    const useGhe = form.getAttribute('data-use-ghe') === '1';
    if (cpfCheckInFlight || !cpfIsAvailable) {
      alert('CPF ja utilizado ou nao validado.');
      return false;
    }

    const cpfDigits = (cpfInput?.value || '').replace(/\D/g, '');
    const ageValue = parseInt(ageInput?.value || '0', 10);
    if (cpfDigits.length !== 11 || !Number.isFinite(ageValue) || ageValue <= 0) {
      alert('Preencha CPF e idade corretamente.');
      return false;
    }
    if (useGhe) {
      if (!gheSelect?.value || !departmentSelect?.value) {
        alert('Selecione GHE e Cargo/Funcao.');
        return false;
      }
    } else {
      if (!departmentSelect?.value || !jobFunctionSelect?.value) {
        alert('Selecione Setor e Cargo/Funcao.');
        return false;
      }
    }
    return true;
  };

  const validateQuestionsStep = (step) => {
    const section = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (!section) return false;
    const groups = Array.from(section.querySelectorAll('.question-card'));
    let firstInvalid = null;
    for (const group of groups) {
      const radios = group.querySelectorAll('input[type="radio"]');
      const checked = Array.from(radios).some((radio) => radio.checked);
      if (!checked && !firstInvalid) {
        firstInvalid = group;
      }
    }
    if (firstInvalid) {
      firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
      firstInvalid.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.25)';
      setTimeout(() => {
        firstInvalid.style.boxShadow = '';
      }, 1200);
      alert('Responda todas as perguntas para continuar.');
      return false;
    }
    return true;
  };

  const saveStep1 = (state) => {
    const cpfInput = form.querySelector('#cpf');
    const ageInput = form.querySelector('#age');
    const firstNameInput = form.querySelector('#first_name');
    const sexSelect = form.querySelector('#sex');
    const gheSelect = form.querySelector('#ghe_id');
    const departmentSelect = form.querySelector('#department_id');
    const jobFunctionSelect = form.querySelector('#job_function_id');
    state.meta = {
      cpf: (cpfInput?.value || '').trim(),
      age: parseInt(ageInput?.value || '0', 10),
      first_name: (firstNameInput?.value || '').trim(),
      sex: (sexSelect?.value || '').trim(),
      ghe_id: gheSelect?.value ? Number(gheSelect.value) : null,
      department_id: departmentSelect?.value ? Number(departmentSelect.value) : null,
      job_function_id: jobFunctionSelect?.value ? Number(jobFunctionSelect.value) : null,
    };
  };

  const saveStepAnswers = (state, step) => {
    const section = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (!section) return;
    const questions = Array.from(section.querySelectorAll('.question-card'));
    const answers = questions.map((group, index) => {
      const title = group.querySelector('.question-card__title');
      const questionText = title ? stripQuestionNumber(title.textContent) : '';
      const checked = group.querySelector('input[type="radio"]:checked');
      return {
        question: questionText,
        answer: checked ? checked.value : '',
      };
    });
    state.responses = state.responses || {};
    state.responses[`step${step}`] = answers;
  };

  const saveComment = (state) => {
    const textarea = form.querySelector('#comments');
    if (textarea) {
      state.comments = textarea.value.trim();
    }
  };

  const goToStep = (step) => {
    showStep(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  form.addEventListener('click', function (event) {
    const nextBtn = event.target.closest('[data-next-step]');
    const prevBtn = event.target.closest('[data-prev-step]');
    if (!nextBtn && !prevBtn) return;
    event.preventDefault();

    const active = document.querySelector('.wizard-step.is-active');
    const currentStep = active ? Number(active.dataset.step) : 1;
    const state = loadState();

    if (prevBtn) {
      const target = Math.max(1, currentStep - 1);
      goToStep(target);
      return;
    }

    if (currentStep === 1) {
      if (!validateStep1()) return;
      saveStep1(state);
      saveState(state);
      goToStep(2);
      return;
    }

    if (currentStep >= 2 && currentStep <= 8) {
      if (!validateQuestionsStep(currentStep)) return;
      saveStepAnswers(state, currentStep);
      saveState(state);
      goToStep(currentStep + 1);
    }
  });

  form.addEventListener('submit', function (event) {
    const active = document.querySelector('.wizard-step.is-active');
    const currentStep = active ? Number(active.dataset.step) : 1;
    if (currentStep !== 9) {
      event.preventDefault();
      return;
    }

    const state = loadState();
    saveComment(state);
    saveState(state);
    const payloadInput = form.querySelector('input[name="local_payload"]');
    payloadInput.value = JSON.stringify(state);
  });

  const init = () => {
    const state = loadState();
    restoreMeta(state);
    restoreStepAnswers(state);
    restoreComment(state);
    showStep(initialStep);
  };

  let cpfIsAvailable = false;
  let cpfCheckInFlight = false;
  let lastCpfChecked = '';
  let debounceId = null;

  const setCpfError = (message) => {
    const errorEl = form.querySelector('[data-cpf-error]');
    if (!errorEl) return;
    if (message) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';
    } else {
      errorEl.textContent = '';
      errorEl.style.display = 'none';
    }
  };

  const checkCpf = async (cpfDigits) => {
    const checkUrl = form.getAttribute('data-cpf-check-url') || '';
    if (!checkUrl || cpfDigits.length !== 11) {
      cpfIsAvailable = false;
      return;
    }
    cpfCheckInFlight = true;
    try {
      const response = await fetch(`${checkUrl}?cpf=${encodeURIComponent(cpfDigits)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error('request_failed');
      const payload = await response.json();
      cpfIsAvailable = Boolean(payload.available);
      setCpfError(payload.available ? '' : (payload.message || 'CPF ja utilizado.'));
    } catch (err) {
      cpfIsAvailable = false;
      setCpfError('Nao foi possivel validar o CPF agora.');
    } finally {
      cpfCheckInFlight = false;
    }
  };

  const scheduleCpfCheck = () => {
    const cpfInput = form.querySelector('#cpf');
    if (!cpfInput) return;
    const cpfDigits = (cpfInput.value || '').replace(/\D/g, '');
    setCpfError('');
    if (cpfDigits.length !== 11) {
      cpfIsAvailable = false;
      lastCpfChecked = '';
      return;
    }
    if (cpfDigits === lastCpfChecked || cpfCheckInFlight) return;
    if (debounceId) clearTimeout(debounceId);
    debounceId = setTimeout(() => {
      lastCpfChecked = cpfDigits;
      checkCpf(cpfDigits);
    }, 350);
  };

  const bindDynamicSelects = () => {
    const useGhe = form.getAttribute('data-use-ghe') === '1';
    const gheSelect = form.querySelector('[data-ghe-select]');
    const departmentSelect = form.querySelector('[data-department-select]');
    const jobFunctionSelect = form.querySelector('[data-job-function-select]');
    const departmentsUrl = gheSelect ? gheSelect.getAttribute('data-departments-url') : '';
    const jobFunctionsUrl = departmentSelect ? departmentSelect.getAttribute('data-job-functions-url') : '';

    const setDepartmentState = (state) => {
      if (!departmentSelect) return;
      departmentSelect.disabled = Boolean(state.disabled);
      departmentSelect.innerHTML = `<option value="">${state.label}</option>`;
    };

    const setJobFunctionState = (state) => {
      if (!jobFunctionSelect) return;
      jobFunctionSelect.disabled = Boolean(state.disabled);
      jobFunctionSelect.innerHTML = `<option value="">${state.label}</option>`;
    };

    const loadDepartments = async (gheId) => {
      if (!gheId || !departmentsUrl) {
        setDepartmentState({ disabled: true, label: 'Selecione o GHE primeiro' });
        return;
      }
      setDepartmentState({ disabled: true, label: 'Carregando...' });
      let payload = null;
      try {
        const response = await fetch(`${departmentsUrl}?ghe_id=${encodeURIComponent(gheId)}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error('request_failed');
        payload = await response.json();
      } catch (err) {
        setDepartmentState({ disabled: true, label: 'Nao foi possivel carregar' });
        return;
      }
      const departments = Array.isArray(payload.departments) ? payload.departments : [];
      if (!departments.length) {
        setDepartmentState({ disabled: true, label: 'Nenhum setor disponivel' });
        return;
      }
      departmentSelect.disabled = false;
      departmentSelect.innerHTML = [
        '<option value="">Selecione</option>',
        ...departments.map((dept) => `<option value="${dept.id}">${dept.name}</option>`),
      ].join('');
    };

    const loadJobFunctions = async (departmentId) => {
      if (!departmentId || !jobFunctionsUrl) {
        setJobFunctionState({ disabled: true, label: 'Selecione o setor primeiro' });
        return;
      }
      setJobFunctionState({ disabled: true, label: 'Carregando...' });
      let payload = null;
      try {
        const response = await fetch(`${jobFunctionsUrl}?department_id=${encodeURIComponent(departmentId)}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error('request_failed');
        payload = await response.json();
      } catch (err) {
        setJobFunctionState({ disabled: true, label: 'Nao foi possivel carregar' });
        return;
      }
      const jobFunctions = Array.isArray(payload.job_functions) ? payload.job_functions : [];
      if (!jobFunctions.length) {
        setJobFunctionState({ disabled: true, label: 'Nenhuma funcao disponivel' });
        return;
      }
      jobFunctionSelect.disabled = false;
      jobFunctionSelect.innerHTML = [
        '<option value="">Selecione</option>',
        ...jobFunctions.map((item) => `<option value="${item.id}">${item.name}</option>`),
      ].join('');
    };

    if (useGhe && gheSelect && departmentSelect) {
      gheSelect.addEventListener('change', (event) => {
        loadDepartments(event.target.value);
      });
    }
    if (!useGhe && departmentSelect && jobFunctionSelect) {
      departmentSelect.addEventListener('change', (event) => {
        loadJobFunctions(event.target.value);
      });
    }
  };

  const bindCommentCounter = () => {
    const textarea = form.querySelector('#comments');
    const counter = document.querySelector('.comment-card__footer');
    if (!textarea || !counter) return;
    const updateCounter = () => {
      counter.textContent = `${textarea.value.length}/1000 caracteres`;
    };
    textarea.addEventListener('input', updateCounter);
    updateCounter();
  };

  const bindCpfCheck = () => {
    const cpfInput = form.querySelector('#cpf');
    if (!cpfInput) return;
    cpfInput.addEventListener('input', scheduleCpfCheck);
  };

  init();
  bindDynamicSelects();
  bindCommentCounter();
  bindCpfCheck();
})();
