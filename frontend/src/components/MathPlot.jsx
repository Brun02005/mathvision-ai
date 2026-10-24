/**
 * MathPlot — wrapper de Plotly compatible con React 19 + Vite.
 * Usa plotly.js-dist-min directamente sin react-plotly.js.
 */
import { useEffect, useRef } from 'react';

export default function MathPlot({ data, layout, style }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !data) return;

    import('plotly.js-dist-min').then((Plotly) => {
      const mergedLayout = {
        ...(layout || {}),
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#e5e7eb', family: 'Inter, sans-serif', size: 12 },
        margin: { t: 30, r: 20, b: 40, l: 50 },
        xaxis: {
          ...(layout?.xaxis || {}),
          gridcolor: '#374151',
          zerolinecolor: '#6366f1',
          linecolor: '#4b5563',
        },
        yaxis: {
          ...(layout?.yaxis || {}),
          gridcolor: '#374151',
          zerolinecolor: '#6366f1',
          linecolor: '#4b5563',
        },
      };

      Plotly.newPlot(ref.current, data, mergedLayout, {
        responsive: true,
        displayModeBar: false,
      });
    });

    // Cleanup on unmount
    return () => {
      import('plotly.js-dist-min').then((Plotly) => {
        if (ref.current) Plotly.purge(ref.current);
      });
    };
  }, [data, layout]);

  return (
    <div
      ref={ref}
      style={style || { width: '100%', minHeight: '280px' }}
    />
  );
}
