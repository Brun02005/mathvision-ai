import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload, FileText, Image as ImageIcon, Loader2, Calculator, AlertCircle,
  CheckCircle2, ChevronRight, Sigma, WifiOff, Camera, RotateCw,
} from 'lucide-react';
import SolutionView from '../components/SolutionView';
import { MathBlock } from '../components/Latex';
import MathInput, { TEMPLATES, hasEmptyBoxes } from '../components/MathInput';
import { Link } from 'react-router-dom';
import { solveFromText, uploadProblem, errorMessage, isLimitError } from '../services/api';
import { useSettings } from '../context/SettingsContext';
import useHealth from '../hooks/useHealth';
import { isPlainText } from '../utils/format';

// What to do with the expression. "auto" lets the server decide from its structure;
// the same expression can mean different things (x^2 - 4: factor it, or solve x^2 - 4 = 0).
const OPERATIONS = [
  ['auto', 'Automático'],
  ['solve', 'Resolver'],
  ['simplify', 'Simplificar'],
  ['factor', 'Factorizar'],
  ['expand', 'Desarrollar'],
  ['derivative', 'Derivar'],
  ['integral', 'Integrar'],
  ['taylor', 'Taylor'],
  ['partial_fractions', 'Fracciones parciales'],
  ['analyze', 'Análisis de función'],
  ['statistics', 'Estadística'],
];

const EXAMPLES = [
  { label: 'Problema en palabras', expr: 'Juan tiene el triple de la edad de su hijo. Dentro de 10 años tendrá el doble. ¿Qué edad tiene el hijo?' },
  { label: 'Escrito en texto', expr: 'x al cuadrado menos 4 igual a 0' },
  { label: 'Ecuación cuadrática', expr: 'x^2 - 5x + 6 = 0' },
  { label: 'Ec. logarítmica', expr: '\\log_{2}(x) + \\log_{2}(x-2) = 3' },
  { label: 'Valor absoluto', expr: '|2x - 3| = 5' },
  { label: 'Sistema de ecuaciones', expr: '2x + 3y = 6; x - y = 1' },
  { label: 'Inecuación', expr: '\\frac{x - 1}{x + 2} \\geq 0' },
  { label: 'Factorizar', expr: 'factorizar x^3 - 8' },
  { label: 'Simplificar', expr: '\\frac{x^2 - 1}{x^2 + 2x + 1}' },
  { label: 'Números complejos', expr: '(2 + 3i)(1 - i)' },
  { label: 'Límite', expr: '\\lim_{x \\to 0} \\frac{\\sin(x)}{x}' },
  { label: 'Derivada', expr: '\\frac{d}{dx}(x^2 \\sin(x))' },
  { label: 'Derivada implícita', expr: 'x^2 + y^2 = 25, \\frac{dy}{dx}' },
  { label: 'Integral por partes', expr: '\\int x e^{x}\\,dx' },
  { label: 'Integral doble', expr: '\\int_{0}^{1}\\int_{0}^{2} x y \\, dy \\, dx' },
  { label: 'Serie', expr: '\\sum_{n=1}^{\\infty} \\frac{1}{n^2}' },
  { label: 'Taylor', expr: '\\text{Taylor de } e^{x} \\text{ en } x = 0 \\text{ orden } 4' },
  { label: 'Ec. diferencial', expr: "y'' + y = 0, y(0) = 1, y'(0) = 0" },
  { label: 'Matriz', expr: '\\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}' },
  { label: 'Producto vectorial', expr: '(1, 2, 3) \\times (4, 5, 6)' },
  { label: 'Estadística', expr: 'media de 2, 4, 4, 4, 5, 5, 7, 9' },
  { label: 'Física (Newton)', expr: 'F = m a, m = 10 \\text{kg}, a = 5 \\text{m/s^2}' },
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
  const [operation, setOperation] = useState('auto');
  const [textInput, setTextInput] = useState('');
  const [editor, setEditor] = useState('math'); // math: visual editor · words: free text / word problems
  const mathRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingMsg, setProcessingMsg] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [limitHit, setLimitHit] = useState(false);

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

  const switchEditor = (next) => {
    setEditor(next);
    setError(null);
  };

  const handleProcess = async () => {
    setError(null);
    if (inputMode === 'text' && !textInput.trim()) return setError('Escribí una expresión matemática.');
    if (inputMode === 'text' && editor === 'math' && hasEmptyBoxes(textInput)) {
      return setError('Completá los cuadraditos vacíos del ejercicio antes de resolver.');
    }
    if (inputMode === 'image' && !file) return setError('Seleccioná una imagen o PDF.');

    setResult(null);
    setIsProcessing(true);
    try {
      if (inputMode === 'text') {
        setProcessingMsg('Calculando solución...');
        setResult(await solveFromText(textInput.trim(), mode, operation));
      } else {
        setProcessingMsg('Leyendo el ejercicio con OCR...');
        setResult(await uploadProblem(file, mode, operation));
      }
    } catch (err) {
      setError(errorMessage(err));
      setLimitHit(isLimitError(err));
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

      <div>
        <p id="operation-label" className="label mb-2">¿Qué querés hacer?</p>
        <div role="radiogroup" aria-labelledby="operation-label" className="flex flex-wrap gap-1.5">
          {OPERATIONS.map(([value, label]) => (
            <button key={value} role="radio" aria-checked={operation === value}
              onClick={() => setOperation(value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${operation === value
                ? 'bg-primary text-white border-primary'
                : 'bg-surfaceLight/60 text-gray-400 border-white/5 hover:text-white hover:border-white/20'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Input ── */}
        <div className="flex flex-col gap-3">
          {inputMode === 'text' ? (
            <div className="glass-panel flex flex-col p-5 gap-4">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <p className="label">Escribí el ejercicio</p>
                  <div className="flex bg-background/60 rounded-lg p-0.5 border border-white/5 text-xs" role="tablist" aria-label="Forma de escribir">
                    {[['math', 'Fórmula'], ['words', 'Texto']].map(([value, label]) => (
                      <button key={value} role="tab" aria-selected={editor === value} onClick={() => switchEditor(value)}
                        className={`px-3 py-1 rounded-md font-medium ${editor === value ? 'bg-primary text-white' : 'text-gray-400 hover:text-white'}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {editor === 'math' ? (
                  <>
                    <MathInput ref={mathRef} value={textInput} onChange={setTextInput} onSubmit={handleProcess}
                      label="Ejercicio" />
                    <div className="flex flex-wrap gap-1.5 mt-2" aria-label="Insertar">
                      {TEMPLATES.map(({ label, latex }) => (
                        <button key={label} type="button" onClick={() => mathRef.current?.insert(latex)}
                          className="px-2.5 py-1.5 rounded-lg bg-surfaceLight/70 border border-white/10 text-xs text-gray-200 hover:border-primary/50 hover:text-white">
                          {label}
                        </button>
                      ))}
                    </div>
                    <p className="text-[11px] text-gray-500 mt-2">
                      Escribí como en el cuaderno: <kbd>/</kbd> hace una fracción, <kbd>^</kbd> un exponente, y los botones arman
                      integrales, límites y derivadas. Completá los cuadraditos y apretá Enter.
                    </p>
                  </>
                ) : (
                  <>
                    <textarea
                      id="expr"
                      aria-label="Ejercicio en texto"
                      value={textInput}
                      onChange={(e) => setTextInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleProcess(); }}
                      placeholder={'Escribilo como lo dirías:\n  integral de arcotangente de x\n  x al cuadrado menos 4 igual a 0\n  Un tren recorre 120 km en 2 horas, ¿a qué velocidad va?\n\nCtrl+Enter para resolver'}
                      className="w-full h-36 bg-background/60 border border-white/10 rounded-xl p-4 text-white text-sm resize-none focus:outline-none focus:border-primary/60 transition-colors placeholder:text-gray-600"
                    />
                    <p className="text-[11px] text-gray-500 mt-1">También acepta LaTeX, por ejemplo <code>\int x^2 dx</code>.</p>
                  </>
                )}
              </div>

              {editor === 'words' && online && info && !info.ai && isPlainText(textInput) && (
                <p className="text-xs text-amber-300/80 bg-amber-400/5 border border-amber-400/10 rounded-xl px-4 py-3">
                  Los cálculos simples escritos en palabras se resuelven igual. Para enunciados de problemas hace falta el asistente de IA,
                  que se activa definiendo <code>GEMINI_API_KEY</code> en el backend.
                </p>
              )}

              {editor === 'words' && textInput.trim() && !isPlainText(textInput) && (
                <div className="bg-background/40 border border-white/5 rounded-xl p-4">
                  <p className="label !text-gray-500 mb-2">Vista previa</p>
                  <div className="text-lg text-center"><MathBlock latex={textInput} /></div>
                </div>
              )}

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
              {/* On phones: open the rear camera directly instead of the file picker */}
              <label className="sm:hidden flex items-center justify-center gap-2 py-3 rounded-xl bg-surfaceLight border border-white/10 text-sm font-medium text-white active:scale-[0.98] cursor-pointer">
                <Camera size={16} /> Sacar foto del ejercicio
                <input type="file" accept="image/*" capture="environment" className="sr-only"
                  onChange={(e) => {
                    const photo = e.target.files?.[0];
                    if (!photo) return;
                    if (photo.size > 10 * 1024 * 1024) return setError('La foto supera los 10 MB.');
                    onDrop([photo], []);
                  }} />
              </label>
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
              <div className="space-y-2">
                <p>{error}</p>
                {limitHit && (
                  <Link to="/cuenta" className="inline-block px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold hover:bg-primary-hover">
                    Ver plan Pro
                  </Link>
                )}
              </div>
            </div>
          )}

          <button onClick={handleProcess} disabled={!canSubmit}
            className={`w-full py-4 rounded-xl font-semibold text-base transition-all duration-300 flex items-center justify-center gap-2 ${canSubmit
              ? 'bg-primary hover:bg-primary-hover text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] hover:shadow-[0_0_30px_rgba(99,102,241,0.6)] active:scale-[0.98]'
              : 'bg-surfaceLight text-gray-500 cursor-not-allowed'}`}>
            {isProcessing
              ? <><Loader2 className="animate-spin" size={18} />{processingMsg}</>
              : <><ChevronRight size={18} />Resolver ejercicio{inputMode === 'text' && <span className="hidden sm:inline text-xs opacity-40 ml-1">Enter</span>}</>}
          </button>

          {/* Examples after the button: the editor, its errors and "Resolver" stay together */}
          {inputMode === 'text' && (
            <div className="glass-panel p-5">
              <p className="label !text-gray-500 mb-2">Ejemplos para probar</p>
              <div className="grid grid-cols-2 gap-2">
                {EXAMPLES.map(({ label, expr }) => (
                  <button key={label} onClick={() => {
                    // Word problems and commands go to the text box; formulas to the visual editor
                    setEditor(isPlainText(expr) || /^[a-záéíóú]/i.test(expr) ? 'words' : 'math');
                    setTextInput(expr); setOperation('auto'); setError(null);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                    className="text-left px-3 py-2 bg-surfaceLight/60 border border-white/5 rounded-lg hover:border-primary/40 hover:bg-primary/5 transition-all min-w-0">
                    <span className="text-primary text-xs font-semibold block mb-0.5">{label}</span>
                    <span className="text-gray-500 text-xs font-mono truncate block">{expr}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
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
