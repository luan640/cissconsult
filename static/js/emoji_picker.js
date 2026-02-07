(function () {
  const triggerSelector = '[data-emoji-picker-trigger]';
  const buttonApi = window.EmojiButton;
  const pickerByInputId = new Map();

  if (!buttonApi || typeof buttonApi.EmojiButton !== 'function') {
    return;
  }

  const getInputByTrigger = (trigger) => {
    const targetId = trigger.getAttribute('data-target-input') || '';
    if (!targetId) {
      return null;
    }
    return document.getElementById(targetId);
  };

  const getOrCreatePicker = (inputId) => {
    if (pickerByInputId.has(inputId)) {
      return pickerByInputId.get(inputId);
    }

    const picker = new buttonApi.EmojiButton({
      position: 'bottom-start',
      showSearch: true,
      autoHide: true,
      theme: 'light',
      zIndex: 2200,
    });
    pickerByInputId.set(inputId, picker);
    return picker;
  };

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest(triggerSelector);
    if (!trigger) {
      return;
    }

    const targetInput = getInputByTrigger(trigger);
    if (!targetInput) {
      return;
    }

    const picker = getOrCreatePicker(targetInput.id);
    picker.off('emoji');
    picker.on('emoji', (selection) => {
      targetInput.value = selection.emoji;
      targetInput.dispatchEvent(new Event('input', { bubbles: true }));
      targetInput.focus();
    });
    picker.togglePicker(trigger);
  });
})();
