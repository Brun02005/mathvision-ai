import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Calculator, Settings, History, UploadCloud, BookOpen, GraduationCap } from 'lucide-react';
import Dashboard from './pages/Dashboard';

function App() {
  const [mode, setMode] = useState('Teacher'); // 'Teacher' or 'Exam'

  return (
    <Router>
      <div className="flex h-screen overflow-hidden bg-background">
        {/* Sidebar */}
        <aside className="w-64 border-r border-white/10 bg-surfaceLight/50 backdrop-blur-md flex flex-col transition-all duration-300">
          <div className="p-6">
            <h1 className="text-2xl font-bold text-gradient flex items-center gap-2">
              <Calculator className="text-primary" />
              MathVision AI
            </h1>
          </div>
          
          <nav className="flex-1 px-4 space-y-2 mt-4">
            <Link to="/" className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 text-gray-300 hover:text-white transition-colors">
              <UploadCloud size={20} />
              <span>Resolver Problema</span>
            </Link>
            <Link to="/history" className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 text-gray-300 hover:text-white transition-colors">
              <History size={20} />
              <span>Historial</span>
            </Link>
            <Link to="/settings" className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 text-gray-300 hover:text-white transition-colors">
              <Settings size={20} />
              <span>Configuración</span>
            </Link>
          </nav>

          {/* Mode Toggle */}
          <div className="p-4 m-4 rounded-xl bg-surface border border-white/5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="text-xs text-gray-400 mb-3 uppercase tracking-wider font-semibold relative z-10">Modo de Operación</div>
            <div className="flex bg-background/80 rounded-lg p-1 relative z-10 backdrop-blur-sm">
              <button 
                onClick={() => setMode('Teacher')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm rounded-md transition-all z-10 ${mode === 'Teacher' ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
              >
                <BookOpen size={16} />
                Profesor
              </button>
              <button 
                onClick={() => setMode('Exam')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm rounded-md transition-all z-10 ${mode === 'Exam' ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
              >
                <GraduationCap size={16} />
                Examen
              </button>
              {/* Animated background pill */}
              <div 
                className="absolute top-1 bottom-1 w-[calc(50%-4px)] bg-primary rounded-md transition-transform duration-300 ease-out shadow-lg"
                style={{ transform: mode === 'Teacher' ? 'translateX(0)' : 'translateX(100%)' }}
              />
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 relative overflow-y-auto">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background pointer-events-none" />
          <div className="relative z-10 p-8 h-full">
            <Routes>
              <Route path="/" element={<Dashboard mode={mode} />} />
              <Route path="/history" element={<div className="text-white">Historial de problemas (Pronto)</div>} />
              <Route path="/settings" element={<div className="text-white">Configuración (Pronto)</div>} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

export default App;
