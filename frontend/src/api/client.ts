import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

const client = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const tokens = localStorage.getItem("tokens");
  if (tokens) {
    const { access } = JSON.parse(tokens);
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const tokens = localStorage.getItem("tokens");
      if (tokens) {
        try {
          const { refresh } = JSON.parse(tokens);
          const res = await axios.post(`${API_URL}/auth/refresh/`, { refresh });
          const newTokens = { access: res.data.access, refresh: res.data.refresh || refresh };
          localStorage.setItem("tokens", JSON.stringify(newTokens));
          original.headers.Authorization = `Bearer ${newTokens.access}`;
          return client(original);
        } catch {
          localStorage.removeItem("tokens");
          localStorage.removeItem("user");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default client;
