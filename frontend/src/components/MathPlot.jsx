/**
 * MathPlot — Plotly (plotly.js-dist-min) cargado bajo demanda, compatible con React 19.
 */
import { useEffect, useRef, useState } from 'react';

const AXIS = { gridcolor: '#374151', zerolinecolor: '#6366f1', linecolor: '#4b5563' };

export default function MathPlot({ data, layout, style }) {
  const ref = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || !data) return;
    let cancelled = false;
    let Plotly;

    import('plotly.js-dist-min')
      .then((mod) => {
        if (cancelled) return;
        Plotly = mod.default ?? mod;
        Plotly.newPlot(el, data, {
          ...(layout || {}),
          autosize: true,
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#e5e7eb', family: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif', size: 12 },
          margin: { t: 20, r: 20, b: 40, l: 50 },
          legend: { orientation: 'h', y: -0.28 },
          xaxis: { ...(layout?.xaxis || {}), ...AXIS },
          yaxis: { ...(layout?.yaxis || {}), ...AXIS },
        }, { responsive: true, displayModeBar: false });
      })
      .catch(() => !cancelled && setFailed(true));

    return () => {
      cancelled = true;
      if (Plotly) Plotly.purge(el);
    };
  }, [data, layout]);

  if (failed) return <p className="text-sm text-gray-500 p-4">No se pudo cargar el gráfico.</p>;
  return <div ref={ref} style={style || { width: '100%', minHeight: '300px' }} />;
}
