import { createCard } from '../components/card';
import { companyService } from '../services/company.service';

export const createCompaniesPage = ({ currentCompanyId, onSelectCompany }) => {
  const wrapper = document.createElement('div');
  wrapper.className = 'stack';

  const selectorCard = createCard({
    title: 'Trocar empresa',
    subtitle: 'Selecione a empresa ativa da sua sessao',
  });

  const select = document.createElement('select');
  select.className = 'input';

  companyService.list().forEach((company) => {
    const option = document.createElement('option');
    option.value = String(company.id);
    option.textContent = `${company.name} (${company.slug})`;
    if (company.id === currentCompanyId) {
      option.selected = true;
    }
    select.appendChild(option);
  });

  const button = document.createElement('button');
  button.className = 'btn btn--primary';
  button.type = 'button';
  button.textContent = 'Ativar empresa';
  button.addEventListener('click', () => {
    onSelectCompany(Number.parseInt(select.value, 10));
  });

  const content = document.createElement('div');
  content.className = 'stack';
  content.appendChild(select);
  content.appendChild(button);

  selectorCard.querySelector('.card__content').appendChild(content);
  wrapper.appendChild(selectorCard);

  return wrapper;
};
