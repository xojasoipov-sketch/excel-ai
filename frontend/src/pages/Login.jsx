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
          <span className="google-mark">G</span> Google bilan davom etish
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
