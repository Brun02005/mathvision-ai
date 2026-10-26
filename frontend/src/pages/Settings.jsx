import { useState } from 'react';
import { BookOpen, GraduationCap, LineChart, Server, RotateCw, Trash2, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import useHealth from '../hooks/useHealth';
import { clearHistory, errorMessage } from '../services/api';

function Section({ icon: Icon, title, description, children }) {
  return (
    <section className="glass-panel p-5 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex items-start gap-3 flex-1">
        <div className="w-9 h-9 rounded-lg bg-primary/15 text-primary flex items-center justify-center shrink-0"><Icon size={18} /></div>
        <div>
          <h2 className="font-semibold text-white">{title}</h2>
          <p className="text-sm text-gray-400">{description}</p>
        </div>
      </div>
      <div className="shrink-0">{children}</div>
    </section>
  );
}

function Toggle({ checked, onChange, label }) {
  return (
    <button role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={`w-12 h-7 rounded-full p-1 transition-colors ${checked ? 'bg-primary' : 'bg-surfaceLight border border-white/10'}`}>
      <span className={`block w-5 h-5 rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : ''}`} />
    </button>
  );
}

function Provider({ name, enabled }) {
  return (
    <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${enabled ? 'text-green-400 border-green-400/20 bg-green-400/10' : 'text-gray-500 border-white/10'}`}>
      {enabled ? <CheckCircle2 size={12} /> : <XCircle size={12} />} {name}
    </span>
  );
}

export default function Settings() {
  const { settings, update, reset } = useSettings();
  const { online, info, refresh } = useHealth();
  const [message, setMessage] = useState(null);

  const wipe = async () => {
    if (!window.confirm('Esto borra todos los ejercicios del historial y las imágenes subidas. ¿Continuar?')) return;
    try {
      await clearHistory();
      setMessage({ ok: true, text: 'Historial eliminado.' });
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err) });
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold text-white">Configuración</h1>
        <p className="text-gray-400 text-sm mt-0.5">Las preferencias se guardan en este navegador.</p>
      </header>

      <Section icon={settings.mode === 'Teacher' ? BookOpen : GraduationCap} title="Modo por defecto"
        description="Profesor muestra cada paso explicado; Examen muestra solo el resultado final.">
        <div className="flex bg-background/80 rounded-lg p-1 border border-white/5">
          {[['Teacher', 'Profesor'], ['Exam', 'Examen']].map(([value, label]) => (
            <button key={value} onClick={() => update({ mode: value })} aria-pressed={settings.mode === value}
              className={`px-4 py-1.5 text-sm rounded-md transition-colors ${settings.mode === value ? 'bg-primary text-white' : 'text-gray-400 hover:text-white'}`}>
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section icon={LineChart} title="Mostrar gráficas" description="Graficar funciones, derivadas, áreas y soluciones cuando tenga sentido.">
        <Toggle checked={settings.showGraphs} onChange={(v) => update({ showGraphs: v })} label="Mostrar gráficas" />
      </Section>

      <Section icon={Server} title="Servidor" description={online ? `Conectado · API v${info?.version}` : online === false ? 'Sin conexión con el backend.' : 'Verificando…'}>
        <div className="flex items-center gap-2 flex-wrap">
          {online && info?.ocr && (
            <>
              <Provider name="Gemini" enabled={info.ocr.gemini} />
              <Provider name="pix2tex" enabled={info.ocr.pix2tex} />
            </>
          )}
          <button onClick={refresh} aria-label="Volver a verificar" className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10">
            {online === null ? <Loader2 size={16} className="animate-spin" /> : <RotateCw size={16} />}
          </button>
        </div>
      </Section>

      <Section icon={Trash2} title="Borrar historial" description="Elimina todos los ejercicios guardados en el servidor. No se puede deshacer.">
        <button onClick={wipe} disabled={!online}
          className="px-4 py-2 rounded-lg text-sm border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-40 disabled:cursor-not-allowed">
          Borrar todo
        </button>
      </Section>

      {message && (
        <p role="status" className={`text-sm ${message.ok ? 'text-green-400' : 'text-red-400'}`}>{message.text}</p>
      )}

      <button onClick={reset} className="self-start text-sm text-gray-500 hover:text-white underline-offset-4 hover:underline">
        Restablecer preferencias
      </button>
    </div>
  );
}
