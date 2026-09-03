import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('uz-UZ', { year: '2-digit', month: '2-digit', day: '2-digit' });
  } catch {
    return String(value).slice(0, 10);
  }
}

function maskCard(digits) {
  if (!digits) return '';
  const clean = digits.replace(/\D/g, '');
  return clean.replace(/(.{4})/g, '$1 ').trim();
}

const StatCard = ({ label, value, hint, accent }) => (
  <div className={`stat-card ${accent || ''}`}>
    <span className="stat-label">{label}</span>
    <strong className="stat-value">{value}</strong>
    {hint && <span className="stat-hint">{hint}</span>}
  </div>
);

const Admin = ({ session, profile }) => {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [promos, setPromos] = useState([]);
  const [payments, setPayments] = useState([]);
  const [card, setCard] = useState('');
  const [cardSaved, setCardSaved] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const [newCode, setNewCode] = useState('');
  const [newPercent, setNewPercent] = useState(100);
  const [newDuration, setNewDuration] = useState('month');
  const [newLimit, setNewLimit] = useState('');
  const [promoError, setPromoError] = useState(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [statsData, usersData, promosData, paymentsData, cardData] = await Promise.all([
        apiFetch('/api/admin/stats'),
        apiFetch('/api/admin/users?limit=100'),
        apiFetch('/api/admin/promo-codes'),
        apiFetch('/api/admin/payments?limit=25'),
        apiFetch('/api/admin/payout-card'),
      ]);
      setStats(statsData);
      setUsers(usersData.users || []);
      setPromos(promosData.codes || []);
      setPayments(paymentsData.payments || []);
      setCard(cardData.card_number || '');
    } catch (err) {
      setError(err.message || 'Maʼlumotlarni yuklab bo‘lmadi.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.is_owner) loadAll();
  }, [profile?.is_owner, loadAll]);

  if (!session) return <Navigate to="/login" replace />;
  if (profile && !profile.is_owner) return <Navigate to="/app" replace />;

  const createPromo = async (event) => {
    event.preventDefault();
    setPromoError(null);
    try {
      await apiFetch('/api/admin/promo-codes', {
        method: 'POST',
        body: JSON.stringify({
          code: newCode.trim(),
          discount_percent: Number(newPercent),
          duration: newDuration,
          max_redemptions: newLimit ? Number(newLimit) : null,
        }),
      });
      setNewCode('');
      setNewLimit('');
      loadAll();
    } catch (err) {
      setPromoError(err.message || 'Promokod yaratilmadi.');
    }
  };

  const togglePromo = async (code, active) => {
    try {
      await apiFetch(`/api/admin/promo-codes/${encodeURIComponent(code)}`, {
        method: 'PATCH',
        body: JSON.stringify({ active }),
      });
      loadAll();
    } catch (err) {
      setPromoError(err.message);
    }
  };

  const deletePromo = async (code) => {
    try {
      await apiFetch(`/api/admin/promo-codes/${encodeURIComponent(code)}`, { method: 'DELETE' });
      loadAll();
    } catch (err) {
      setPromoError(err.message);
    }
  };

  const savePayoutCard = async (event) => {
    event.preventDefault();
    setCardSaved(false);
    try {
      await apiFetch('/api/admin/payout-card', {
        method: 'PUT',
        body: JSON.stringify({ card_number: card }),
      });
      setCardSaved(true);
      setTimeout(() => setCardSaved(false), 2500);
    } catch (err) {
      setError(err.message || 'Karta saqlanmadi.');
    }
  };

  return (
    <div className="admin-page">
      <header className="admin-header">
        <h1>Admin panel</h1>
        <button type="button" className="ghost-btn" onClick={loadAll}>Yangilash</button>
      </header>

      {error && <div className="alert error">{error}</div>}
      {loading && <div className="loading">Yuklanmoqda…</div>}

      {stats && (
        <>
          <section className="stat-grid">
            <StatCard label="Jami foydalanuvchi" value={stats.total_users} hint={`7 kunda +${stats.signups_7d}`} />
            <StatCard label="To‘lovchi (Pro)" value={stats.paying_users} accent="green" />
            <StatCard label="MRR" value={`$${stats.mrr_usd}`} hint="oylik takrorlanuvchi" accent="green" />
            <StatCard label="Jami tushum" value={`$${stats.revenue_total_usd}`} hint={`30 kunda $${stats.revenue_30d_usd}`} />
            <StatCard label="Promokod bilan Pro" value={stats.promo_pro_users} />
            <StatCard label="Bugungi AI so‘rov" value={stats.ai_calls_today} />
          </section>

          <section className="admin-section">
            <h2>Promokodlar</h2>
            <form className="promo-create" onSubmit={createPromo}>
              <input
                type="text"
                placeholder="KOD (masalan TEKIN2026)"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                required
              />
              <select value={newPercent} onChange={(e) => setNewPercent(e.target.value)}>
                <option value={100}>100% — to‘liq bepul</option>
                <option value={75}>75% chegirma</option>
                <option value={50}>50% chegirma</option>
                <option value={30}>30% chegirma</option>
                <option value={20}>20% chegirma</option>
                <option value={10}>10% chegirma</option>
              </select>
              <select value={newDuration} onChange={(e) => setNewDuration(e.target.value)}>
                <option value="month">1 oy</option>
                <option value="year">1 yil</option>
              </select>
              <input
                type="number"
                min="1"
                placeholder="Limit (bo‘sh = cheksiz)"
                value={newLimit}
                onChange={(e) => setNewLimit(e.target.value)}
              />
              <button type="submit" className="primary-btn">Yaratish</button>
            </form>
            {promoError && <div className="alert error">{promoError}</div>}

            <div className="table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Kod</th><th>Chegirma</th><th>Muddat</th><th>Ishlatilgan</th><th>Holat</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {promos.length === 0 && (
                    <tr><td colSpan={6} className="empty-row">Hali promokod yaratilmagan.</td></tr>
                  )}
                  {promos.map((p) => (
                    <tr key={p.code}>
                      <td><code>{p.code}</code></td>
                      <td>{p.discount_percent}%</td>
                      <td>{p.duration === 'year' ? '1 yil' : '1 oy'}</td>
                      <td>{p.redemption_count}{p.max_redemptions ? ` / ${p.max_redemptions}` : ''}</td>
                      <td>
                        <span className={p.active ? 'badge-on' : 'badge-off'}>
                          {p.active ? 'Faol' : 'O‘chirilgan'}
                        </span>
                      </td>
                      <td className="row-actions">
                        <button type="button" onClick={() => togglePromo(p.code, !p.active)}>
                          {p.active ? 'O‘chirish' : 'Yoqish'}
                        </button>
                        <button type="button" className="danger" onClick={() => deletePromo(p.code)}>O‘chirib tashlash</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-section">
            <h2>To‘lov kartam</h2>
            <p className="muted-note">
              Tushumni qabul qiladigan karta raqami. Faqat siz ko‘rasiz va o‘zgartirasiz — bazada
              shifrlangan holda saqlanadi.
            </p>
            <form className="card-form" onSubmit={savePayoutCard}>
              <input
                type="text"
                inputMode="numeric"
                value={maskCard(card)}
                onChange={(e) => setCard(e.target.value.replace(/\D/g, '').slice(0, 19))}
                placeholder="8600 1234 5678 9012"
              />
              <button type="submit" className="primary-btn">Saqlash</button>
            </form>
            {cardSaved && <div className="alert success">Karta saqlandi.</div>}
          </section>

          <section className="admin-section">
            <h2>Foydalanuvchilar ({users.length})</h2>
            <div className="table-wrap">
              <table className="admin-table">
                <thead>
                  <tr><th>Email</th><th>Reja</th><th>Pro tugashi</th><th>Qo‘shilgan</th></tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id}>
                      <td>{u.email}{u.is_owner && <span className="badge-owner">admin</span>}</td>
                      <td>{u.plan === 'pro' ? 'Pro' : 'Bepul'}</td>
                      <td>{formatDate(u.pro_until)}</td>
                      <td>{formatDate(u.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-section">
            <h2>To‘lovlar tarixi</h2>
            <div className="table-wrap">
              <table className="admin-table">
                <thead>
                  <tr><th>Sana</th><th>Turi</th><th>Summa</th><th>Holat</th></tr>
                </thead>
                <tbody>
                  {payments.length === 0 && (
                    <tr><td colSpan={4} className="empty-row">Hali to‘lov yo‘q.</td></tr>
                  )}
                  {payments.map((p) => (
                    <tr key={p.id}>
                      <td>{formatDate(p.created_at)}</td>
                      <td>{p.type}</td>
                      <td>{p.amount_cents ? `$${(p.amount_cents / 100).toFixed(2)}` : '—'}</td>
                      <td>{p.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default Admin;
