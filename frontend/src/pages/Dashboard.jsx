import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload, FileText, Image as ImageIcon, Loader2,
  Calculator, BookOpen, AlertCircle, CheckCircle2,
  ChevronRight, Sigma, WifiOff, Camera, Hash
} from 'lucide-react';
import 'katex/dist/katex.min.css';
import katex from 'katex';
import StepRenderer from '../components/StepRenderer';
import MathPlot from '../components/MathPlot';
import { solveFromText, uploadProblem, healthCheck } from '../services/api';

/** Render a pure LaTeX expression as display block */
function MathBlock({ latex }) {
  if (!latex) return null;
  let html = '';
  try {
    html = katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false, strict: false });
  } catch {
    html = `<code>${latex}</code>`;
  }
  return (
    <div className="overflow-x-auto py-1" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export default function Dashboard({ mode }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [textInput, setTextInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [backendOnline, setBackendOnline] = useState(null);
  const [inputMode, setInputMode] = useState('text');
  const [processingMsg, setProcessingMsg] = useState('');

  useEffect(() => {
    healthCheck().then(() => setBackendOnline(true)).catch(() => setBackendOnline(false));
  }, []);

  const onDrop = useCallback(accepted => {
    const sel = accepted[0];
    if (sel) { setFile(sel); setPreview(URL.createObjectURL(sel)); setError(null); }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.bmp'], 'application/pdf': ['.pdf'] },
    maxFiles: 1,
  });

  const handleProcess = async () => {
    setError(null); setResult(null); setIsProcessing(true);
    try {
      let data;
      if (inputMode === 'text') {
        if (!textInput.trim()) { setError('Escribí una expresión matemática.'); setIsProcessing(false); return; }
        setProcessingMsg('Calculando solución...');
        data = await solveFromText(textInput.trim(), mode);
      } else {
        if (!file) { setError('Seleccioná una imagen o PDF.'); setIsProcessing(false); return; }
        setProcessingMsg('Analizando imagen con OCR...');
        data = await uploadProblem(file, mode);
      }

      let steps = [];
      try { steps = JSON.parse(data.solution_steps_json || '[]'); } catch { steps = []; }

      let graphData = null;
      try { if (data.graph_data_json) graphData = JSON.parse(data.graph_data_json); } catch { }

      setResult({
        expression: data.extracted_latex || '',
        domain: data.domain_classification || 'Matemáticas',
        steps,
        final: data.final_result_latex || '',
        graphData,
      });
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.message?.includes('Network')) {
        setError('No se puede conectar con el servidor. Asegurate de que el backend esté corriendo.'); setBackendOnline(false);
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setError('Tiempo de espera agotado. Si usás imagen, el OCR puede tardar la primera vez. Intentá de nuevo o usá el modo texto.');
      } else {
        setError(err.response?.data?.detail || err.message || 'Error inesperado.');
      }
    } finally { setIsProcessing(false); }
  };

  const examples = [
    { label: 'Integral definida',   expr: '\\int_{0}^{\\pi} \\sin(x)\\,dx' },
    { label: 'Ecuación cuadrática', expr: 'x^2 - 5x + 6 = 0' },
    { label: 'Integral indefinida', expr: '\\int x^3 + 2x\\,dx' },
    { label: 'Derivada',            expr: '\\frac{d}{dx}(x^3 - 4x + 1)' },
    { label: 'Suma simple',         expr: '2 + 2' },
    { label: 'Fracción',            expr: '\\frac{3}{4} + \\frac{1}{8}' },
  ];

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-5 h-full">

      {/* Header */}
      <header className="flex flex-wrap justify-between items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Resolver Problema</h2>
          <p className="text-gray-400 text-sm mt-0.5">Desde sumas simples hasta integrales complejas — todo en español.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {backendOnline === null  && <span className="flex items-center gap-1 text-gray-400 bg-surface px-3 py-1.5 rounded-full border border-white/5"><Loader2 size={10} className="animate-spin"/>Verificando...</span>}
          {backendOnline === true  && <span className="flex items-center gap-1 text-green-400 bg-green-400/10 px-3 py-1.5 rounded-full border border-green-400/20"><CheckCircle2 size={10}/>Servidor conectado</span>}
          {backendOnline === false && <span className="flex items-center gap-1 text-red-400 bg-red-400/10 px-3 py-1.5 rounded-full border border-red-400/20"><WifiOff size={10}/>Servidor offline</span>}
          <span className="px-3 py-1.5 bg-surface border border-white/10 rounded-full font-medium text-primary">
            {mode === 'Teacher' ? '📖 Modo Profesor' : '🎓 Modo Examen'}
          </span>
        </div>
      </header>

      {/* Offline banner */}
      {backendOnline === false && (
        <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300">
          <AlertCircle size={15} className="shrink-0 mt-0.5"/>
          <div>
            <p className="font-semibold mb-1">Backend no disponible</p>
            <code className="block bg-black/30 px-3 py-1.5 rounded text-xs font-mono text-red-200">
              cd backend && .\venv\Scripts\Activate.ps1 && uvicorn main:app --reload
            </code>
          </div>
        </div>
      )}

      {/* Input tabs */}
      <div className="flex gap-1 bg-surfaceLight/60 p-1 rounded-xl w-fit border border-white/5">
        {[['text','image'],['Escribir expresión','Subir imagen/PDF']].reduce((_,__)=>null) || null}
        <button onClick={()=>{setInputMode('text');setError(null);}}
          className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium transition-all ${inputMode==='text'?'bg-primary text-white shadow':'text-gray-400 hover:text-white'}`}>
          <Sigma size={13}/> Escribir expresión
        </button>
        <button onClick={()=>{setInputMode('image');setError(null);}}
          className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium transition-all ${inputMode==='image'?'bg-primary text-white shadow':'text-gray-400 hover:text-white'}`}>
          <Camera size={13}/> Subir imagen / PDF
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 flex-1 min-h-0">

        {/* ── LEFT: Input ── */}
        <div className="flex flex-col gap-3">

          {inputMode === 'text' ? (
            <div className="glass-panel flex-1 flex flex-col p-5 gap-4">
              <div>
                <label className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2 block">
                  Expresión Matemática
                </label>
                <textarea
                  value={textInput}
                  onChange={e=>setTextInput(e.target.value)}
                  onKeyDown={e=>{ if(e.key==='Enter'&&e.ctrlKey) handleProcess(); }}
                  placeholder={"Podés escribir:\n  2 + 2\n  x^2 - 5x + 6 = 0\n  \\int x^2 dx\n  \\frac{d}{dx}(x^3)\n\nCtrl+Enter para resolver"}
                  className="w-full h-36 bg-background/60 border border-white/10 rounded-xl p-4 text-white text-sm font-mono resize-none focus:outline-none focus:border-primary/60 transition-colors placeholder:text-gray-600"
                />
              </div>

              {/* Live preview */}
              {textInput.trim() && (
                <div className="bg-background/40 border border-white/5 rounded-xl p-4 min-h-[60px]">
                  <p className="text-xs text-gray-500 uppercase tracking-widest mb-2">Vista previa</p>
                  <div className="text-lg text-center overflow-x-auto">
                    <MathBlock latex={textInput} />
                  </div>
                </div>
              )}

              {/* Quick examples */}
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-widest mb-2">Ejemplos rápidos</p>
                <div className="grid grid-cols-2 gap-2">
                  {examples.map(({label,expr})=>(
                    <button key={label} onClick={()=>{setTextInput(expr);setError(null);}}
                      className="text-left px-3 py-2 bg-surfaceLight/60 border border-white/5 rounded-lg hover:border-primary/40 hover:bg-primary/5 transition-all">
                      <span className="text-primary text-xs font-semibold block mb-0.5">{label}</span>
                      <span className="text-gray-500 text-xs font-mono truncate block">{expr.substring(0,28)}…</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

          ) : (
            <>
              <div {...getRootProps()}
                className={`glass-panel flex-1 flex flex-col items-center justify-center p-6 border-2 border-dashed cursor-pointer min-h-[280px] transition-all duration-300
                  ${isDragActive?'border-primary bg-primary/5':'border-white/10 hover:border-white/25'}`}>
                <input {...getInputProps()}/>
                {preview ? (
                  <div className="w-full h-full flex flex-col items-center justify-center relative group">
                    {file?.type?.includes('pdf')
                      ? <FileText className="w-20 h-20 text-primary mb-3"/>
                      : <img src={preview} alt="Preview" className="max-h-[240px] object-contain rounded-lg shadow-lg mb-3"/>}
                    <p className="text-sm text-gray-400">{file.name}</p>
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-2xl">
                      <span className="bg-surface px-4 py-2 rounded-full text-sm border border-white/10">Cambiar archivo</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center flex flex-col items-center gap-4">
                    <div className="w-14 h-14 bg-surfaceLight rounded-full flex items-center justify-center">
                      <Upload className="w-6 h-6 text-gray-400"/>
                    </div>
                    <div>
                      <p className="font-semibold mb-1 text-sm">Arrastrá el ejercicio aquí</p>
                      <p className="text-gray-500 text-xs max-w-[220px] mx-auto">PNG, JPG, PDF — el OCR extrae la fórmula automáticamente</p>
                    </div>
                    <div className="flex gap-2 text-xs text-gray-500">
                      <span className="bg-surface px-3 py-1 rounded-full flex items-center gap-1"><ImageIcon size={10}/> Imagen</span>
                      <span className="bg-surface px-3 py-1 rounded-full flex items-center gap-1"><FileText size={10}/> PDF</span>
                    </div>
                  </div>
                )}
              </div>
              <div className="text-xs text-amber-400/70 bg-amber-400/5 border border-amber-400/10 rounded-xl px-4 py-3 flex items-start gap-2">
                <AlertCircle size={12} className="shrink-0 mt-0.5"/>
                <span>El modelo OCR puede tardar 1-2 min la primera vez (descarga del modelo). Las siguientes son rápidas.</span>
              </div>
            </>
          )}

          {error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300 animate-fade-in">
              <AlertCircle size={14} className="shrink-0 mt-0.5"/>
              <p>{error}</p>
            </div>
          )}

          <button onClick={handleProcess} disabled={isProcessing||backendOnline===false}
            className={`w-full py-4 rounded-xl font-semibold text-base transition-all duration-300 flex items-center justify-center gap-2
              ${(!isProcessing&&backendOnline!==false)
                ?'bg-primary hover:bg-primary-hover text-white shadow-[0_0_20px_rgba(99,102,241,0.4)] hover:shadow-[0_0_30px_rgba(99,102,241,0.6)] active:scale-[0.98]'
                :'bg-surfaceLight text-gray-500 cursor-not-allowed'}`}>
            {isProcessing
              ? <><Loader2 className="animate-spin" size={18}/>{processingMsg}</>
              : <><ChevronRight size={18}/>Resolver Ejercicio{inputMode==='text'&&<span className="text-xs opacity-40 ml-1">Ctrl+Enter</span>}</>}
          </button>
        </div>

        {/* ── RIGHT: Results ── */}
        <div className="min-h-[500px]">
          <div className="glass-panel h-full flex flex-col overflow-hidden">

            {!result && !isProcessing ? (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-600 p-8 text-center gap-3">
                <Calculator className="w-12 h-12 opacity-20"/>
                <p className="text-sm opacity-40">La solución aparecerá aquí</p>
              </div>

            ) : isProcessing ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-5 p-8">
                <div className="relative w-16 h-16">
                  <div className="absolute inset-0 rounded-full border-4 border-primary/20 border-t-primary animate-spin"/>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Calculator size={18} className="text-primary"/>
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-white font-medium mb-1">Procesando…</p>
                  <p className="text-gray-400 text-xs max-w-xs">{processingMsg}</p>
                </div>
              </div>

            ) : result && (
              <div className="flex-1 overflow-y-auto p-5 space-y-5 animate-slide-up">

                {/* Expression */}
                <div className="pb-4 border-b border-white/10">
                  <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2 flex items-center gap-1.5">
                    <Hash size={11} className="text-secondary"/> Expresión
                  </p>
                  <div className="text-xl overflow-x-auto bg-background/30 rounded-xl p-4">
                    <MathBlock latex={result.expression}/>
                  </div>
                  <span className="mt-2 inline-block bg-primary/20 border border-primary/30 text-primary px-3 py-1 rounded-full text-xs font-semibold">
                    {result.domain}
                  </span>
                </div>

                {/* Steps */}
                {mode === 'Teacher' && result.steps?.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-3 flex items-center gap-1.5">
                      <BookOpen size={11} className="text-primary"/> Resolución paso a paso
                    </p>
                    <div className="space-y-2">
                      {result.steps.map((step, i) => (
                        <div key={i}
                          className="bg-surfaceLight/50 px-4 py-3 rounded-xl border border-white/5 text-sm leading-relaxed hover:bg-surfaceLight/80 transition-colors">
                          <StepRenderer text={step}/>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Final result */}
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">Resultado Final</p>
                  <div className="bg-gradient-to-br from-primary/20 to-secondary/20 border border-primary/30 p-6 rounded-2xl">
                    <MathBlock latex={result.final}/>
                  </div>
                </div>

                {/* Graph — only when present */}
                {result.graphData?.data && (
                  <div className="animate-fade-in">
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">Gráfica</p>
                    <div className="bg-surfaceLight/40 rounded-xl border border-white/5 overflow-hidden p-2">
                      <MathPlot data={result.graphData.data} layout={result.graphData.layout}/>
                    </div>
                  </div>
                )}

              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
