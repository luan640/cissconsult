import { createElement } from '../utils/dom';

export const createCard = ({ title, subtitle, content }) => {
  const card = createElement('section', 'card');
  const heading = createElement('h2', 'card__title', title);
  const helper = createElement('p', 'card__subtitle', subtitle);
  const body = createElement('div', 'card__content');
  if (typeof content === 'string') {
    body.textContent = content;
  } else if (content) {
    body.appendChild(content);
  }

  card.appendChild(heading);
  if (subtitle) {
    card.appendChild(helper);
  }
  card.appendChild(body);

  return card;
};
