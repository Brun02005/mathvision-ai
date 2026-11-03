import { Component } from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';

/**
 * A rendering error anywhere below shows this instead of a blank page.
 * (Error boundaries must be class components: React has no hook for componentDidCatch.)
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error('UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="max-w-md mx-auto mt-24 text-center space-y-4 p-6">
        <AlertTriangle className="mx-auto text-amber-400" size={36} />
        <h1 className="text-lg font-semibold text-white">Algo salió mal al mostrar esta pantalla</h1>
        <p className="text-sm text-gray-400">Tus datos están a salvo. Recargá la página para seguir.</p>
        <button onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover">
          <RotateCw size={14} /> Recargar
        </button>
      </div>
    );
  }
}
