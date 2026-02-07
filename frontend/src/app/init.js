import { createDashboardShell } from '../layouts/dashboard-shell';
import { env } from '../config/env';
import { authService } from '../services/auth.service';
import { createCompaniesPage } from '../pages/companies.page';
import { createDashboardPage } from '../pages/dashboard.page';
import { createLoginPage } from '../pages/login.page';
import { appState } from './state';
import { getCurrentRoute, navigateTo, onRouteChange } from './router';

const renderLogin = (target, errorMessage = '') => {
  target.innerHTML = '';
  const loginPage = createLoginPage({
    errorMessage,
    onSubmit: ({ username, password }) => {
      try {
        authService.login({ username, password });
        navigateTo('#/dashboard');
      } catch (error) {
        renderLogin(target, error.message);
      }
    },
  });
  target.appendChild(loginPage);
};

const renderProtectedPage = async (target) => {
  const user = appState.getUser();
  if (!user) {
    navigateTo('#/login');
    return;
  }

  const route = getCurrentRoute();
  const pageTitle = route === '#/companies' ? 'Empresas' : 'Tela inicial';

  target.innerHTML = '';
  const { shell, body } = createDashboardShell({
    appName: env.appName,
    activeRoute: route,
    userName: user.name,
    pageTitle,
    onLogout: () => {
      authService.logout();
      navigateTo('#/login');
    },
  });

  if (route === '#/companies') {
    const page = createCompaniesPage({
      currentCompanyId: appState.getCompanyId(),
      onSelectCompany: (companyId) => {
        appState.setCompanyId(companyId);
        navigateTo('#/dashboard');
      },
    });
    body.appendChild(page);
  } else {
    const dashboardPage = await createDashboardPage({
      companyId: appState.getCompanyId(),
      userName: user.name,
    });
    body.appendChild(dashboardPage);
  }

  target.appendChild(shell);
};

const render = async (target) => {
  const route = getCurrentRoute();
  if (route === '#/login') {
    renderLogin(target);
    return;
  }
  await renderProtectedPage(target);
};

export const mountApp = (target) => {
  if (!window.location.hash) {
    navigateTo('#/login');
  }
  render(target);
  onRouteChange(() => {
    render(target);
  });
};
