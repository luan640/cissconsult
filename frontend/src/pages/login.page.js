import { createElement } from '../utils/dom';

export const createLoginPage = ({ onSubmit, errorMessage }) => {
  const container = createElement('main', 'auth-page');
  const panel = createElement('section', 'auth-panel');
  const title = createElement('h1', 'auth-title', 'Acessar plataforma');
  const subtitle = createElement(
    'p',
    'auth-subtitle',
    'Entre com seu usuario para acessar o ambiente multi-tenant.'
  );
  const form = createElement('form', 'auth-form');
  const usernameInput = createElement('input', 'input');
  const passwordInput = createElement('input', 'input');
  const button = createElement('button', 'btn btn--primary', 'Entrar');
  const hint = createElement('small', 'text-muted', 'Exemplo rapido: owner / 12345678');

  usernameInput.name = 'username';
  usernameInput.placeholder = 'Usuario';
  usernameInput.autocomplete = 'username';
  passwordInput.name = 'password';
  passwordInput.type = 'password';
  passwordInput.placeholder = 'Senha';
  passwordInput.autocomplete = 'current-password';
  button.type = 'submit';

  form.appendChild(usernameInput);
  form.appendChild(passwordInput);
  form.appendChild(button);
  form.appendChild(hint);

  if (errorMessage) {
    const error = createElement('p', 'error-text', errorMessage);
    panel.appendChild(error);
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    onSubmit({
      username: usernameInput.value.trim(),
      password: passwordInput.value,
    });
  });

  panel.appendChild(title);
  panel.appendChild(subtitle);
  panel.appendChild(form);
  container.appendChild(panel);

  return container;
};
