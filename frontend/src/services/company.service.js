const defaultCompanies = [
  { id: 1, name: 'Acme', slug: 'acme' },
  { id: 2, name: 'Beta', slug: 'beta' },
];

export const companyService = {
  list() {
    return defaultCompanies;
  },
  getById(companyId) {
    return defaultCompanies.find((company) => company.id === companyId) || null;
  },
};
