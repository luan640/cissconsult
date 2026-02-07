import { createElement } from '../utils/dom';

export const createButton = ({ label, variant = 'primary', onClick }) => {
  const button = createElement('button', `btn btn--${variant}`, label);
  if (onClick) {
    button.addEventListener('click', onClick);
  }
  return button;
};
