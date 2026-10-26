import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload, FileText, Image as ImageIcon, Loader2, Calculator, AlertCircle,
  CheckCircle2, ChevronRight, Sigma, WifiOff, Camera, RotateCw,
} from 'lucide-react';
import SolutionView from '../components/SolutionView';
import { MathBlock } from '../components/Latex';
import { solveFromText, uploadProblem, errorMessage } from '../services/api';
import { useSettings } from '../context/SettingsContext';
import useHealth from '../hooks/useHealth';

const EXAMPLES = [
  { label: 'Integral definida', expr: '\\int_{0}^{\\pi} \\sin(x)\\,dx' },
  { label: 'Fracciones parciales', expr: '\\int \\frac{x^5 + x^4 - 8}{x^3 - 4x}\\,dx' },
  { label: 'Por partes', expr: '\\int x e^{x}\\,dx' },
  { label: 'Derivada', expr: '\\frac{d}{dx}(x^2 \\sin(x))' },
  { label: 'Límite', expr: '\\lim_{x \\to 0} \\frac{\\sin(x)}{x}' },
  { label: 'Ecuación cuadrática', expr: 'x^2 - 5x + 6 = 0' },
  { label: 'Sistema de ecuaciones', expr: '2x + 3y = 6; x - y = 1' },
  { label: 'Análisis de función', expr: 'f(x) = x^3 - 3x' },
  { label: 'Inecuación', expr: 'x^2 - 4 > 0' },
  { label: 'Serie', expr: '\\sum_{n=1}^{\\infty} \\frac{1}{n^2}' },
  { label: 'Ec. diferencial', expr: "y'' + y = 0, y(0) = 1, y'(0) = 0" },
  { label: 'Matriz', expr: '\\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}' },
  { label: 'Física (Newton)', expr: 'F = m a, m = 10 \\text{kg}, a = 5 \\text{m/s^2}' },
  { label: 'Fracción', expr: '\\frac{3}{4} + \\frac{1}{8}' },
];

function StatusBadge({ online, onRetry }) {
  if (online === null) {
    return <span className="flex items-center gap-1 text-gray-400 bg-surface px-3 py-1.5 rounded-full border border-white/5"><Loader2 size={10} className="animate-spin" />Verificando...</span>;
  }
  if (online) {
    return <span className="flex items-center gap-1 text-green-400 bg-green-400/10 px-3 py-1.5 rounded-full border border-green-400/20"><CheckCircle2 size={10} />Servidor conectado</span>;
  }
  return (
    <button onClick={onRetry} className="flex items-center gap-1 text-red-400 bg-red-400/10 px-3 py-1.5 rounded-full border border-red-400/20 hover:bg-red-400/20">
      <WifiOff size={10} />Servidor offline <RotateCw size={10} />
    </button>
  );
}

export default function Dashboard() {
  const { settings } = useSettings();
  const { mode, showGraphs } = settings;
  const { online, info, refresh } = useHealth();

  const [inputMode, setInputMode] = useState('text');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingMsg, setProcessingMsg] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Release the object URL of the previous preview
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const onDrop = useCallback((accepted, rejected) => {
    if (rejected?.length) {
      setError('Formato no soportado o archivo demasiado grande (máx. 10 MB).');
      return;
    }
    const sel = accepted[0];
    if (sel) {
      setFile(sel);
      setPreview(URL.createObjectURL(sel));
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.bmp'], 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
  });

  const handleProcess = async () => {
    setError(null);
    if (inputMode === 'text' && !textInput.trim()) return setError('Escribí una expresión matemática.');
    if (inputMode === 'image' && !file) return setError('Seleccioná una imagen o PDF.');

    setResult(null);
    setIsProcessing(true);
    try {
      if (inputMode === 'text') {
        setProcessingMsg('Calculando solución...');
        setResult(await solveFromText(textInput.trim(), mode));
      } else {
        setProcessingMsg('Leyendo el ejercicio con OCR...');
        setResult(await uploadProblem(file, mode));
      }
    } catch (err) {
      setError(errorMessage(err));
      if (err.code === 'ERR_NETWORK') refresh();
    } finally {
      setIsProcessing(false);
    }
  };

  const ocrReady = info?.ocr && (info.ocr.gemini || info.ocr.pix2tex);
  const canSubmit = !isProcessing && online !== false;

  return (
    <div className="max-w-6xl mx-auto flex flex-col gap-5">
      <header className="flex flex-wrap justify-between items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Resolver Problema</h1>
          <p className="text-gray-400 text-sm mt-0.5">Desde sumas simples hasta ecuaciones diferenciales — todo en español.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <StatusBadge online={online} onRetry={refresh} />
          <span className="px-3 py-1.5 bg-surface border border-white/10 rounded-full font-medium text-primary">
            {mode === 'Teacher' ? '📖 Modo Profesor' : '🎓 Modo Examen'}
          </span>
        </div>
      </header>

      {online === false && (
        <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300">
          <AlertCircle size={15} className="shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="font-semibold mb-1">Backend no disponible</p>
            <code className="block bg-black/30 px-3 py-1.5 rounded text-xs font-mono text-red-200 overflow-x-auto whitespace-nowrap">
              cd backend &amp;&amp; venv\Scripts\activate &amp;&amp; uvicorn main:app --reload
            </code>
          </div>
        </div>
      )}

      <div className="flex gap-1 bg-surfaceLight/60 p-1 rounded-xl w-fit border border-white/5" role="tablist">
        {[['text', 'Escribir expresión', Sigma], ['image', 'Subir imagen / PDF', Camera]].map(([value, label, Icon]) => (
          <button key={value} role="tab" aria-selected={inputMode === value}
            onClick={() => { setInputMode(value); setError(null); }}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium transition-all ${inputMode === value ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white'}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Input ── */}
        <div className="flex flex-col gap-3">
          {inputMode === 'text' ? (
            <div className="glass-panel flex flex-col p-5 gap-4">
              <div>
                <label htmlFor="expr" className="label mb-2 block">Expresión matemática (LaTeX)</label>
                <textarea
                  id="expr"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleProcess(); }}
                  placeholder={'Podés escribir:\n  x^2 - 5x + 6 = 0\n  \\int x^2 dx\n  \\lim_{x \\to 0} \\frac{\\sin x}{x}\n\nCtrl+Enter para resolver'}
                  className="w-full h-36 bg-background/60 border border-white/10 rounded-xl p-4 text-white text-sm font-mono resize-none focus:outline-none focus:border-primary/60 transition-colors placeholder:text-gray-600"
                />
              </div>

              {textInput.trim() && (
                <div className="bg-background/40 border border-white/5 rounded-xl p-4">
                  <p className="label !text-gray-500 mb-2">Vista previa</p>
                  <div className="text-lg text-center"><MathBlock latex={textInput} /></div>
                </div>
              )}

              <div>
                <p className="label !text-gray-500 mb-2">Ejemplos rápidos</p>
                <div className="grid grid-cols-2 gap-2">
                  {EXAMPLES.map(({ label, expr }) => (
                    <button key={label} onClick={() => { setTextInput(expr); setError(null); }}
                      className="text-left px-3 py-2 bg-surfaceLight/60 border border-white/5 rounded-lg hover:border-primary/40 hover:bg-primary/5 transition-all min-w-0">
                      <span className="text-primary text-xs font-semibold block mb-0.5">{label}</span>
                      <span className="text-gray-500 text-xs font-mono truncate block">{expr}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              <div {...getRootProps()}
                className={`glass-panel flex flex-col items-center justify-center p-6 border-2 border-dashed cursor-pointer min-h-[280px] transition-all duration-300 ${isDragActive ? 'border-primary bg-primary/5' : 'border-white/10 hover:border-white/25'}`}>
                <input {...getInputProps()} />
                {preview ? (
                  <div className="w-full h-full flex flex-col items-center justify-center relative group">
                    {file?.type?.includes('pdf')
                      ? <FileText className="w-20 h-20 text-primary mb-3" />
                      : <img src={preview} alt="Vista previa del ejercicio" className="max-h-[240px] object-contain rounded-lg shadow-lg mb-3" />}
                    <p className="text-sm text-gray-400 break-all">{file.name}</p>
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-2xl">
                      <span className="bg-surface px-4 py-2 rounded-full text-sm border border-white/10">Cambiar archivo</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center flex flex-col items-center gap-4">
                    <div className="w-14 h-14 bg-surfaceLight rounded-full flex items-center justify-center">
                      <Upload className="w-6 h-6 text-gray-400" />
                    </div>
                    <div>
                      <p className="font-semibold mb-1 text-sm">Arrastrá el ejercicio aquí o tocá para elegirlo</p>
                      <p className="text-gray-500 text-xs max-w-[240px] mx-auto">PNG, JPG, WEBP o PDF (máx. 10 MB). La IA extrae la fórmula automáticamente.</p>
                    </div>
                    <div className="flex gap-2 text-xs text-gray-500">
                      <span className="bg-surface px-3 py-1 rounded-full flex items-center gap-1"><ImageIcon size={10} /> Imagen</span>
                      <span className="bg-surface px-3 py-1 rounded-full flex items-center gap-1"><FileText size={10} /> PDF</span>
                    </div>
                  </div>
                )}
              </div>
              {online && !ocrReady && (
                <div className="text-xs text-amber-300/80 bg-amber-400/5 border border-amber-400/10 rounded-xl px-4 py-3 flex items-start gap-2">
                  <AlertCircle size={12} className="shrink-0 mt-0.5" />
                  <span>El servidor no tiene OCR configurado. Definí <code>GEMINI_API_KEY</code> en el backend (o instalá pix2tex) para leer imágenes.</span>
                </div>
              )}
            </>
          )}

          {error && (
            <div role="alert" className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300 animate-fade-in">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <p>{error}</p>
            </div>
          )}

          <button onClick={handleProcess} disabled={!canSubmit}
            className={`w-full py-4 rounded-xl font-semibold text-base transition-all duration-300 flex items-center justify-center gap-2 ${canSubmit
              ? 'bg-primary hover:bg-primary-hover text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] hover:shadow-[0_0_30px_rgba(99,102,241,0.6)] active:scale-[0.98]'
              : 'bg-surfaceLight text-gray-500 cursor-not-allowed'}`}>
            {isProcessing
              ? <><Loader2 className="animate-spin" size={18} />{processingMsg}</>
              : <><ChevronRight size={18} />Resolver ejercicio{inputMode === 'text' && <span className="hidden sm:inline text-xs opacity-40 ml-1">Ctrl+Enter</span>}</>}
          </button>
        </div>

        {/* ── Result ── */}
        <div className="glass-panel min-h-[420px] flex flex-col overflow-hidden" aria-live="polite">
          {isProcessing ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-5 p-8">
              <div className="relative w-16 h-16">
                <div className="absolute inset-0 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center"><Calculator size={18} className="text-primary" /></div>
              </div>
              <div className="text-center">
                <p className="text-white font-medium mb-1">Procesando…</p>
                <p className="text-gray-400 text-xs max-w-xs">{processingMsg}</p>
              </div>
            </div>
          ) : result ? (
            <div className="flex-1 overflow-y-auto p-5">
              <SolutionView result={result} showSteps={mode === 'Teacher'} showGraph={showGraphs} />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-600 p-8 text-center gap-3">
              <Calculator className="w-12 h-12 opacity-20" />
              <p className="text-sm opacity-40">La solución aparecerá aquí</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
