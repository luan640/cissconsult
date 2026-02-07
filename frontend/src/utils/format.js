export const formatDate = (value) => {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat('pt-BR').format(date);
};
