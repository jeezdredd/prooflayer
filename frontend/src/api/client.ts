import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

let accessToken: string | null = sessionStorage.getItem("access") || null;

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) sessionStorage.setItem("access", token);
  else sessionStorage.removeItem("access");
}

export function getAccessToken(): string | null {
  return accessToken;
}

const client = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

client.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  try {
    const res = await axios.post(
      `${API_URL}/auth/refresh/`,
      {},
      { withCredentials: true }
    );
    const next = res.data.access as string;
    setAccessToken(next);
    return next;
  } catch {
    setAccessToken(null);
    localStorage.removeItem("user");
    return null;
  }
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const url: string = original?.url || "";
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !url.includes("/auth/refresh/") &&
      !url.includes("/auth/login/")
    ) {
      original._retry = true;
      if (!refreshPromise) refreshPromise = refreshAccess();
      const next = await refreshPromise;
      refreshPromise = null;
      if (next) {
        original.headers.Authorization = `Bearer ${next}`;
        return client(original);
      }
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
