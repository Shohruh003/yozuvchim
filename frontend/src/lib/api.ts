import axios, { AxiosError } from 'axios';
import { useAuthStore } from '@/stores/auth';

const baseURL = (import.meta.env.VITE_API_URL as string | undefined) || '/api';

export const api = axios.create({
  baseURL,
  withCredentials: true,
});

// Attach access token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto refresh on 401
let refreshPromise: Promise<string | null> | null = null;
async function tryRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = api
      .post('/auth/refresh', {})
      .then((r) => {
        const tok = (r.data?.data?.access_token ?? r.data?.access_token) as string | undefined;
        if (tok) useAuthStore.getState().setAccessToken(tok);
        return tok ?? null;
      })
      .catch(() => null)
      .finally(() => {
        setTimeout(() => (refreshPromise = null), 100);
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const status = err.response?.status;
    const cfg: any = err.config || {};
    if (
      status === 401 &&
      !cfg.__retried &&
      !cfg.url?.includes('/auth/')
    ) {
      cfg.__retried = true;
      const tok = await tryRefresh();
      if (tok) {
        cfg.headers = cfg.headers ?? {};
        cfg.headers.Authorization = `Bearer ${tok}`;
        return api.request(cfg);
      }
      useAuthStore.getState().clear();
    }
    return Promise.reject(err);
  },
);

/** Unwrap `{ data: T }` envelope */
export async function apiGet<T>(url: string): Promise<T> {
  const r = await api.get(url);
  return r.data?.data ?? r.data;
}
export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const r = await api.post(url, body);
  return r.data?.data ?? r.data;
}
