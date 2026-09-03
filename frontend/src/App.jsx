import React, { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Admin from './pages/Admin';
import Billing from './pages/Billing';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Workspace from './pages/Workspace';
import { apiFetch } from './lib/api';
import { signOut, useSession } from './lib/supabase';
import './App.css';
import './styles/shell.css';

function TopBar({ session, profile }) {
  const { pathname } = useLocation();
  const isPro = profile?.is_owner
    || profile?.plan === 'pro'
    || (profile?.pro_until && new Date(profile.pro_until) > new Date());

  return (
    <header className="topbar">
      <Link to="/" className="brand">
        <span className="brand-mark">X</span>
        <span>ExcelYordamchi <b>AI</b></span>
      </Link>

      <nav className="topbar-nav">
        <Link to="/app" className={pathname.startsWith('/app') ? 'active' : ''}>Ilova</Link>
        <Link to="/billing" className={pathname.startsWith('/billing') ? 'active' : ''}>Narxlar</Link>
        {profile?.is_owner && (
          <Link to="/admin" className={pathname.startsWith('/admin') ? 'active' : ''}>Admin</Link>
        )}
      </nav>

      <div className="topbar-actions">
        {session ? (
          <>
            <span className={`plan-badge ${isPro ? 'pro' : 'free'}`}>
              {profile?.is_owner ? 'Admin' : isPro ? 'Pro' : 'Bepul'}
            </span>
            <span className="topbar-email">{profile?.email || session.user?.email}</span>
            <button type="button" className="ghost-btn small" onClick={() => signOut()}>Chiqish</button>
          </>
        ) : (
          <Link to="/login" className="primary-btn small">Kirish</Link>
        )}
      </div>
    </header>
  );
}

function AppShell() {
  const { session, loading } = useSession();
  const [profile, setProfile] = useState(null);

  const refreshProfile = useCallback(async () => {
    if (!session) {
      setProfile(null);
      return;
    }
    try {
      setProfile(await apiFetch('/api/me'));
    } catch (err) {
      console.error('Profilni yuklab bo‘lmadi:', err);
    }
  }, [session]);

  useEffect(() => { refreshProfile(); }, [refreshProfile]);

  if (loading) {
    return <div className="app-container"><div className="loading">Yuklanmoqda…</div></div>;
  }

  return (
    <div className="app-container">
      <TopBar session={session} profile={profile} />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Landing session={session} />} />
          <Route path="/login" element={<Login session={session} />} />
          <Route
            path="/app"
            element={<Workspace session={session} profile={profile} onProfileRefresh={refreshProfile} />}
          />
          <Route
            path="/billing"
            element={<Billing session={session} profile={profile} onProfileRefresh={refreshProfile} />}
          />
          <Route path="/admin" element={<Admin session={session} profile={profile} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
