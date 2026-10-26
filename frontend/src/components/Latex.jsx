/* eslint-disable react-refresh/only-export-components */
import katex from 'katex';

const escapeHtml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

/**
 * LaTeX → HTML with KaTeX. Input can come from OCR or the user, so `trust`
 * stays off (no \href / \url / raw HTML) and the fallback is escaped.
 */
export function renderLatex(latex, displayMode = false) {
  try {
    return katex.renderToString(latex.trim(), {
      displayMode,
      throwOnError: false,
      strict: false,
      trust: false,
    });
  } catch {
    return `<code>${escapeHtml(latex)}</code>`;
  }
}

/** A pure LaTeX expression rendered as a centered display block. */
export function MathBlock({ latex, className = '' }) {
  if (!latex) return null;
  return (
    <div
      className={`overflow-x-auto py-1 ${className}`}
      dangerouslySetInnerHTML={{ __html: renderLatex(latex, true) }}
    />
  );
}
