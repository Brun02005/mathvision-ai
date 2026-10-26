import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Link } from 'react-router-dom';
import { Calculator, Settings as SettingsIcon, History as HistoryIcon, UploadCloud, BookOpen, GraduationCap, Menu, X } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import HistoryDetail from './pages/HistoryDetail';
import Settings from './pages/Settings';
import { useSettings } from './context/SettingsContext';

const NAV = [
  { to: '/', label: 'Resolver Problema', icon: UploadCloud, end: true },
  { to: '/history', label: 'Historial', icon: HistoryIcon },
  { to: '/settings', label: 'Configuración', icon: SettingsIcon },
];

function ModeToggle() {
  const { settings, update } = useSettings();
  const mode = settings.mode;
  return (
    <div className="p-4 m-4 rounded-xl bg-surface border border-white/5">
      <div className="text-xs text-gray-400 mb-3 uppercase tracking-wider font-semibold">Modo de Operación</div>
      <div className="flex bg-background/80 rounded-lg p-1 relative" role="radiogroup" aria-label="Modo de operación">
        {[['Teacher', 'Profesor', BookOpen], ['Exam', 'Examen', GraduationCap]].map(([value, label, Icon]) => (
          <button key={value} role="radio" aria-checked={mode === value} onClick={() => update({ mode: value })}
            className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm rounded-md transition-colors z-10 ${mode === value ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}>
            <Icon size={16} /> {label}
          </button>
        ))}
        <div className="absolute top-1 bottom-1 w-[calc(50%-4px)] bg-primary rounded-md transition-transform duration-300 ease-out shadow-lg"
          style={{ transform: mode === 'Teacher' ? 'translateX(0)' : 'translateX(100%)' }} />
      </div>
      <p className="text-[11px] text-gray-500 mt-2">
        {mode === 'Teacher' ? 'Solución completa con cada paso explicado.' : 'Solo el resultado final.'}
      </p>
    </div>
  );
}

function Sidebar({ open, onClose }) {
  return (
    <>
      {open && <div className="fixed inset-0 bg-black/60 z-30 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside className={`fixed lg:static inset-y-0 left-0 z-40 w-64 border-r border-white/10 bg-surfaceLight/95 lg:bg-surfaceLight/50 backdrop-blur-md flex flex-col transition-transform duration-300 ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="p-6 flex items-center justify-between">
          <Link to="/" onClick={onClose} className="text-2xl font-bold text-gradient flex items-center gap-2">
            <Calculator className="text-primary" /> MathVision AI
          </Link>
          <button className="lg:hidden text-gray-400 hover:text-white" onClick={onClose} aria-label="Cerrar menú"><X size={20} /></button>
        </div>
        <nav className="flex-1 px-4 space-y-2 mt-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onClose}
              className={({ isActive }) => `flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${isActive ? 'bg-primary/15 text-white border border-primary/30' : 'text-gray-300 hover:bg-white/5 hover:text-white border border-transparent'}`}>
              <Icon size={20} /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <ModeToggle />
      </aside>
    </>
  );
}

function NotFound() {
  return (
    <div className="max-w-md mx-auto text-center mt-24 space-y-3">
      <p className="text-6xl font-bold text-gradient">404</p>
      <p className="text-gray-400">Esta página no existe.</p>
      <Link to="/" className="inline-block text-primary hover:underline">Volver a resolver problemas</Link>
    </div>
  );
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <Router>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

        <main className="flex-1 min-w-0 relative overflow-y-auto">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background pointer-events-none" />

          <header className="lg:hidden sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-background/80 backdrop-blur border-b border-white/10">
            <button onClick={() => setMenuOpen(true)} aria-label="Abrir menú" className="text-gray-300 hover:text-white"><Menu size={22} /></button>
            <span className="font-bold text-gradient">MathVision AI</span>
          </header>

          <div className="relative z-10 p-4 sm:p-8 min-h-full">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/history" element={<History />} />
              <Route path="/history/:id" element={<HistoryDetail />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}
