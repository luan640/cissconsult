import { appState } from '../app/state';

export const authService = {
  login({ username, password }) {
    if (!username || !password) {
      throw new Error('Informe usuario e senha.');
    }
    const user = {
      id: 1,
      name: username,
      role: 'owner',
    };
    appState.setUser(user);
    return user;
  },
  logout() {
    appState.clearUser();
  },
};
