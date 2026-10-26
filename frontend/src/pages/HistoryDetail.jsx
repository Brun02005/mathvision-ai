import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Trash2, AlertCircle } from 'lucide-react';
import SolutionView from '../components/SolutionView';
import { getExercise, deleteExercise, errorMessage } from '../services/api';
import { useSettings } from '../context/SettingsContext';
import { formatDate } from '../utils/format';

export default function HistoryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { settings } = useSettings();
  const [exercise, setExercise] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getExercise(id)
      .then((data) => !cancelled && setExercise(data))
      .catch((err) => !cancelled && setError(err.response?.status === 404 ? 'Este ejercicio no existe o fue eliminado.' : errorMessage(err)));
    return () => { cancelled = true; };
  }, [id]);

  const remove = async () => {
    if (!window.confirm('¿Eliminar este ejercicio del historial?')) return;
    try {
      await deleteExercise(id);
      navigate('/history');
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <Link to="/history" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white">
          <ArrowLeft size={16} /> Volver al historial
        </Link>
        {exercise && (
          <button onClick={remove} className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 px-3 py-1.5 rounded-lg hover:bg-red-400/10">
            <Trash2 size={14} /> Eliminar
          </button>
        )}
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300">
          <AlertCircle size={14} className="shrink-0 mt-0.5" /><p>{error}</p>
        </div>
      )}

      {!exercise && !error && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-primary" /></div>}

      {exercise && (
        <div className="glass-panel p-5">
          <p className="text-xs text-gray-500 mb-4">Resuelto el {formatDate(exercise.created_at)}</p>
          <SolutionView result={exercise} showSteps showGraph={settings.showGraphs} />
        </div>
      )}
    </div>
  );
}
