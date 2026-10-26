import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { History as HistoryIcon, Loader2, Search, Trash2, AlertCircle, ChevronRight } from 'lucide-react';
import { MathBlock } from '../components/Latex';
import { getHistory, deleteExercise, errorMessage } from '../services/api';
import { formatDate } from '../utils/format';

const PAGE_SIZE = 20;

export default function History() {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  // `forQuery` records which search the data belongs to: loading = data is for an older search
  const [data, setData] = useState({ forQuery: null, items: [], total: 0, error: null });
  const [loadingMore, setLoadingMore] = useState(false);
  const { items, total, error } = data;
  const loading = data.forQuery !== debounced || loadingMore;

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    getHistory({ q: debounced, limit: PAGE_SIZE })
      .then((page) => !cancelled && setData({ forQuery: debounced, items: page.items, total: page.total, error: null }))
      .catch((err) => !cancelled && setData({ forQuery: debounced, items: [], total: 0, error: errorMessage(err) }));
    return () => { cancelled = true; };
  }, [debounced]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const page = await getHistory({ q: debounced, skip: items.length, limit: PAGE_SIZE });
      setData((d) => ({ ...d, items: [...d.items, ...page.items], total: page.total }));
    } catch (err) {
      setData((d) => ({ ...d, error: errorMessage(err) }));
    } finally {
      setLoadingMore(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('¿Eliminar este ejercicio del historial?')) return;
    try {
      await deleteExercise(id);
      setData((d) => ({ ...d, items: d.items.filter((it) => it.id !== id), total: d.total - 1 }));
    } catch (err) {
      setData((d) => ({ ...d, error: errorMessage(err) }));
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Historial</h1>
          <p className="text-gray-400 text-sm mt-0.5">{total} ejercicio{total === 1 ? '' : 's'} resuelto{total === 1 ? '' : 's'}</p>
        </div>
        <label className="relative w-full sm:w-72">
          <span className="sr-only">Buscar</span>
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar por tema o expresión…"
            className="w-full bg-surface border border-white/10 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-primary/60" />
        </label>
      </header>

      {error && (
        <div role="alert" className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-300">
          <AlertCircle size={14} className="shrink-0 mt-0.5" /><p>{error}</p>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="glass-panel p-10 text-center text-gray-500 flex flex-col items-center gap-3">
          <HistoryIcon className="w-10 h-10 opacity-30" />
          <p>{debounced ? 'No hay ejercicios que coincidan con la búsqueda.' : 'Todavía no resolviste ningún ejercicio.'}</p>
          {!debounced && <Link to="/" className="text-primary hover:underline text-sm">Resolver el primero</Link>}
        </div>
      )}

      <ul className="space-y-3">
        {items.map((it) => (
          <li key={it.id} className="glass-panel p-4 flex items-center gap-3 hover:border-primary/30 transition-colors">
            <Link to={`/history/${it.id}`} className="flex-1 min-w-0 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="bg-primary/20 border border-primary/30 text-primary px-2 py-0.5 rounded-full text-[11px] font-semibold">{it.domain_classification}</span>
                  <span className="text-[11px] text-gray-500">{formatDate(it.created_at)}</span>
                </div>
                <div className="text-sm text-gray-200 overflow-hidden"><MathBlock latex={it.extracted_latex} className="text-left" /></div>
                {it.final_result_latex && (
                  <div className="text-xs text-gray-400 flex items-center gap-1 overflow-hidden">
                    <span className="shrink-0">Resultado:</span>
                    <MathBlock latex={it.final_result_latex} className="!py-0 [&_.katex-display]:!m-0 [&_.katex-display]:!text-left" />
                  </div>
                )}
              </div>
              <ChevronRight size={16} className="text-gray-600 shrink-0" />
            </Link>
            <button onClick={() => remove(it.id)} aria-label="Eliminar ejercicio" title="Eliminar"
              className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-400/10 transition-colors shrink-0">
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>

      {loading && <div className="flex justify-center py-6"><Loader2 className="animate-spin text-primary" /></div>}

      {!loading && items.length < total && (
        <button onClick={loadMore} className="mx-auto px-5 py-2 rounded-xl bg-surfaceLight border border-white/10 text-sm hover:border-primary/40">
          Cargar más
        </button>
      )}
    </div>
  );
}
