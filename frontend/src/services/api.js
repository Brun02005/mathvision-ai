import axios from 'axios';
import { accessToken, supabase } from './supabase';

const api = axios.create({
  // Same-origin /api by default (Vite proxy in dev, nginx in Docker). Override with VITE_API_URL.
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 150000, // OCR + symbolic solving + AI fallback (each step has its own server-side limit)
});

// Every request carries the user's session token
api.interceptors.request.use(async (config) => {
  const token = await accessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// A rejected session (expired, revoked) signs the user out: the app then shows the login
api.interceptors.response.use(undefined, async (error) => {
  if (error.response?.status === 401 && supabase) await supabase.auth.signOut();
  return Promise.reject(error);
});

/** Human-readable message for any API error. */
export function errorMessage(err) {
  if (err.code === 'ERR_NETWORK') {
    return 'No se puede conectar con el servidor. Asegurate de que el backend esté corriendo.';
  }
  if (err.code === 'ECONNABORTED') {
    return 'Tiempo de espera agotado. Si usás imagen, el OCR puede tardar la primera vez. Intentá de nuevo o usá el modo texto.';
  }
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('. ');
  return err.message || 'Error inesperado.';
}

/** True when the request failed because the plan's daily limit was reached. */
export function isLimitError(err) {
  return err.response?.status === 429 && err.response?.data?.detail?.code === 'daily_limit';
}

/** Account: email, plan ("free" | "pro"), pro_until, usage today, billing availability and price. */
export async function getMe() {
  const { data } = await api.get('/me');
  return data;
}

/** Start the Mercado Pago subscription: returns the checkout URL to redirect to. */
export async function subscribe() {
  const { data } = await api.post('/billing/subscribe');
  return data.checkout_url;
}

export async function cancelSubscription() {
  const { data } = await api.post('/billing/cancel');
  return data;
}

/** Delete the account and all its data (cancels the subscription first). */
export async function deleteAccount() {
  await api.delete('/me');
}

/** "Botón de arrepentimiento": works without a session. Returns { code, message }. */
export async function requestWithdrawal({ email, name, details }) {
  const { data } = await api.post('/legal/arrepentimiento', { email, name, details });
  return data;
}

/** Solve a LaTeX string typed by the user (no OCR). */
export async function solveFromText(latexExpression, mode, operation = 'auto') {
  const form = new FormData();
  form.append('latex_expression', latexExpression);
  form.append('mode', mode);
  form.append('operation', operation);
  const { data } = await api.post('/solve-text', form);
  return data;
}

/** Upload an image or PDF for OCR + solving. */
export async function uploadProblem(file, mode, operation = 'auto') {
  const form = new FormData();
  form.append('file', file);
  form.append('mode', mode);
  form.append('operation', operation);
  const { data } = await api.post('/upload', form);
  return data;
}

export async function getHistory({ skip = 0, limit = 20, q = '' } = {}) {
  const { data } = await api.get('/history', { params: { skip, limit, q: q || undefined } });
  return data; // { items, total }
}

export async function getExercise(id) {
  const { data } = await api.get(`/history/${id}`);
  return data;
}

export async function deleteExercise(id) {
  await api.delete(`/history/${id}`);
}

export async function clearHistory() {
  await api.delete('/history');
}

export async function healthCheck() {
  const { data } = await api.get('/health', { timeout: 5000 });
  return data; // { status, version, ocr: { gemini, pix2tex } }
}
