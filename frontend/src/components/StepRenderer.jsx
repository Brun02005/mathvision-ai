/**
 * StepRenderer — renderiza un paso que mezcla texto español y fórmulas LaTeX.
 *
 * Soporta:
 *   $$...$$ → bloque matemático centrado
 *   $...$   → fórmula inline
 *   **...**  → negrita
 *   texto normal → párrafo sin tocar KaTeX
 */
import katex from 'katex';
import 'katex/dist/katex.min.css';

function renderLatex(latex, displayMode) {
  try {
    return katex.renderToString(latex.trim(), {
      displayMode,
      throwOnError: false,
      strict: false,
    });
  } catch {
    return `<code>${latex}</code>`;
  }
}

function parseSegments(text) {
  const segments = [];
  // Match $$...$$ (display), $...$ (inline), **...** (bold)
  const re = /(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$|\*\*[^*]+\*\*)/g;
  let last = 0;
  let match;

  while ((match = re.exec(text)) !== null) {
    // plain text before match
    if (match.index > last) {
      segments.push({ type: 'text', content: text.slice(last, match.index) });
    }
    const raw = match[0];
    if (raw.startsWith('$$')) {
      segments.push({ type: 'display', content: raw.slice(2, -2) });
    } else if (raw.startsWith('$')) {
      segments.push({ type: 'inline', content: raw.slice(1, -1) });
    } else if (raw.startsWith('**')) {
      segments.push({ type: 'bold', content: raw.slice(2, -2) });
    }
    last = match.index + raw.length;
  }

  if (last < text.length) {
    segments.push({ type: 'text', content: text.slice(last) });
  }

  return segments;
}

export default function StepRenderer({ text = '', className = '' }) {
  const segments = parseSegments(text);

  return (
    <span className={className}>
      {segments.map((seg, i) => {
        if (seg.type === 'display') {
          return (
            <span
              key={i}
              className="block my-2 overflow-x-auto text-center"
              dangerouslySetInnerHTML={{ __html: renderLatex(seg.content, true) }}
            />
          );
        }
        if (seg.type === 'inline') {
          return (
            <span
              key={i}
              dangerouslySetInnerHTML={{ __html: renderLatex(seg.content, false) }}
            />
          );
        }
        if (seg.type === 'bold') {
          return <strong key={i}>{seg.content}</strong>;
        }
        // plain text — never goes through KaTeX
        return <span key={i}>{seg.content}</span>;
      })}
    </span>
  );
}
