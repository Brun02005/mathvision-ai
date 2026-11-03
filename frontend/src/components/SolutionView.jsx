import { useState } from 'react';
import { BookOpen, Check, Copy, Hash, LineChart, AlertCircle, ShieldCheck, Sparkles } from 'lucide-react';
import { isPlainText } from '../utils/format';
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
 * `result` is the API response ({extracted_latex, domain_classification, steps, final_result_latex,
 * graph_data, solved, verified, method, interpretation}).
 */
export default function SolutionView({ result, showSteps = true, showGraph = true }) {
  const solved = result.solved !== false;
  // The AI warning is also saved as the first step (so history keeps it); here the banner shows it
  const steps = (result.steps || []).filter((s) => !(result.method === 'ai' && s.startsWith('⚠ **Resuelto con IA')));

  return (
    <div className="space-y-5 animate-slide-up">
      <section className="pb-4 border-b border-white/10">
        <p className="label mb-2 flex items-center gap-1.5">
          <Hash size={11} className="text-secondary" /> Ejercicio
        </p>
        {isPlainText(result.extracted_latex) ? (
          <p className="bg-background/30 rounded-xl p-4 text-sm leading-relaxed text-gray-200 whitespace-pre-wrap break-words">
            {result.extracted_latex}
          </p>
        ) : (
          <div className="text-xl overflow-x-auto bg-background/30 rounded-xl p-4">
            <MathBlock latex={result.extracted_latex} />
          </div>
        )}
        {result.interpretation && (
          <div className="mt-2 bg-background/30 rounded-xl p-3">
            <p className="text-[11px] text-gray-500 mb-1">Lo interpretamos como</p>
            <div className="text-base overflow-x-auto"><MathBlock latex={result.interpretation} /></div>
          </div>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="inline-block bg-primary/20 border border-primary/30 text-primary px-3 py-1 rounded-full text-xs font-semibold">
            {result.domain_classification || 'Matemática'}
          </span>
          {result.method === 'interpreted' && (
            <span className="flex items-center gap-1 text-xs text-sky-300 bg-sky-400/10 border border-sky-400/20 px-3 py-1 rounded-full"
              title="La IA solo tradujo el ejercicio; el cálculo lo hizo el motor exacto.">
              <Sparkles size={11} /> Interpretado con IA
            </span>
          )}
        </div>
      </section>

      {solved && result.method === 'ai' && (
        <div role="note" className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-sm text-amber-200">
          <Sparkles size={14} className="shrink-0 mt-0.5" />
          <p><strong>Resuelto con IA.</strong> Este ejercicio no se pudo resolver con el motor de cálculo exacto. La respuesta la generó un modelo de lenguaje y puede tener errores: revisala.</p>
        </div>
      )}

      {!solved && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-sm text-amber-200">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <p>No pudimos resolver este ejercicio. El detalle de abajo explica por qué; revisá la expresión o probá con uno de los ejemplos.</p>
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
          <div className="flex items-center justify-between mb-2 gap-2">
            <p className="label">Resultado final</p>
            <div className="flex items-center gap-1">
              {result.verified && (
                <span title="Comprobado de forma independiente: sustituyendo en la ecuación, derivando la primitiva o evaluando numéricamente."
                  className="flex items-center gap-1 text-[11px] font-semibold text-green-400 bg-green-400/10 border border-green-400/20 px-2 py-0.5 rounded-full">
                  <ShieldCheck size={12} /> Verificado
                </span>
              )}
              <CopyButton text={result.final_result_latex} />
            </div>
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
