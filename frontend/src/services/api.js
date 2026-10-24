import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 60000, // 60s for OCR processing
});

/**
 * Solve from a LaTeX string typed directly by the user (fast, no OCR).
 */
export const solveFromText = async (latexExpression, mode) => {
  const formData = new FormData();
  formData.append('latex_expression', latexExpression);
  formData.append('mode', mode);

  const response = await api.post('/solve-text', formData);
  return response.data;
};

/**
 * Upload an image or PDF for OCR + solving.
 */
export const uploadProblem = async (file, mode) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);

  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

/**
 * Get solution history.
 */
export const getHistory = async () => {
  const response = await api.get('/history');
  return response.data;
};

/**
 * Check if the backend is reachable.
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};
