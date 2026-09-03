import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { signInWithEmail, signInWithGoogle, signUpWithEmail, supabaseConfigured } from '../lib/supabase';

const Login = ({ session }) => {
  const [mode, setMode] = useState('signin'); // 'signin' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  if (session) return <Navigate to="/app" replace />;

  const handleGoogle = async () => {
    setError(null);
    setBusy(true);
    try {
      const { error: oauthError } = await signInWithGoogle();
      if (oauthError) throw oauthError;
    } catch (err) {
      setError(err.message || 'Google orqali kirishda xatolik.');
      setBusy(false);
    }
  };

  const handleEmailSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === 'signup') {
        const { data, error: signUpError } = await signUpWithEmail(email, password);
        if (signUpError) throw signUpError;
        if (!data.session) {
          setInfo('Emailingizga tasdiqlash havolasi yuborildi. Havolani bosib, keyin kiring.');
        }
      } else {
        const { error: signInError } = await signInWithEmail(email, password);
        if (signInError) throw signInError;
      }
    } catch (err) {
      setError(err.message || 'Kirishda xatolik.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>{mode === 'signup' ? 'Ro‘yxatdan o‘tish' : 'Kirish'}</h1>
        <p className="auth-sub">ExcelYordamchi AI — o‘zbekcha Excel formula yordamchisi</p>

        {!supabaseConfigured && (
          <div className="auth-error">
            Supabase kalitlari sozlanmagan (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).
          </div>
        )}

        <button type="button" className="google-btn" onClick={handleGoogle} disabled={busy || !supabaseConfigured}>
          <svg className="google-mark" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/>
            <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/>
            <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/>
            <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/>
          </svg>
          Google bilan davom etish
        </button>

        <div className="auth-divider"><span>yoki email bilan</span></div>

        <form onSubmit={handleEmailSubmit} className="auth-form">
          <label htmlFor="auth-email">Email</label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <label htmlFor="auth-password">Parol</label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
          />
          <button type="submit" className="primary-btn full" disabled={busy || !supabaseConfigured}>
            {busy ? 'Kuting…' : mode === 'signup' ? 'Hisob yaratish' : 'Kirish'}
          </button>
        </form>

        {error && <div className="auth-error">{error}</div>}
        {info && <div className="auth-info">{info}</div>}

        <button
          type="button"
          className="auth-switch"
          onClick={() => { setMode(mode === 'signup' ? 'signin' : 'signup'); setError(null); setInfo(null); }}
        >
          {mode === 'signup' ? 'Hisobim bor — kirish' : 'Hisobim yo‘q — ro‘yxatdan o‘tish'}
        </button>
      </div>
    </div>
  );
};

export default Login;
