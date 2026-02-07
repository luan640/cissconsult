import { createElement } from '../utils/dom';

const navItems = [
  { href: '#/dashboard', label: 'Tela inicial' },
  { href: '#/companies', label: 'Empresas' },
];

export const createSidebar = ({ appName, activeRoute, userName, onLogout }) => {
  const sidebar = createElement('aside', 'sidebar');
  const brand = createElement('h2', 'sidebar__brand', appName);
  const user = createElement('p', 'sidebar__user', `Usuario: ${userName}`);
  const nav = createElement('nav', 'sidebar__nav');

  navItems.forEach((item) => {
    const link = createElement(
      'a',
      `sidebar__link${activeRoute === item.href ? ' is-active' : ''}`,
      item.label
    );
    link.href = item.href;
    nav.appendChild(link);
  });

  const logoutButton = createElement('button', 'btn btn--secondary sidebar__logout', 'Sair');
  logoutButton.type = 'button';
  logoutButton.addEventListener('click', onLogout);

  sidebar.appendChild(brand);
  sidebar.appendChild(user);
  sidebar.appendChild(nav);
  sidebar.appendChild(logoutButton);

  return sidebar;
};
