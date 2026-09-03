import React, { useEffect, useMemo, useState } from 'react';
import { evaluateFormula, columnIndexToLetter } from '../utils/formulaEngine';

const GRID_ROWS = 8;
const GRID_COLS = 6; // A..F — enough columns for VLOOKUP-style lookup tables

function emptyGrid() {
  const cells = {};
  for (let r = 1; r <= GRID_ROWS; r += 1) {
    for (let c = 0; c < GRID_COLS; c += 1) {
      cells[`${columnIndexToLetter(c)}${r}`] = '';
    }
  }
  return cells;
}

/**
 * Live "Formula Test" panel: an editable mini-grid plus a formula box, evaluated
 * instantly and fully offline via formulaEngine (no AI call). This is the
 * standalone USP called out in the product brief — users can verify a formula
 * actually does what they expect before pasting it into their real spreadsheet.
 */
const FormulaTester = ({ initialFormula, initialSample, resetKey }) => {
  const [formula, setFormula] = useState(initialFormula || '=SUM(A1:A5)');
  const [cells, setCells] = useState(() => ({ ...emptyGrid(), ...(initialSample || {}) }));

  // Re-seed the grid whenever a new library formula is picked (resetKey changes).
  useEffect(() => {
    setFormula(initialFormula || '=SUM(A1:A5)');
    setCells({ ...emptyGrid(), ...(initialSample || {}) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  const evaluation = useMemo(() => evaluateFormula(formula, cells), [formula, cells]);

  const handleCellChange = (key, value) => {
    setCells((prev) => ({ ...prev, [key]: value }));
  };

  const handleClear = () => setCells(emptyGrid());

  return (
    <div className="formula-tester">
      <div className="tester-header">
        <h3>🧪 Formula Test</h3>
        <p>Formulani pastdagi jadval ustida sinab ko‘ring — natija zudlik bilan, AI’ga so‘rov yubormasdan hisoblanadi.</p>
      </div>

      <label className="tester-formula-label" htmlFor="formula-tester-input">Formula</label>
      <div className="tester-formula-row">
        <input
          id="formula-tester-input"
          type="text"
          className="tester-formula-input"
          value={formula}
          onChange={(e) => setFormula(e.target.value)}
          spellCheck={false}
        />
      </div>

      <div className={`tester-result ${evaluation.ok ? 'ok' : 'error'}`}>
        {evaluation.ok ? (
          <>
            <span className="tester-result-label">Natija</span>
            <span className="tester-result-value">{formatResult(evaluation.result)}</span>
          </>
        ) : (
          <>
            <span className="tester-result-label">Xato</span>
            <span className="tester-result-value">{evaluation.error}</span>
          </>
        )}
      </div>

      <div className="tester-grid-wrap">
        <table className="tester-grid">
          <thead>
            <tr>
              <th></th>
              {Array.from({ length: GRID_COLS }, (_, c) => (
                <th key={c}>{columnIndexToLetter(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: GRID_ROWS }, (_, r) => (
              <tr key={r}>
                <th>{r + 1}</th>
                {Array.from({ length: GRID_COLS }, (_, c) => {
                  const key = `${columnIndexToLetter(c)}${r + 1}`;
                  return (
                    <td key={key}>
                      <input
                        value={cells[key] ?? ''}
                        onChange={(e) => handleCellChange(key, e.target.value)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button type="button" className="tester-clear-btn" onClick={handleClear}>
        Jadvalni tozalash
      </button>
    </div>
  );
};

function formatResult(result) {
  if (result === null || result === undefined || result === '') return '(bo‘sh)';
  if (typeof result === 'boolean') return result ? 'TRUE' : 'FALSE';
  if (typeof result === 'number') {
    return Number.isInteger(result) ? String(result) : result.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  }
  // ISO date strings from date functions (TODAY/WORKDAY) — show just the date part.
  if (typeof result === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(result)) {
    return result.slice(0, 10);
  }
  return String(result);
}

export default FormulaTester;
