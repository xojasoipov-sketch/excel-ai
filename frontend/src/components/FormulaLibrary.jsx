import React, { useMemo, useState } from 'react';
import { CATEGORIES, FORMULA_LIBRARY } from '../data/formulaLibrary';
import FormulaTester from './FormulaTester';

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * "Shablonlar" screen: a searchable, category-filtered library of ready-made
 * formula templates (no AI call needed — instant and free), paired with the
 * live Formula Test panel so a picked template can be tried immediately.
 */
const FormulaLibrary = () => {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [selectedId, setSelectedId] = useState(FORMULA_LIBRARY[0].id);
  const [copiedId, setCopiedId] = useState(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return FORMULA_LIBRARY.filter((item) => {
      const matchesCategory = category === 'all' || item.category === category;
      const matchesQuery = !q
        || item.name.toLowerCase().includes(q)
        || item.formula.toLowerCase().includes(q)
        || item.description.toLowerCase().includes(q);
      return matchesCategory && matchesQuery;
    });
  }, [query, category]);

  const selected = useMemo(
    () => FORMULA_LIBRARY.find((item) => item.id === selectedId) || filtered[0] || FORMULA_LIBRARY[0],
    [selectedId, filtered]
  );

  const handleCopy = async (item) => {
    const ok = await copyToClipboard(item.formula);
    if (ok) {
      setCopiedId(item.id);
      setTimeout(() => setCopiedId((current) => (current === item.id ? null : current)), 1500);
    }
  };

  return (
    <div className="formula-library">
      <div className="library-list">
        <div className="library-search">
          <input
            type="text"
            placeholder="Formula qidiring… (masalan: SUMIF, sana, VLOOKUP)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="library-categories">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`category-pill ${category === c.id ? 'active' : ''}`}
              onClick={() => setCategory(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="library-cards">
          {filtered.length === 0 && (
            <div className="library-empty">Hech narsa topilmadi. Boshqa so‘z bilan qidiring.</div>
          )}
          {filtered.map((item) => (
            <div
              key={item.id}
              className={`library-card ${selected?.id === item.id ? 'active' : ''}`}
              onClick={() => setSelectedId(item.id)}
            >
              <div className="library-card-head">
                <h4>{item.name}</h4>
                <button
                  type="button"
                  className="library-copy-btn"
                  onClick={(e) => { e.stopPropagation(); handleCopy(item); }}
                >
                  {copiedId === item.id ? 'Nusxalandi ✓' : 'Nusxa olish'}
                </button>
              </div>
              <code>{item.formula}</code>
              <p>{item.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="library-tester">
        {selected && (
          <FormulaTester
            initialFormula={selected.formula}
            initialSample={selected.sample}
            resetKey={selected.id}
          />
        )}
      </div>
    </div>
  );
};

export default FormulaLibrary;
