import { createClient } from '@supabase/supabase-js';
import { useEffect, useState } from 'react';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabaseConfigured = Boolean(url && anonKey);

// A stub keeps the app renderable (landing page, formula library) even when the
// keys aren't set yet, instead of blowing up at import time.
export const supabase = supabaseConfigured
  ? createClient(url, anonKey, { auth: { persistSession: true, autoRefreshToken: true } })
  : null;

export function useSession() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(supabaseConfigured);

  useEffect(() => {
    if (!supabase) return undefined;

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setLoading(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession ?? null);
      setLoading(false);
    });

    return () => subscription?.subscription?.unsubscribe();
  }, []);

  return { session, loading };
}

export async function signInWithGoogle() {
  if (!supabase) throw new Error('Supabase sozlanmagan.');
  return supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: `${window.location.origin}/app` },
  });
}

export async function signInWithEmail(email, password) {
  if (!supabase) throw new Error('Supabase sozlanmagan.');
  return supabase.auth.signInWithPassword({ email, password });
}

export async function signUpWithEmail(email, password) {
  if (!supabase) throw new Error('Supabase sozlanmagan.');
  return supabase.auth.signUp({
    email,
    password,
    options: { emailRedirectTo: `${window.location.origin}/app` },
  });
}

export async function signOut() {
  if (!supabase) return;
  await supabase.auth.signOut();
}
