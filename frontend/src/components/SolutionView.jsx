import { useState } from 'react';
import { BookOpen, Check, Copy, Hash, LineChart, AlertCircle } from 'lucide-react';
import StepRenderer from './StepRenderer';
import MathPlot from './MathPlot';
import { MathBlock } from './Latex';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard not available (http, permissions): nothing to do
    }
  };
  return (
    <button onClick={copy} title="Copiar LaTeX" aria-label="Copiar LaTeX del resultado"
      className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
    </button>
  );
}

/**
 * Full solution: expression, topic, steps, final result and graph.
 * `result` is the API response ({extracted_latex, domain_classification, steps, final_result_latex, graph_data, solved}).
 */
export default function SolutionView({ result, showSteps = true, showGraph = true }) {
  const steps = result.steps || [];
  const solved = result.solved !== false;

  return (
    <div className="space-y-5 animate-slide-up">
      <section className="pb-4 border-b border-white/10">
        <p className="label mb-2 flex items-center gap-1.5">
          <Hash size={11} className="text-secondary" /> Expresión
        </p>
        <div className="text-xl overflow-x-auto bg-background/30 rounded-xl p-4">
          <MathBlock latex={result.extracted_latex} />
        </div>
        <span className="mt-2 inline-block bg-primary/20 border border-primary/30 text-primary px-3 py-1 rounded-full text-xs font-semibold">
          {result.domain_classification || 'Matemática'}
        </span>
      </section>

      {!solved && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-sm text-amber-200">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <p>No pudimos interpretar la expresión. Revisá la sintaxis LaTeX o probá con uno de los ejemplos.</p>
        </div>
      )}

      {showSteps && steps.length > 0 && (
        <section>
          <p className="label mb-3 flex items-center gap-1.5">
            <BookOpen size={11} className="text-primary" /> {solved ? 'Resolución paso a paso' : 'Detalle'}
          </p>
          <ol className="space-y-2">
            {steps.map((step, i) => (
              <li key={i} className="bg-surfaceLight/50 px-4 py-3 rounded-xl border border-white/5 text-sm leading-relaxed text-gray-200">
                <StepRenderer text={step} />
              </li>
            ))}
          </ol>
        </section>
      )}

      {solved && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <p className="label">Resultado final</p>
            <CopyButton text={result.final_result_latex} />
          </div>
          <div className="bg-gradient-to-br from-primary/20 to-secondary/20 border border-primary/30 p-6 rounded-2xl text-lg">
            <MathBlock latex={result.final_result_latex} />
          </div>
        </section>
      )}

      {showGraph && result.graph_data?.data && (
        <section className="animate-fade-in">
          <p className="label mb-2 flex items-center gap-1.5">
            <LineChart size={11} className="text-primary" /> Gráfica
          </p>
          <div className="bg-surfaceLight/40 rounded-xl border border-white/5 overflow-hidden p-2">
            <MathPlot data={result.graph_data.data} layout={result.graph_data.layout} />
          </div>
        </section>
      )}
    </div>
  );
}
