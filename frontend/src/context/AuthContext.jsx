/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { authEnabled, supabase } from '../services/supabase';

const AuthContext = createContext(null);

const LOCAL_SESSION = { user: { email: 'modo local' }, local: true };

export function AuthProvider({ children }) {
  // undefined = still checking, null = signed out
  const [session, setSession] = useState(authEnabled ? undefined : LOCAL_SESSION);

  useEffect(() => {
    if (!supabase) return undefined;
    supabase.auth.getSession().then(({ data }) => setSession(data.session ?? null));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => setSession(next ?? null));
    return () => listener.subscription.unsubscribe();
  }, []);

  const value = useMemo(() => ({
    session,
    loading: session === undefined,
    authEnabled,
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    // The acceptance of the terms (and the age declaration) is stored with the account
    signUp: (email, password) => supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin,
        data: { terms_accepted_at: new Date().toISOString(), adult_declared: true },
      },
    }),
    signInWithGoogle: () => supabase.auth.signInWithOAuth({
      provider: 'google', options: { redirectTo: window.location.origin },
    }),
    resetPassword: (email) => supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/cuenta`,
    }),
    signOut: () => (supabase ? supabase.auth.signOut() : Promise.resolve()),
  }), [session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
