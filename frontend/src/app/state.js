const AUTH_KEY = 'nr1_auth_user';
const COMPANY_KEY = 'company_id';

const readJson = (key, fallback = null) => {
  const value = localStorage.getItem(key);
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
};

export const appState = {
  getUser() {
    return readJson(AUTH_KEY);
  },
  setUser(user) {
    localStorage.setItem(AUTH_KEY, JSON.stringify(user));
  },
  clearUser() {
    localStorage.removeItem(AUTH_KEY);
  },
  getCompanyId() {
    return Number.parseInt(localStorage.getItem(COMPANY_KEY) || '1', 10);
  },
  setCompanyId(companyId) {
    localStorage.setItem(COMPANY_KEY, String(companyId));
  },
};
