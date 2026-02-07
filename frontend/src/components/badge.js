import { createElement } from '../utils/dom';

export const createBadge = ({ text, tone = 'neutral' }) => {
  return createElement('span', `badge badge--${tone}`, text);
};
