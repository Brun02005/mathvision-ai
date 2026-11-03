import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Crown, Loader2, LogOut, Sparkles, Calculator } from 'lucide-react';
import useAccount from '../hooks/useAccount';
import { useAuth } from '../context/AuthContext';
import { cancelSubscription, deleteAccount, errorMessage, subscribe } from '../services/api';
import { formatDate } from '../utils/format';

function UsageBar({ icon: Icon, label, used, limit }) {
  const pct = Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  return (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="flex items-center gap-1.5 text-gray-300"><Icon size={14} /> {label}</span>
        <span className="text-gray-400">{used} / {limit}</span>
      </div>
      <div className="h-2 rounded-full bg-white/5 overflow-hidden" role="progressbar" aria-valuenow={used} aria-valuemax={limit} aria-label={label}>
        <div className={`h-full rounded-full ${pct >= 100 ? 'bg-red-400' : pct >= 80 ? 'bg-amber-400' : 'bg-primary'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const ars = (n) => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n);

export default function Account() {
  const { account, error, refresh } = useAccount();
  const { signOut, session } = useAuth();
  const [params] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const returnedFromPayment = params.get('pago') === 'ok';

  // Back from Mercado Pago: the payment notification can take a few seconds to arrive
  useEffect(() => {
    if (!returnedFromPayment) return undefined;
    const timer = setInterval(refresh, 4000);
    const stop = setTimeout(() => clearInterval(timer), 60000);
    return () => { clearInterval(timer); clearTimeout(stop); };
  }, [returnedFromPayment, refresh]);

  const goPro = async () => {
    setActionError(null);
    setBusy(true);
    try {
      window.location.assign(await subscribe());
    } catch (err) {
      setActionError(errorMessage(err));
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!window.confirm('¿Cancelar la suscripción? Seguís siendo Pro hasta el final del período que ya pagaste.')) return;
    setActionError(null);
    setBusy(true);
    try {
      await cancelSubscription();
      await refresh();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (error) return <p role="alert" className="max-w-2xl mx-auto text-red-300">{error}</p>;
  if (!account) return <div className="flex justify-center mt-24"><Loader2 className="animate-spin text-primary" /></div>;

  const pro = account.plan === 'pro';
  const active = account.subscription_status === 'authorized';

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Mi cuenta</h1>
          <p className="text-gray-400 text-sm mt-0.5">{account.email}</p>
        </div>
        {!session?.local && (
          <button onClick={signOut} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-white/5">
            <LogOut size={15} /> Cerrar sesión
          </button>
        )}
      </header>

      {returnedFromPayment && !pro && (
        <div role="status" className="flex items-center gap-2 text-sm text-sky-200 bg-sky-500/10 border border-sky-500/20 rounded-xl p-4">
          <Loader2 size={15} className="animate-spin shrink-0" /> Estamos confirmando tu pago con Mercado Pago. Puede tardar unos segundos.
        </div>
      )}

      <section className="glass-panel p-6 space-y-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="label mb-1">Plan</p>
            <p className="text-xl font-semibold text-white flex items-center gap-2">
              {pro ? <><Crown size={18} className="text-amber-400" /> Pro</> : 'Gratis'}
            </p>
            {pro && account.pro_until && (
              <p className="text-xs text-gray-400 mt-1">
                {active ? 'Se renueva automáticamente. Pagado hasta' : 'Activo hasta'} {formatDate(account.pro_until)}
              </p>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <p className="label">Uso de hoy</p>
          <UsageBar icon={Calculator} label="Ejercicios" used={account.usage.exercises.used} limit={account.usage.exercises.limit} />
          <UsageBar icon={Sparkles} label="Ejercicios con IA (enunciados, fotos difíciles)" used={account.usage.ai.used} limit={account.usage.ai.limit} />
          <p className="text-xs text-gray-500">Los límites se renuevan todos los días a la medianoche. Los ejercicios que no se pudieron resolver no se cuentan.</p>
        </div>
      </section>

      {account.billing_enabled && (
        <section id="baja" className="glass-panel p-6 space-y-3">
          {!pro || !active ? (
            <>
              <p className="text-lg font-semibold text-white flex items-center gap-2"><Crown size={18} className="text-amber-400" /> MathVision Pro</p>
              <ul className="text-sm text-gray-300 space-y-1 list-disc pl-5">
                <li>Ejercicios ilimitados para uso personal</li>
                <li>Mucho más uso del asistente de IA para enunciados y fotos</li>
              </ul>
              <p className="text-2xl font-bold text-white">{ars(account.price_ars)} <span className="text-sm font-normal text-gray-400">/ mes</span></p>
              <button onClick={goPro} disabled={busy}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold disabled:opacity-60 flex items-center justify-center gap-2">
                {busy && <Loader2 size={16} className="animate-spin" />} Suscribirme con Mercado Pago
              </button>
              <p className="text-xs text-gray-500">Débito automático mensual. Podés cancelar cuando quieras desde esta página.</p>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-300">Tu suscripción se paga con Mercado Pago.</p>
              <button onClick={cancel} disabled={busy}
                className="px-4 py-2 rounded-lg text-sm border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-40">
                Cancelar suscripción
              </button>
            </>
          )}
          {actionError && <p role="alert" className="text-sm text-red-300">{actionError}</p>}
        </section>
      )}

      <DeleteAccount onDeleted={signOut} />
    </div>
  );
}

function DeleteAccount({ onDeleted }) {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      await onDeleted();
      window.location.assign('/');
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <section className="glass-panel p-6 space-y-3">
      <p className="font-semibold text-white">Eliminar mi cuenta</p>
      <p className="text-sm text-gray-400">Borra tu cuenta, tu historial y tus datos de uso. Si tenés una suscripción activa, primero
        la cancelamos para que no se hagan más cobros. No se puede deshacer.</p>
      {!open ? (
        <button onClick={() => setOpen(true)} className="px-4 py-2 rounded-lg text-sm border border-red-400/30 text-red-400 hover:bg-red-400/10">
          Eliminar mi cuenta
        </button>
      ) : (
        <div className="space-y-2">
          <label htmlFor="confirm-delete" className="text-sm text-gray-300 block">Escribí <strong>ELIMINAR</strong> para confirmar:</label>
          <input id="confirm-delete" value={confirm} onChange={(e) => setConfirm(e.target.value)}
            className="w-full sm:w-64 bg-background/60 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-red-400/60" />
          <div className="flex gap-2">
            <button onClick={remove} disabled={busy || confirm.trim().toUpperCase() !== 'ELIMINAR'}
              className="px-4 py-2 rounded-lg text-sm bg-red-500 text-white font-semibold disabled:opacity-40 flex items-center gap-2">
              {busy && <Loader2 size={14} className="animate-spin" />} Eliminar definitivamente
            </button>
            <button onClick={() => { setOpen(false); setConfirm(''); }} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white">
              Cancelar
            </button>
          </div>
          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        </div>
      )}
    </section>
  );
}
