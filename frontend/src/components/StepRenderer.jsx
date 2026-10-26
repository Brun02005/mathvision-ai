/**
 * StepRenderer — renderiza un paso que mezcla texto en español y fórmulas LaTeX.
 *
 *   $$...$$ → bloque matemático centrado
 *   $...$   → fórmula inline
 *   **...** → negrita
 *   `...`   → código
 *   texto normal → React lo escapa, nunca pasa por KaTeX
 */
import { renderLatex } from './Latex';

const TOKEN = /(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$|\*\*[^*]+\*\*|`[^`]+`)/g;

function parseSegments(text) {
  const segments = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    if (match.index > last) segments.push({ type: 'text', content: text.slice(last, match.index) });
    const raw = match[0];
    if (raw.startsWith('$$')) segments.push({ type: 'display', content: raw.slice(2, -2) });
    else if (raw.startsWith('$')) segments.push({ type: 'inline', content: raw.slice(1, -1) });
    else if (raw.startsWith('**')) segments.push({ type: 'bold', content: raw.slice(2, -2) });
    else segments.push({ type: 'code', content: raw.slice(1, -1) });
    last = match.index + raw.length;
  }
  if (last < text.length) segments.push({ type: 'text', content: text.slice(last) });
  return segments;
}

function Segment({ seg }) {
  switch (seg.type) {
    case 'display':
      return <span className="block my-2 overflow-x-auto text-center" dangerouslySetInnerHTML={{ __html: renderLatex(seg.content, true) }} />;
    case 'inline':
      return <span dangerouslySetInnerHTML={{ __html: renderLatex(seg.content, false) }} />;
    case 'bold':
      // Bold text may itself contain inline math: **Solución:** $x = 2$
      return <strong className="text-white">{parseSegments(seg.content).map((s, i) => <Segment key={i} seg={s} />)}</strong>;
    case 'code':
      return <code className="px-1.5 py-0.5 rounded bg-black/30 text-xs font-mono text-gray-300 break-all">{seg.content}</code>;
    default:
      return <span>{seg.content}</span>;
  }
}

export default function StepRenderer({ text = '', className = '' }) {
  return (
    <span className={className}>
      {parseSegments(text).map((seg, i) => <Segment key={i} seg={seg} />)}
    </span>
  );
}
