// Client-side Excel formula evaluator for the "Formula Test" panel.
// Built on hot-formula-parser (which wraps @handsontable/formulajs), but that
// package's built-in SUMIF/SUMIFS/AVERAGEIF/COUNTIFS etc. only implement the old
// 2-argument SUMIF form and don't cover VLOOKUP/XLOOKUP/INDEX/IFS/DATEDIF at all —
// verified against real formulas before writing this. We register faithful custom
// implementations for the functions AI-generated formulas use most, so a user's
// formula can be tried instantly, fully offline, without spending an AI call.
import { Parser } from 'hot-formula-parser';
import * as formulajsModule from '@handsontable/formulajs';

// Depending on the bundler's CJS/ESM interop, the functions can land either as
// named exports or nested under `.default` — support both so this doesn't break
// if the build tooling changes.
const fx = formulajsModule.VLOOKUP ? formulajsModule : (formulajsModule.default || formulajsModule);

function columnIndexToLetter(index) {
  let n = index + 1;
  let label = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    label = String.fromCharCode(65 + rem) + label;
    n = Math.floor((n - 1) / 26);
  }
  return label;
}

// Matches a single Excel-style criteria string ("Toshkent", ">100", "<=5", "<>0")
// against one cell value the way SUMIF/COUNTIF/AVERAGEIF family expect.
function matchesCriteria(value, criteria) {
  if (criteria === undefined || criteria === null || criteria === '') return false;
  const raw = String(criteria).trim();
  const opMatch = raw.match(/^(<=|>=|<>|=|<|>)(.*)$/);

  if (opMatch) {
    const [, op, rhsRaw] = opMatch;
    const rhsNum = parseFloat(rhsRaw);
    const lhsNum = parseFloat(value);
    const numeric = !Number.isNaN(rhsNum) && !Number.isNaN(lhsNum);
    const lhs = numeric ? lhsNum : String(value ?? '').toLowerCase();
    const rhs = numeric ? rhsNum : rhsRaw.trim().toLowerCase();
    switch (op) {
      case '=': return lhs === rhs;
      case '<>': return lhs !== rhs;
      case '<': return lhs < rhs;
      case '>': return lhs > rhs;
      case '<=': return lhs <= rhs;
      case '>=': return lhs >= rhs;
      default: return false;
    }
  }

  const rhsNum = parseFloat(raw);
  const lhsNum = parseFloat(value);
  if (!Number.isNaN(rhsNum) && !Number.isNaN(lhsNum)) return lhsNum === rhsNum;
  return String(value ?? '').trim().toLowerCase() === raw.toLowerCase();
}

function toNumber(value) {
  const n = parseFloat(value);
  return Number.isNaN(n) ? 0 : n;
}

function sumif(range, criteria, sumRange) {
  const source = sumRange || range;
  let total = 0;
  for (let i = 0; i < range.length; i += 1) {
    if (matchesCriteria(range[i], criteria)) total += toNumber(source[i]);
  }
  return total;
}

function countif(range, criteria) {
  let count = 0;
  for (const value of range) if (matchesCriteria(value, criteria)) count += 1;
  return count;
}

function averageif(range, criteria, avgRange) {
  const source = avgRange || range;
  let total = 0;
  let count = 0;
  for (let i = 0; i < range.length; i += 1) {
    if (matchesCriteria(range[i], criteria)) {
      total += toNumber(source[i]);
      count += 1;
    }
  }
  return count === 0 ? 0 : total / count;
}

// *IFS variants take pairs of (range, criteria) after the aggregation range
// (SUMIFS/AVERAGEIFS) or with no separate aggregation range (COUNTIFS).
function everyPairMatches(pairs, rowIndex) {
  for (let j = 0; j < pairs.length; j += 2) {
    if (!matchesCriteria(pairs[j][rowIndex], pairs[j + 1])) return false;
  }
  return true;
}

function sumifs(params) {
  const [sumRange, ...pairs] = params;
  let total = 0;
  for (let i = 0; i < sumRange.length; i += 1) {
    if (everyPairMatches(pairs, i)) total += toNumber(sumRange[i]);
  }
  return total;
}

function countifs(params) {
  const length = params[0]?.length ?? 0;
  let count = 0;
  for (let i = 0; i < length; i += 1) if (everyPairMatches(params, i)) count += 1;
  return count;
}

function averageifs(params) {
  const [avgRange, ...pairs] = params;
  let total = 0;
  let count = 0;
  for (let i = 0; i < avgRange.length; i += 1) {
    if (everyPairMatches(pairs, i)) {
      total += toNumber(avgRange[i]);
      count += 1;
    }
  }
  return count === 0 ? 0 : total / count;
}

function indexFn([array, row, col]) {
  if (!Array.isArray(array)) return '#REF!';
  if (Array.isArray(array[0])) {
    return col === undefined ? array[row - 1]?.[0] : array[row - 1]?.[col - 1];
  }
  return array[row - 1];
}

function xlookupFn([needle, lookupArray, returnArray, notFound]) {
  if (!Array.isArray(lookupArray) || !Array.isArray(returnArray)) return '#N/A';
  const idx = lookupArray.findIndex((v) => String(v) === String(needle));
  return idx === -1 ? (notFound ?? '#N/A') : returnArray[idx];
}

function ifsFn(params) {
  for (let i = 0; i < params.length; i += 2) {
    if (params[i]) return params[i + 1];
  }
  return '#N/A';
}

function datedifFn([start, end, unit]) {
  const d1 = new Date(start);
  const d2 = new Date(end);
  if (Number.isNaN(d1.getTime()) || Number.isNaN(d2.getTime())) return '#VALUE!';
  const days = Math.round((d2 - d1) / 86400000);
  const u = String(unit || 'D').toUpperCase();
  if (u === 'D') return days;
  if (u === 'M') return Math.floor(days / 30);
  if (u === 'Y') return Math.floor(days / 365);
  return days;
}

/**
 * Build a parser wired to a flat { A1: value, B2: value, ... } cell map.
 * Single-column ranges resolve to a plain list (what SUM/COUNTIF-style functions
 * expect); wider ranges stay row-matrices (what VLOOKUP/INDEX expect).
 */
function createParser(cells) {
  const parser = new Parser();

  parser.on('callCellValue', (cellCoord, done) => {
    done(cells[cellCoord.label] ?? '');
  });

  parser.on('callRangeValue', (start, end, done) => {
    const numCols = end.column.index - start.column.index + 1;
    const rows = [];
    for (let r = start.row.index; r <= end.row.index; r += 1) {
      const row = [];
      for (let c = start.column.index; c <= end.column.index; c += 1) {
        row.push(cells[columnIndexToLetter(c) + (r + 1)] ?? '');
      }
      rows.push(row);
    }
    done(numCols === 1 ? rows.map((r) => r[0]) : rows);
  });

  parser.setFunction('SUMIF', (p) => sumif(p[0], p[1], p[2]));
  parser.setFunction('COUNTIF', (p) => countif(p[0], p[1]));
  parser.setFunction('AVERAGEIF', (p) => averageif(p[0], p[1], p[2]));
  parser.setFunction('SUMIFS', sumifs);
  parser.setFunction('COUNTIFS', countifs);
  parser.setFunction('AVERAGEIFS', averageifs);
  parser.setFunction('VLOOKUP', (p) => fx.VLOOKUP(p[0], p[1], p[2], p[3]));
  parser.setFunction('MATCH', (p) => fx.MATCH(p[0], p[1], p[2]));
  parser.setFunction('INDEX', indexFn);
  parser.setFunction('XLOOKUP', xlookupFn);
  parser.setFunction('IFS', ifsFn);
  parser.setFunction('DATEDIF', datedifFn);

  return parser;
}

/**
 * Evaluate a formula string (with or without a leading "=") against a flat cell map.
 * Returns { ok, result, error }.
 */
export function evaluateFormula(formula, cells) {
  const expr = String(formula || '').trim().replace(/^=/, '');
  if (!expr) return { ok: false, result: null, error: 'Formula bo‘sh' };

  try {
    const parser = createParser(cells);
    const { result, error } = parser.parse(expr);
    if (error) return { ok: false, result: null, error };
    return { ok: true, result, error: null };
  } catch (e) {
    return { ok: false, result: null, error: e?.message || 'Noma‘lum xato' };
  }
}

export { columnIndexToLetter };
