const normalizeHash = () => {
  const hash = window.location.hash || '#/dashboard';
  if (hash === '#') {
    return '#/dashboard';
  }
  return hash;
};

export const getCurrentRoute = () => normalizeHash();

export const navigateTo = (route) => {
  window.location.hash = route;
};

export const onRouteChange = (callback) => {
  window.addEventListener('hashchange', callback);
};
