import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { LegalLayout, LEGAL } from './Legal';
import { errorMessage, requestWithdrawal } from '../services/api';

/** "Botón de arrepentimiento" (Res. SCI 424/2020): works without logging in and returns a code at once. */
export default function Withdrawal() {
  const [form, setForm] = useState({ email: '', name: '', details: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      setDone(await requestWithdrawal(form));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });
  const input = 'w-full bg-background/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60';

  return (
    <LegalLayout title="Botón de arrepentimiento">
      <p>Si contrataste el plan Pro hace 10 días o menos, podés revocar la contratación sin dar explicaciones y te devolvemos el
        total pagado (art. 34 de la Ley 24.240). No hace falta iniciar sesión. Si lo que querés es dejar de pagar más adelante,
        podés <Link className="text-primary" to="/cuenta">cancelar la suscripción</Link> en cualquier momento.</p>

      {done ? (
        <div role="status" className="glass-panel p-6 space-y-3">
          <p className="flex items-center gap-2 text-green-300 font-semibold"><CheckCircle2 size={18} /> Solicitud recibida</p>
          <p>Tu código de seguimiento es <strong className="text-white text-lg font-mono">{done.code}</strong>.</p>
          <p>{done.message}</p>
          <p className="text-xs text-gray-500">Ante cualquier duda escribinos a {LEGAL.email} indicando el código.</p>
        </div>
      ) : (
        <form onSubmit={submit} className="glass-panel p-6 space-y-4">
          <div>
            <label htmlFor="w-email" className="label mb-1 block">Email con el que pagaste</label>
            <input id="w-email" type="email" required maxLength={320} autoComplete="email" className={input} {...field('email')} />
          </div>
          <div>
            <label htmlFor="w-name" className="label mb-1 block">Nombre y apellido (opcional)</label>
            <input id="w-name" maxLength={200} autoComplete="name" className={input} {...field('name')} />
          </div>
          <div>
            <label htmlFor="w-details" className="label mb-1 block">Comentarios (opcional)</label>
            <textarea id="w-details" maxLength={2000} rows={3} className={`${input} resize-none`} {...field('details')} />
          </div>
          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
          <button type="submit" disabled={busy}
            className="px-6 py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold disabled:opacity-60 flex items-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Solicitar la revocación
          </button>
        </form>
      )}
    </LegalLayout>
  );
}
