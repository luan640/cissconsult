import { createBadge } from '../components/badge';
import { createCard } from '../components/card';
import { companyService } from '../services/company.service';
import { healthService } from '../services/health.service';
import { formatDate } from '../utils/format';

const createKpiCard = ({ title, value, helper }) =>
  createCard({
    title,
    subtitle: helper,
    content: value,
  });

export const createDashboardPage = async ({ companyId, userName }) => {
  const wrapper = document.createElement('div');
  wrapper.className = 'grid';

  const company = companyService.getById(companyId);
  const companyName = company ? company.name : `Empresa ${companyId}`;

  const welcomeCard = createCard({
    title: `Bem-vindo, ${userName}`,
    content: `Ultima atualização: ${formatDate(new Date())}`,
  });

  let apiBadge = createBadge({ text: 'API indisponivel', tone: 'danger' });
  try {
    const payload = await healthService.getStatus();
    apiBadge = createBadge({
      text: payload.status === 'ok' ? 'API Online' : 'API com alerta',
      tone: payload.status === 'ok' ? 'success' : 'danger',
    });
  } catch (error) {
    // keep fallback badge
  }

  const healthCard = createCard({
    title: 'Status da plataforma',
    subtitle: 'Conectividade de backend',
    content: apiBadge,
  });

  const peopleCard = createKpiCard({
    title: 'Usuarios monitorados',
    value: '24',
    helper: 'Base inicial da empresa',
  });

  const alertsCard = createKpiCard({
    title: 'Alertas em aberto',
    value: '3',
    helper: 'Prioridade alta: 1',
  });

  wrapper.appendChild(welcomeCard);
  wrapper.appendChild(healthCard);
  wrapper.appendChild(peopleCard);
  wrapper.appendChild(alertsCard);

  return wrapper;
};
