"""Formula Library + Formula Test, ported to Python for the Telegram bot.

This mirrors frontend/src/data/formulaLibrary.js and frontend/src/utils/formulaEngine.js
exactly (same 24 templates, same criteria semantics) so a formula behaves identically
whether a user tries it on the website or through the bot. The web version runs on
hot-formula-parser (a JS-only dependency), so rather than pull in a heavy Excel-formula
engine for Python, each template gets a small dedicated evaluator function — the same
approach already proven correct and tested on the frontend.
"""
from datetime import datetime, date
from typing import Callable, Dict, List, Optional, Tuple

Cells = Dict[str, str]


# ─── Shared criteria semantics (matches formulaEngine.js's matchesCriteria) ────

def _matches_criteria(value, criteria: str) -> bool:
    if criteria is None or criteria == "":
        return False
    raw = str(criteria).strip()
    for op in ("<=", ">=", "<>", "=", "<", ">"):
        if raw.startswith(op):
            rhs_raw = raw[len(op):]
            try:
                rhs_num, lhs_num = float(rhs_raw), float(value)
                lhs, rhs = lhs_num, rhs_num
            except (TypeError, ValueError):
                lhs, rhs = str(value or "").lower(), rhs_raw.strip().lower()
            if op == "=":
                return lhs == rhs
            if op == "<>":
                return lhs != rhs
            if op == "<":
                return lhs < rhs
            if op == ">":
                return lhs > rhs
            if op == "<=":
                return lhs <= rhs
            if op == ">=":
                return lhs >= rhs
    try:
        return float(value) == float(raw)
    except (TypeError, ValueError):
        return str(value or "").strip().lower() == raw.lower()


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _column(cells: Cells, letter: str, start: int, end: int) -> List:
    return [cells.get(f"{letter}{r}") for r in range(start, end + 1)]


def _sumif(range_: List, criteria: str, sum_range: Optional[List] = None) -> float:
    source = sum_range or range_
    return sum(_num(source[i]) for i, v in enumerate(range_) if _matches_criteria(v, criteria))


def _countif(range_: List, criteria: str) -> int:
    return sum(1 for v in range_ if _matches_criteria(v, criteria))


def _averageif(range_: List, criteria: str, avg_range: Optional[List] = None) -> float:
    source = avg_range or range_
    matched = [_num(source[i]) for i, v in enumerate(range_) if _matches_criteria(v, criteria)]
    return sum(matched) / len(matched) if matched else 0.0


def _sumifs(sum_range: List, *pairs) -> float:
    total = 0.0
    for i in range(len(sum_range)):
        if all(_matches_criteria(pairs[j][i], pairs[j + 1]) for j in range(0, len(pairs), 2)):
            total += _num(sum_range[i])
    return total


def _vlookup(needle, table_cols: List[List], col_index: int):
    needle_col = table_cols[0]
    for i, v in enumerate(needle_col):
        if str(v) == str(needle):
            return table_cols[col_index - 1][i]
    return "#N/A"


def _xlookup(needle, lookup: List, ret: List, not_found="Topilmadi"):
    for i, v in enumerate(lookup):
        if str(v) == str(needle):
            return ret[i]
    return not_found


def _index_match(needle, lookup: List, ret: List):
    return _xlookup(needle, lookup, ret, not_found="#N/A")


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt).date()
        except ValueError:
            continue
    return None


def _datedif(start, end, unit: str = "D"):
    d1, d2 = _parse_date(start), _parse_date(end)
    if not d1 or not d2:
        return "#VALUE!"
    days = (d2 - d1).days
    unit = (unit or "D").upper()
    if unit == "M":
        return days // 30
    if unit == "Y":
        return days // 365
    return days


def _pmt(rate: float, nper: float, pv: float) -> float:
    if rate == 0:
        return -pv / nper
    return -pv * rate * (1 + rate) ** nper / ((1 + rate) ** nper - 1)


# ─── The 24 templates (id/category/name/formula/description/sample) ───────────
# Kept in the same order and content as frontend/src/data/formulaLibrary.js.

FORMULA_LIBRARY: List[dict] = [
    {"id": "sum-basic", "category": "sum", "name": "Ustun yig'indisi", "formula": "=SUM(A1:A10)",
     "description": "A1 dan A10 gacha bo'lgan barcha sonlarni qo'shadi.",
     "sample": {"A1": 10, "A2": 20, "A3": 5, "A4": 15}},
    {"id": "average-basic", "category": "sum", "name": "O'rtacha qiymat", "formula": "=AVERAGE(A1:A10)",
     "description": "Diapazondagi sonlarning o'rtachasini hisoblaydi.",
     "sample": {"A1": 10, "A2": 20, "A3": 5, "A4": 15}},
    {"id": "sumif-basic", "category": "sum", "name": "Shart bo'yicha yig'indi (SUMIF)",
     "formula": '=SUMIF(B1:B10,"Toshkent",A1:A10)',
     "description": "B ustuni \"Toshkent\" bo'lgan qatorlardagi A ustun qiymatlarini yig'adi.",
     "sample": {"A1": 100, "B1": "Toshkent", "A2": 50, "B2": "Andijon", "A3": 30, "B3": "Toshkent"}},
    {"id": "sumifs-basic", "category": "sum", "name": "Bir nechta shart bo'yicha yig'indi (SUMIFS)",
     "formula": '=SUMIFS(D1:D10,B1:B10,"Toshkent",C1:C10,">100")',
     "description": "B ustuni \"Toshkent\" VA C ustuni 100 dan katta bo'lgan qatorlardagi D ustunini yig'adi.",
     "sample": {"D1": 500, "B1": "Toshkent", "C1": 150, "D2": 200, "B2": "Toshkent", "C2": 50}},
    {"id": "countif-basic", "category": "sum", "name": "Shart bo'yicha sanash (COUNTIF)",
     "formula": '=COUNTIF(A1:A10,">50")', "description": "Diapazonda 50 dan katta bo'lgan qiymatlar sonini sanaydi.",
     "sample": {"A1": 60, "A2": 20, "A3": 80, "A4": 45}},
    {"id": "averageif-basic", "category": "sum", "name": "Shart bo'yicha o'rtacha (AVERAGEIF)",
     "formula": '=AVERAGEIF(B1:B10,"IT",A1:A10)',
     "description": "B ustuni \"IT\" bo'lgan qatorlardagi A ustunining o'rtachasini hisoblaydi.",
     "sample": {"A1": 4000000, "B1": "IT", "A2": 2500000, "B2": "Sotuv", "A3": 5000000, "B3": "IT"}},
    {"id": "if-basic", "category": "logic", "name": "Oddiy shart (IF)", "formula": '=IF(A1>100,"Ha","Yo\'q")',
     "description": "A1 100 dan katta bo'lsa \"Ha\", aks holda \"Yo'q\" qaytaradi.", "sample": {"A1": 150}},
    {"id": "ifs-basic", "category": "logic", "name": "Ko'p shartli baholash (IFS)",
     "formula": '=IFS(A1>=90,"A\'lo",A1>=70,"Yaxshi",A1>=50,"Qoniqarli",TRUE,"Qoniqarsiz")',
     "description": "Ballga qarab bir nechta shartni ketma-ket tekshirib, mos natijani qaytaradi.",
     "sample": {"A1": 75}},
    {"id": "and-or-basic", "category": "logic", "name": "AND / OR bilan shart",
     "formula": '=IF(AND(A1>50,B1="Faol"),"Mos","Mos emas")',
     "description": "Ikkala shart ham to'g'ri bo'lsagina \"Mos\" qaytaradi.", "sample": {"A1": 60, "B1": "Faol"}},
    {"id": "iferror-basic", "category": "logic", "name": "Xatoni ushlash (IFERROR)",
     "formula": '=IFERROR(A1/B1,"Xato")',
     "description": "Formula xato bersa (masalan, nolga bo'lish), o'rniga \"Xato\" matnini ko'rsatadi. B1 ni 0 ga o'zgartirib sinab ko'ring.",
     "sample": {"A1": 10, "B1": 2}},
    {"id": "vlookup-basic", "category": "lookup", "name": "Vertikal qidiruv (VLOOKUP)",
     "formula": "=VLOOKUP(A1,B1:D10,3,FALSE)",
     "description": "A1 qiymatini B ustunidan qidirib, mos qatordagi 3-ustun (D) qiymatini qaytaradi.",
     "sample": {"A1": "X1", "B1": "X1", "C1": "Noutbuk", "D1": 4500000}},
    {"id": "xlookup-basic", "category": "lookup", "name": "Zamonaviy qidiruv (XLOOKUP)",
     "formula": '=XLOOKUP(A1,B1:B10,D1:D10,"Topilmadi")',
     "description": "VLOOKUP'dan farqli, ustun raqamini sanash shart emas va topilmasa xabar beradi.",
     "sample": {"A1": "X1", "B1": "X1", "D1": 4500000}},
    {"id": "index-match-basic", "category": "lookup", "name": "INDEX + MATCH",
     "formula": "=INDEX(D1:D10,MATCH(A1,B1:B10,0))",
     "description": "VLOOKUP'ning eski, lekin ikki tomonlama qidira oladigan muqobili.",
     "sample": {"A1": "X1", "B1": "X1", "D1": 4500000}},
    {"id": "concatenate-basic", "category": "text", "name": "Matnlarni birlashtirish", "formula": '=A1&" "&B1',
     "description": "Ism va familiyani bitta katakka birlashtiradi (masalan, A1 va B1).",
     "sample": {"A1": "Aziz", "B1": "Karimov"}},
    {"id": "trim-basic", "category": "text", "name": "Ortiqcha bo'shliqni olib tashlash (TRIM)",
     "formula": "=TRIM(A1)", "description": "Matn boshi, oxiri va o'rtasidagi ortiqcha bo'shliqlarni tozalaydi.",
     "sample": {"A1": "  Aziz   Karimov  "}},
    {"id": "left-right-basic", "category": "text", "name": "Belgilarni ajratib olish (LEFT/RIGHT)",
     "formula": "=LEFT(A1,4)",
     "description": "Matnning chap tomonidan berilgan sondagi belgini oladi (masalan, yil: 2026-05 dan \"2026\").",
     "sample": {"A1": "2026-05"}},
    {"id": "upper-lower-basic", "category": "text", "name": "Katta/kichik harf (UPPER/LOWER)",
     "formula": "=UPPER(A1)", "description": "Matnni katta harflarga o'zgartiradi.", "sample": {"A1": "toshkent"}},
    {"id": "today-basic", "category": "date", "name": "Bugungi sana", "formula": "=TODAY()",
     "description": "Kompyuterdagi joriy sanani qaytaradi (parametrsiz).", "sample": {}},
    {"id": "datedif-basic", "category": "date", "name": "Ikki sana orasidagi farq",
     "formula": '=DATEDIF(A1,B1,"D")', "description": "A1 va B1 sanalari orasidagi kunlar sonini hisoblaydi.",
     "sample": {"A1": "2026-01-01", "B1": "2026-03-01"}},
    {"id": "year-month-basic", "category": "date", "name": "Yil va oyni ajratib olish", "formula": "=YEAR(A1)",
     "description": "Sana katagidan faqat yilni ajratib oladi (MONTH va DAY ham shu tarzda ishlaydi).",
     "sample": {"A1": "2026-05-14"}},
    {"id": "workday-basic", "category": "date", "name": "Ish kunlarini qo'shish (WORKDAY)",
     "formula": "=WORKDAY(A1,10)",
     "description": "A1 sanasidan boshlab 10 ish kuni keyingi sanani topadi (dam olish kunlarisiz).",
     "sample": {"A1": "2026-01-05"}},
    {"id": "percentage-basic", "category": "finance", "name": "Foizni hisoblash", "formula": "=(A1-B1)/B1",
     "description": "Ikki qiymat orasidagi foizli o'sish/pasayishni hisoblaydi (natijani % formatga o'tkazing).",
     "sample": {"A1": 120, "B1": 100}},
    {"id": "pmt-basic", "category": "finance", "name": "Kredit oylik to'lovi (PMT)",
     "formula": "=PMT(B1/12,C1,-A1)",
     "description": "A1 kredit summasi, B1 yillik foiz stavkasi, C1 oylar soni bo'yicha oylik to'lovni hisoblaydi.",
     "sample": {"A1": 10000000, "B1": 0.24, "C1": 12}},
    {"id": "round-basic", "category": "finance", "name": "Yaxlitlash (ROUND)", "formula": "=ROUND(A1,2)",
     "description": "Sonni berilgan sondagi kasr xonagacha yaxlitlaydi (masalan, narxlar uchun 2 xona).",
     "sample": {"A1": 1234.5678}},
]

CATEGORIES = [
    {"id": "sum", "label": "Yig'indi va statistika"},
    {"id": "logic", "label": "Shartli (IF)"},
    {"id": "lookup", "label": "Qidiruv (VLOOKUP/XLOOKUP)"},
    {"id": "text", "label": "Matn"},
    {"id": "date", "label": "Sana va vaqt"},
    {"id": "finance", "label": "Moliya"},
]

_LIBRARY_BY_ID = {item["id"]: item for item in FORMULA_LIBRARY}


def find_by_id(formula_id: str) -> Optional[dict]:
    return _LIBRARY_BY_ID.get(formula_id)


def search_library(query: str = "") -> List[dict]:
    q = (query or "").strip().lower()
    if not q:
        return FORMULA_LIBRARY
    return [
        item for item in FORMULA_LIBRARY
        if q in item["name"].lower() or q in item["formula"].lower() or q in item["description"].lower()
    ]


# ─── Per-template evaluators (Cells -> result) ─────────────────────────────────
# Each mirrors the exact range/args baked into that template's formula string.

def _eval_sum_basic(c: Cells): return sum(_num(v) for v in _column(c, "A", 1, 10))
def _eval_average_basic(c: Cells):
    vals = [_num(v) for v in _column(c, "A", 1, 10) if v not in (None, "")]
    return sum(vals) / len(vals) if vals else 0.0
def _eval_sumif_basic(c: Cells): return _sumif(_column(c, "B", 1, 10), "Toshkent", _column(c, "A", 1, 10))
def _eval_sumifs_basic(c: Cells):
    return _sumifs(_column(c, "D", 1, 10), _column(c, "B", 1, 10), "Toshkent", _column(c, "C", 1, 10), ">100")
def _eval_countif_basic(c: Cells): return _countif(_column(c, "A", 1, 10), ">50")
def _eval_averageif_basic(c: Cells): return _averageif(_column(c, "B", 1, 10), "IT", _column(c, "A", 1, 10))
def _eval_if_basic(c: Cells): return "Ha" if _num(c.get("A1")) > 100 else "Yo'q"
def _eval_ifs_basic(c: Cells):
    a1 = _num(c.get("A1"))
    if a1 >= 90: return "A'lo"
    if a1 >= 70: return "Yaxshi"
    if a1 >= 50: return "Qoniqarli"
    return "Qoniqarsiz"
def _eval_and_or_basic(c: Cells):
    return "Mos" if _num(c.get("A1")) > 50 and str(c.get("B1")) == "Faol" else "Mos emas"
def _eval_iferror_basic(c: Cells):
    try:
        b1 = _num(c.get("B1"))
        if b1 == 0:
            return "Xato"
        return _num(c.get("A1")) / b1
    except ZeroDivisionError:
        return "Xato"
def _eval_vlookup_basic(c: Cells):
    return _vlookup(c.get("A1"), [_column(c, "B", 1, 10), _column(c, "C", 1, 10), _column(c, "D", 1, 10)], 3)
def _eval_xlookup_basic(c: Cells):
    return _xlookup(c.get("A1"), _column(c, "B", 1, 10), _column(c, "D", 1, 10), "Topilmadi")
def _eval_index_match_basic(c: Cells):
    return _index_match(c.get("A1"), _column(c, "B", 1, 10), _column(c, "D", 1, 10))
def _eval_concatenate_basic(c: Cells): return f"{c.get('A1', '')} {c.get('B1', '')}"
def _eval_trim_basic(c: Cells): return " ".join(str(c.get("A1", "")).split())
def _eval_left_right_basic(c: Cells): return str(c.get("A1", ""))[:4]
def _eval_upper_lower_basic(c: Cells): return str(c.get("A1", "")).upper()
def _eval_today_basic(_: Cells): return date.today().isoformat()
def _eval_datedif_basic(c: Cells): return _datedif(c.get("A1"), c.get("B1"), "D")
def _eval_year_month_basic(c: Cells):
    d = _parse_date(c.get("A1"))
    return d.year if d else "#VALUE!"
def _eval_workday_basic(c: Cells):
    d = _parse_date(c.get("A1"))
    if not d:
        return "#VALUE!"
    added, day = 0, d
    from datetime import timedelta
    while added < 10:
        day += timedelta(days=1)
        if day.weekday() < 5:
            added += 1
    return day.isoformat()
def _eval_percentage_basic(c: Cells):
    b1 = _num(c.get("B1"))
    return (_num(c.get("A1")) - b1) / b1 if b1 else "#DIV/0!"
def _eval_pmt_basic(c: Cells):
    return _pmt(_num(c.get("B1")) / 12, _num(c.get("C1")), -_num(c.get("A1")))
def _eval_round_basic(c: Cells): return round(_num(c.get("A1")), 2)

_EVALUATORS: Dict[str, Callable[[Cells], object]] = {
    "sum-basic": _eval_sum_basic, "average-basic": _eval_average_basic, "sumif-basic": _eval_sumif_basic,
    "sumifs-basic": _eval_sumifs_basic, "countif-basic": _eval_countif_basic,
    "averageif-basic": _eval_averageif_basic, "if-basic": _eval_if_basic, "ifs-basic": _eval_ifs_basic,
    "and-or-basic": _eval_and_or_basic, "iferror-basic": _eval_iferror_basic,
    "vlookup-basic": _eval_vlookup_basic, "xlookup-basic": _eval_xlookup_basic,
    "index-match-basic": _eval_index_match_basic, "concatenate-basic": _eval_concatenate_basic,
    "trim-basic": _eval_trim_basic, "left-right-basic": _eval_left_right_basic,
    "upper-lower-basic": _eval_upper_lower_basic, "today-basic": _eval_today_basic,
    "datedif-basic": _eval_datedif_basic, "year-month-basic": _eval_year_month_basic,
    "workday-basic": _eval_workday_basic, "percentage-basic": _eval_percentage_basic,
    "pmt-basic": _eval_pmt_basic, "round-basic": _eval_round_basic,
}


def evaluate(formula_id: str, cells: Cells) -> Tuple[bool, object]:
    """Run a library template against a cell map. Returns (ok, result_or_error)."""
    fn = _EVALUATORS.get(formula_id)
    if not fn:
        return False, "Noma'lum formula."
    try:
        return True, fn(cells)
    except Exception as e:  # defensive: bad/missing input should never crash the bot
        return False, f"Xato: {e}"
