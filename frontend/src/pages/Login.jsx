import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Calculator, Loader2, Mail } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import LegalLinks from '../components/LegalLinks';

const MESSAGES = {
  'Invalid login credentials': 'Email o contraseña incorrectos.',
  'User already registered': 'Ya existe una cuenta con ese email. Iniciá sesión.',
  'Email not confirmed': 'Todavía no confirmaste tu email. Revisá tu casilla (y la carpeta de spam).',
};

function translate(error) {
  if (!error) return null;
  return MESSAGES[error.message] || error.message || 'No se pudo completar la operación.';
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export default function Login() {
  const { signIn, signUp, signInWithGoogle, resetPassword } = useAuth();
  const [mode, setMode] = useState('signin'); // signin | signup | reset
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [accepted, setAccepted] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (mode !== 'reset' && password.length < 8) return setError('La contraseña tiene que tener al menos 8 caracteres.');
    if (mode === 'signup' && !accepted) return setError('Para crear la cuenta tenés que confirmar que tenés 18 años o más y aceptar los términos.');
    setBusy(true);
    try {
      if (mode === 'signin') {
        const { error: err } = await signIn(email, password);
        if (err) setError(translate(err));
      } else if (mode === 'signup') {
        const { data, error: err } = await signUp(email, password);
        if (err) setError(translate(err));
        else if (!data.session) setNotice(`Te enviamos un mail a ${email} para confirmar la cuenta.`);
      } else {
        const { error: err } = await resetPassword(email);
        if (err) setError(translate(err));
        else setNotice(`Si existe una cuenta con ${email}, te llega un mail para elegir una contraseña nueva.`);
      }
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setError(null);
    const { error: err } = await signInWithGoogle();
    if (err) setError(translate(err));
  };

  const titles = { signin: 'Iniciá sesión', signup: 'Creá tu cuenta', reset: 'Recuperar contraseña' };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <div className="text-3xl font-bold text-gradient flex items-center justify-center gap-2">
            <Calculator className="text-primary" /> MathVision AI
          </div>
          <p className="text-gray-400 text-sm">Resolvé cualquier ejercicio de matemática, paso a paso.</p>
        </div>

        <div className="glass-panel p-6 space-y-4">
          <h1 className="text-lg font-semibold text-white">{titles[mode]}</h1>

          {mode !== 'reset' && (
            <>
              <button onClick={google} type="button"
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white text-gray-800 font-medium text-sm hover:bg-gray-100 transition-colors">
                <GoogleIcon /> Continuar con Google
              </button>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <div className="flex-1 h-px bg-white/10" /> o con tu email <div className="flex-1 h-px bg-white/10" />
              </div>
            </>
          )}

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="email" className="label mb-1 block">Email</label>
              <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-background/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60" />
            </div>
            {mode !== 'reset' && (
              <div>
                <label htmlFor="password" className="label mb-1 block">Contraseña</label>
                <input id="password" type="password" required minLength={8}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-background/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60" />
              </div>
            )}

            {mode === 'signup' && (
              <label className="flex items-start gap-2 text-xs text-gray-300 cursor-pointer">
                <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} className="mt-0.5 accent-primary" />
                <span>Tengo 18 años o más y acepto los <Link className="text-primary underline" to="/terminos">Términos</Link> y
                  la <Link className="text-primary underline" to="/privacidad">Política de privacidad</Link>.</span>
              </label>
            )}

            {error && <p role="alert" className="text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}
            {notice && (
              <p role="status" className="text-sm text-green-300 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 flex gap-2">
                <Mail size={16} className="shrink-0 mt-0.5" /> {notice}
              </p>
            )}

            <button type="submit" disabled={busy}
              className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
              {busy && <Loader2 size={16} className="animate-spin" />}
              {{ signin: 'Entrar', signup: 'Crear cuenta', reset: 'Enviar mail' }[mode]}
            </button>
          </form>

          <div className="text-xs text-gray-400 flex flex-wrap justify-between gap-2">
            {mode === 'signin' ? (
              <>
                <button className="hover:text-white" onClick={() => setMode('signup')}>¿No tenés cuenta? Registrate</button>
                <button className="hover:text-white" onClick={() => setMode('reset')}>Olvidé mi contraseña</button>
              </>
            ) : (
              <button className="hover:text-white" onClick={() => setMode('signin')}>Ya tengo cuenta: iniciar sesión</button>
            )}
          </div>
        </div>
        <p className="text-center text-[11px] text-gray-500">
          Servicio para mayores de 18 años. Al continuar con Google aceptás los <Link className="underline" to="/terminos">Términos</Link> y
          la <Link className="underline" to="/privacidad">Política de privacidad</Link>.
        </p>
        <LegalLinks className="justify-center" />
      </div>
    </div>
  );
}
