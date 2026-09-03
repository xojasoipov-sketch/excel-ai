import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';

const Landing = ({ session }) => {
  const [plans, setPlans] = useState(null);

  useEffect(() => {
    apiFetch('/api/plans').then(setPlans).catch(() => setPlans(null));
  }, []);

  const proPrice = plans?.pro?.price_usd ?? 5;
  const freeCalls = plans?.free?.daily_ai_calls ?? 5;

  return (
    <div className="marketing">
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-eyebrow">fx · O‘zbekcha AI</span>
          <h1>Excel formulalarini <span>o‘z tilingizda</span> so‘rang</h1>
          <p>
            “B ustundagi Toshkent bo‘yicha sotuvlar yig‘indisini top” deb yozing —
            ExcelYordamchi AI tayyor formulani izohi bilan qaytaradi. O‘zbek, rus va
            ingliz tilida ishlaydi.
          </p>
          <div className="hero-actions">
            <Link to={session ? '/app' : '/login'} className="primary-btn">
              {session ? 'Ishni boshlash' : 'Bepul boshlash'}
            </Link>
            <Link to="/app" className="ghost-btn">Formula kutubxonasini ko‘rish</Link>
          </div>
          <p className="hero-note">Kartani ulash shart emas — kuniga {freeCalls} ta so‘rov bepul.</p>
        </div>
        <div className="hero-formula">
          <div className="formula-bar">
            <span className="fx">fx</span>
            <code>=SUMIF(B2:B100,"Toshkent",D2:D100)</code>
          </div>
          <ul className="hero-list">
            <li>✓ Fayl yuklab, jadval ustida to‘g‘ridan-to‘g‘ri ishlash</li>
            <li>✓ Faylsiz rejim — jadvalni so‘z bilan tasvirlash</li>
            <li>✓ 24 ta tayyor shablon + formulani sinash paneli</li>
            <li>✓ Telegram bot</li>
          </ul>
        </div>
      </section>

      <section className="pricing" id="narxlar">
        <h2>Narxlar</h2>
        <div className="pricing-grid">
          <div className="price-card">
            <h3>Bepul</h3>
            <div className="price">$0<span>/oy</span></div>
            <ul>
              <li>Kuniga {freeCalls} ta AI so‘rov</li>
              <li>Fayl yuklash va tahlil</li>
              <li>Formula kutubxonasi — cheksiz</li>
              <li>Formula Test — cheksiz</li>
            </ul>
            <Link to="/login" className="ghost-btn full">Ro‘yxatdan o‘tish</Link>
          </div>

          <div className="price-card featured">
            <div className="price-badge">Ommabop</div>
            <h3>Pro</h3>
            <div className="price">${proPrice}<span>/oy</span></div>
            <ul>
              <li>Cheksiz AI so‘rovlar</li>
              <li>Cheksiz fayl tahlili</li>
              <li>Barcha shablonlar va Test rejimi</li>
              <li>Telegram bot</li>
            </ul>
            <Link to="/billing" className="primary-btn full">Pro’ga o‘tish</Link>
          </div>
        </div>

        <div className="payment-methods">
          <span>To‘lov usullari:</span>
          <div className="method-chip active">💳 Karta (Visa/Mastercard)</div>
          <div className="method-chip soon">Payme — tez orada</div>
          <div className="method-chip soon">Click — tez orada</div>
        </div>
      </section>

      <section className="how">
        <h2>Qanday ishlaydi?</h2>
        <div className="how-grid">
          <div><span>1</span><h4>Ro‘yxatdan o‘ting</h4><p>Google akkaunt bilan bir bosishda.</p></div>
          <div><span>2</span><h4>So‘rovingizni yozing</h4><p>Faylni yuklang yoki jadvalni so‘z bilan tasvirlang.</p></div>
          <div><span>3</span><h4>Formulani oling</h4><p>Nusxa oling yoki shu yerda sinab ko‘ring.</p></div>
        </div>
      </section>
    </div>
  );
};

export default Landing;
