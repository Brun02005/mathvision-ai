/**
 * MathDisplay — renderiza LaTeX con KaTeX directamente.
 * Compatible con React 19 sin depender de react-latex-next.
 */
import katex from 'katex';
import 'katex/dist/katex.min.css';

/**
 * Renderiza una expresión LaTeX.
 * @param {string} latex  - Expresión LaTeX (sin $ delimitadores)
 * @param {boolean} block - true = centrado en bloque, false = inline
 */
export default function MathDisplay({ latex = '', block = false, className = '' }) {
  if (!latex) return null;

  // Limpia delimitadores $, $$, \( \), \[ \] si el caller los incluye
  let clean = latex
    .replace(/^\$\$|\$\$$/g, '')
    .replace(/^\$|\$$/g, '')
    .replace(/^\\\[|\\\]$/g, '')
    .replace(/^\\\(|\\\)$/g, '')
    .trim();

  let html = '';
  try {
    html = katex.renderToString(clean, {
      displayMode: block,
      throwOnError: false,
      trust: true,
      strict: false,
      macros: {
        '\\RR': '\\mathbb{R}',
        '\\NN': '\\mathbb{N}',
      },
    });
  } catch {
    html = `<code style="color:#f87171">${clean}</code>`;
  }

  return (
    <span
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
      style={block ? { display: 'block', textAlign: 'center' } : {}}
    />
  );
}
