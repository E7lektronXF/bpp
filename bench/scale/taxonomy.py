"""Classify a wrong answer, to tell which bpp feature (if any) caused it.

    pointer            the answer is a dictionary reference (`*12`, or the bare `12` of a
                       value the encoding interned) instead of the value
    column_shift       the value of another column of the right row
    row_shift          the right column of a neighbouring row (up to 3 rows away; for a
                       child table, another child of the right row)
    count_off          a count or aggregate that is a number, but the wrong one
    refused_truncated  no answer, a refusal, or the output limit was hit
    other              anything else

The checks run in that order; the first that matches wins.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_qa import _norm, _num, grade  # noqa: E402

CATEGORIES = ("pointer", "column_shift", "row_shift", "count_off", "refused_truncated", "other")
CUT = ("length", "max_tokens", "too_large", "refusal", "content_filter", "skipped")
NEAR = 3
_REFUSAL = re.compile(r"\b(can ?not|can't|unable|not (found|available|present|listed|provided|"
                      r"specified|given)|no such|unknown|n/a|insufficient)\b", re.I)


def _same(answer: str, value) -> bool:
    if isinstance(value, bool):
        return grade(answer, value, "bool")
    if isinstance(value, (int, float)):
        return grade(answer, value, "num")
    if isinstance(value, list):
        return grade(answer, value, "list") or (len(value) == 1 and grade(answer, value[0], "str"))
    return grade(answer, value, "str")


def _only_index_differs(a: tuple, b: tuple) -> bool:
    return len(a) == len(b) and all(x == y or (isinstance(x, int) and isinstance(y, int))
                                    for x, y in zip(a, b))


def classify(answer: str | None, q, rows: list[dict], refs: dict | None = None,
             stop: str | None = None) -> tuple[str, str]:
    """(category, detail) for a wrong answer.

    q: a questions.Q (uses expected, qtype, row, col); rows: the payload's rows as
    questions.flat() dicts; refs: {interned string: n} of the encoding shown to the
    model (empty for formats without a dictionary).
    """
    refs = refs or {}
    a = _norm(answer) if answer is not None else ""
    if not a or stop in CUT:
        return "refused_truncated", stop or "empty"
    if refs:
        # _norm strips Markdown asterisks, so look for `*n` in the raw answer
        m = re.fullmatch(r"\*(\d+)\**", answer.strip().strip("`'\". "))
        if m:
            return "pointer", f"*{m.group(1)}"
        m = re.fullmatch(r"&?(\d+)", a)
        if m and isinstance(q.expected, str) and _num(q.expected) is None:
            n = int(m.group(1))
            if n in refs.values():
                return "pointer", ("own index" if refs.get(q.expected) == n else "index") + f" {n}"
    if q.qtype in ("count", "aggregate"):
        if _num(a) is not None:
            return "count_off", f"{a} vs {q.expected}"
        return ("refused_truncated", "refusal") if _REFUSAL.search(a) else ("other", "")
    if q.row is not None and q.col is not None:
        row = rows[q.row]
        for p, v in row.items():
            if p != q.col and not _only_index_differs(p, q.col) and _same(a, v):
                return "column_shift", ".".join(map(str, p))
        for p, v in row.items():
            if p != q.col and _only_index_differs(p, q.col) and _same(a, v):
                return "row_shift", "child " + ".".join(map(str, p))
        for d in range(1, NEAR + 1):
            for i in (q.row - d, q.row + d):
                if 0 <= i < len(rows) and q.col in rows[i] and _same(a, rows[i][q.col]):
                    return "row_shift", f"{i - q.row:+d}"
    if _REFUSAL.search(a):
        return "refused_truncated", "refusal"
    return "other", ""


def refs_of(text: str) -> dict:
    """{value: n} of the `&n value` definitions of a bpp text (empty if none)."""
    from bpp import decode

    out = {}
    for line in text.splitlines()[1:]:
        if line.startswith("#"):
            continue
        m = re.match(r"&(\d+) ", line)
        if not m:
            break
        # decode the definition as the decoder would (quotes, escapes)
        out[decode(f"bpp4\nv {line[m.end():]}\n")["v"]] = int(m.group(1))
    return out
