(function () {
  const form = document.getElementById('step-form');
  if (!form) return;

  const campaignUuid = form.dataset.campaignUuid;
  const step = parseInt(form.dataset.step || '0', 10);
  const isFinal = form.dataset.finalStep === '1';
  if (!campaignUuid || !step) return;

  const storageKey = `campaign:${campaignUuid}:responses`;

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

  const stripQuestionNumber = (text) =>
    (text || '').replace(/^\s*\d+\.\s*/, '').trim();

  const restoreAnswers = () => {
    const state = loadState();
    if (step >= 2 && step <= 8) {
      const stepKey = `step${step}`;
      const saved = (state.responses || {})[stepKey] || [];
      if (!saved.length) return;
      const answersMap = {};
      saved.forEach((item, index) => {
        const key = String(index + 1);
        answersMap[key] = item.answer;
      });
      const groups = Array.from(form.querySelectorAll('.question-card'));
      groups.forEach((group, idx) => {
        const answer = answersMap[String(idx + 1)];
        if (!answer) return;
        const radios = group.querySelectorAll('input[type="radio"]');
        radios.forEach((radio) => {
          radio.checked = radio.value === answer;
        });
      });
    }
    if (step === 9) {
      const textarea = form.querySelector('textarea[name="comments"]');
      if (!textarea) return;
      if (textarea.value.trim()) return;
      textarea.value = (state.comments || '').trim();
      const counter = document.querySelector('.comment-card__footer');
      if (counter) {
        counter.textContent = `${textarea.value.length}/1000 caracteres`;
      }
    }
  };

  const validateStep = () => {
    if (step < 2 || step > 8) return true;
    const groups = Array.from(form.querySelectorAll('.question-card'));
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

  const collectAnswers = () => {
    const groups = Array.from(form.querySelectorAll('.question-card'));
    return groups.map((group) => {
      const title = group.querySelector('.question-card__title');
      const questionText = title ? stripQuestionNumber(title.textContent) : '';
      const checked = group.querySelector('input[type="radio"]:checked');
      return {
        question: questionText,
        answer: checked ? checked.value : '',
      };
    });
  };

  const ensurePayloadInput = (payload) => {
    let input = form.querySelector('input[name="local_payload"]');
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'local_payload';
      form.appendChild(input);
    }
    input.value = JSON.stringify(payload);
  };

  restoreAnswers();

  form.addEventListener('submit', function (event) {
    const state = loadState();
    state.responses = state.responses || {};
    if (step >= 2 && step <= 8) {
      if (!validateStep()) {
        event.preventDefault();
        return;
      }
      state.responses[`step${step}`] = collectAnswers();
      saveState(state);
      event.preventDefault();
      window.location.href = `${form.action}?step=${step + 1}`;
      return;
    }

    if (step === 9) {
      const textarea = form.querySelector('textarea[name="comments"]');
      if (textarea) {
        state.comments = textarea.value.trim();
      }
      saveState(state);
      ensurePayloadInput(state);
    }
  });
})();
