import { apiRequest } from './http';

export const healthService = {
  async getStatus() {
    return apiRequest('/healthz/');
  },
};
