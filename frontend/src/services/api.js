import axios from 'axios';

const api = axios.create({
  // Same-origin /api by default (Vite proxy in dev, nginx in Docker). Override with VITE_API_URL.
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 90000, // OCR + symbolic solving can take a while on the first request
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
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('. ');
  return err.message || 'Error inesperado.';
}

/** Solve a LaTeX string typed by the user (no OCR). */
export async function solveFromText(latexExpression, mode) {
  const form = new FormData();
  form.append('latex_expression', latexExpression);
  form.append('mode', mode);
  const { data } = await api.post('/solve-text', form);
  return data;
}

/** Upload an image or PDF for OCR + solving. */
export async function uploadProblem(file, mode) {
  const form = new FormData();
  form.append('file', file);
  form.append('mode', mode);
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
