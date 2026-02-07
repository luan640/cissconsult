import { env } from '../config/env';

const resolveCompanyId = () => {
  const stored = localStorage.getItem('company_id');
  return stored || String(env.defaultCompanyId);
};

export const apiRequest = async (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('X-Company-Id')) {
    headers.set('X-Company-Id', resolveCompanyId());
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const message = `Erro ${response.status} em ${path}`;
    throw new Error(message);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
};
