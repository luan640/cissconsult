import { createSidebar } from '../components/sidebar';
import { createElement } from '../utils/dom';

export const createDashboardShell = ({
  appName,
  activeRoute,
  userName,
  pageTitle,
  onLogout,
}) => {
  const shell = createElement('div', 'dashboard-shell');
  const sidebar = createSidebar({ appName, activeRoute, userName, onLogout });
  const content = createElement('section', 'dashboard-content');
  const heading = createElement('h1', 'dashboard-title', pageTitle);
  const body = createElement('div', 'dashboard-body');

  content.appendChild(heading);
  content.appendChild(body);
  shell.appendChild(sidebar);
  shell.appendChild(content);

  return { shell, body };
};
