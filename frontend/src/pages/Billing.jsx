import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch } from '../lib/api';

function formatDate(value) {
  if (!value) return null;
  try {
    return new Date(value).toLocaleDateString('uz-UZ', { year: 'numeric', month: 'long', day: 'numeric' });
  } catch {
    return String(value).slice(0, 10);
  }
}

const Billing = ({ session, profile, onProfileRefresh }) => {
  const [searchParams] = useSearchParams();
  const [plans, setPlans] = useState(null);
  const [promoCode, setPromoCode] = useState('');
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoResult, setPromoResult] = useState(null);
  const [promoError, setPromoError] = useState(null);
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState(null);

  const checkoutState = searchParams.get('checkout');

  useEffect(() => {
    apiFetch('/api/plans').then(setPlans).catch(() => setPlans(null));
  }, []);

  useEffect(() => {
    if (checkoutState === 'success') onProfileRefresh?.();
  }, [checkoutState, onProfileRefresh]);

  const isPro = profile?.is_owner
    || profile?.plan === 'pro'
    || (profile?.pro_until && new Date(profile.pro_until) > new Date());

  const redeemPromo = async (event) => {
    event.preventDefault();
    if (!promoCode.trim()) return;
    setPromoBusy(true);
    setPromoError(null);
    setPromoResult(null);
    try {
      const result = await apiFetch('/api/promo/redeem', {
        method: 'POST',
        body: JSON.stringify({ code: promoCode.trim() }),
      });
      setPromoResult(result);
      setPromoCode('');
      onProfileRefresh?.();
    } catch (err) {
      setPromoError(err.message || 'Promokodni qo‘llab bo‘lmadi.');
    } finally {
      setPromoBusy(false);
    }
  };

  const startCheckout = async () => {
    setCheckoutBusy(true);
    setCheckoutError(null);
    try {
      const { url } = await apiFetch('/api/billing/checkout', { method: 'POST' });
      window.location.href = url;
    } catch (err) {
      setCheckoutError(err.message || 'To‘lov sahifasini ochib bo‘lmadi.');
      setCheckoutBusy(false);
    }
  };

  const openPortal = async () => {
    setCheckoutBusy(true);
    setCheckoutError(null);
    try {
      const { url } = await apiFetch('/api/billing/portal', { method: 'POST' });
      window.location.href = url;
    } catch (err) {
      setCheckoutError(err.message || 'Obuna boshqaruvini ochib bo‘lmadi.');
      setCheckoutBusy(false);
    }
  };

  if (!session) {
    return (
      <div className="page-narrow">
        <h1>Obuna</h1>
        <p>Obunani boshqarish uchun tizimga kiring.</p>
        <Link to="/login" className="primary-btn">Kirish</Link>
      </div>
    );
  }

  const price = plans?.pro?.price_usd ?? 5;
  const cardActive = plans?.methods?.card === 'active';

  return (
    <div className="page-narrow billing-page">
      <h1>Obuna va to‘lov</h1>

      {checkoutState === 'success' && (
        <div className="alert success">To‘lov qabul qilindi. Obunangiz bir necha soniyada faollashadi.</div>
      )}
      {checkoutState === 'cancelled' && (
        <div className="alert">To‘lov bekor qilindi.</div>
      )}

      <div className="plan-status">
        <div>
          <span className="plan-status-label">Hozirgi holat</span>
          <strong className={isPro ? 'plan-pro' : 'plan-free'}>
            {profile?.is_owner ? 'Admin — cheksiz' : isPro ? 'Pro — cheksiz' : 'Bepul'}
          </strong>
          {profile?.pro_until && !profile?.is_owner && (
            <span className="plan-until">Amal qiladi: {formatDate(profile.pro_until)}</span>
          )}
          {!isPro && profile?.quota && (
            <span className="plan-until">
              Bugun qoldi: {profile.quota.remaining} / {profile.quota.limit} so‘rov
            </span>
          )}
        </div>
        {profile?.plan === 'pro' && !profile?.is_owner && (
          <button type="button" className="ghost-btn" onClick={openPortal} disabled={checkoutBusy}>
            Obunani boshqarish
          </button>
        )}
      </div>

      {!isPro && (
        <div className="upgrade-card">
          <h2>Pro — ${price}/oy</h2>
          <ul>
            <li>Cheksiz AI formula so‘rovlari</li>
            <li>Cheksiz fayl tahlili</li>
            <li>Barcha shablonlar va Formula Test</li>
          </ul>
          <button type="button" className="primary-btn full" onClick={startCheckout} disabled={checkoutBusy || !cardActive}>
            {checkoutBusy ? 'Ochilmoqda…' : '💳 Karta bilan to‘lash'}
          </button>
          {!cardActive && (
            <p className="muted-note">
              Karta orqali to‘lov hali yoqilmagan. Promokod bilan Pro’ni hozir ham ochish mumkin.
            </p>
          )}
          {checkoutError && <div className="alert error">{checkoutError}</div>}
        </div>
      )}

      <div className="promo-card">
        <h2>Promokod</h2>
        <p>Chegirma yoki bepul obuna kodi bo‘lsa, shu yerga kiriting.</p>
        <form onSubmit={redeemPromo} className="promo-form">
          <input
            type="text"
            value={promoCode}
            onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
            placeholder="MASALAN: TEKIN2026"
            maxLength={32}
          />
          <button type="submit" className="primary-btn" disabled={promoBusy}>
            {promoBusy ? 'Tekshirilmoqda…' : 'Qo‘llash'}
          </button>
        </form>
        {promoResult && <div className="alert success">{promoResult.message}</div>}
        {promoError && <div className="alert error">{promoError}</div>}
      </div>

      <div className="methods-card">
        <h2>To‘lov usullari</h2>
        <div className="methods-row">
          <div className={`method-chip ${cardActive ? 'active' : 'soon'}`}>
            💳 Karta (Visa / Mastercard) {cardActive ? '' : '— sozlanmagan'}
          </div>
          <div className="method-chip soon">Payme (so‘m) — tez orada</div>
          <div className="method-chip soon">Click (so‘m) — tez orada</div>
        </div>
        <p className="muted-note">
          So‘m orqali to‘lov (Payme va Click) ustida ishlanmoqda — tayyor bo‘lganda shu yerda paydo bo‘ladi.
        </p>
      </div>
    </div>
  );
};

export default Billing;
