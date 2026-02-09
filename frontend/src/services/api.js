const API_BASE = '/api';

export const searchTrials = async (query, page = 1, size = 10) => {
  const encoded = encodeURIComponent(query.trim());
  const res = await fetch(`${API_BASE}/search/${encoded}?page=${page}&size=${size}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export const checkHealth = async () => {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
};
