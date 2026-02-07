const toInt = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

export const env = {
  appName: import.meta.env.VITE_APP_NAME || 'PLATAFORMA NR-1',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  defaultCompanyId: toInt(import.meta.env.VITE_COMPANY_ID || '1', 1),
};
