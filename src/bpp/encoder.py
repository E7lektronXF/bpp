"""JSON data model -> .bpp text (SPEC §1-§6)."""

from __future__ import annotations

from collections import Counter

from .estimate import est_tokens
from .lexer import NUM_RE, Ref, fmt_inline, fmt_key, fmt_scalar, is_scalar, jstr

HEADER = "bpp2"
PRIMER = ("# bpp2: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows of values "
          "in column order, last column = rest of line; x? = optional ('-' if absent), "
          "x?= columns appear as x=v. \"...\" = JSON string, *n = &n.")
PRIMER_LONG = (
    "# bpp2 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.\n"
    "# k[N]{a b c}: N rows, values space-separated in column order, last column = rest of line;\n"
    "# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids. {a,b}: comma rows. "
    "k[N]: N '- ' items. \"...\" = JSON string. *n = &n value."
)
CHILD_KEYS = ("steps", "children", "subtasks", "tasks", "items", "nodes")
MIN_REF_LEN = 8


def encode(data, *, primer: bool | str = False, refs: bool = True,
           keep_order: bool = False) -> str:
    """Encode a JSON-compatible value as .bpp text.

    primer: add a one-line (True) or three-line ("long") explanation comment.
    refs: allow the &n/*n dictionary for repeated long strings.
    keep_order: never reorder object keys (disables the row-table variant that
        moves its free-text column last).
    """
    out = [HEADER]
    if primer:
        out.append(PRIMER_LONG if primer == "long" else PRIMER)
    defs: list[str] = []
    if refs:
        data, defs = _extract_refs(data)
    for i, s in enumerate(defs):
        out.append(f"&{i} {fmt_scalar(s)}")
    out.extend(_Enc(keep_order).root(data))
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ dictionary

def _walk_strings(v, cnt: Counter):
    if isinstance(v, str):
        cnt[v] += 1
    elif isinstance(v, dict):
        for x in v.values():
            _walk_strings(x, cnt)
    elif isinstance(v, list):
        for x in v:
            _walk_strings(x, cnt)


def _extract_refs(data):
    if isinstance(data, str):
        return data, []
    cnt: Counter = Counter()
    _walk_strings(data, cnt)
    cands = []
    for s, n in cnt.items():
        if n < 2 or len(s) < MIN_REF_LEN:
            continue
        cost = est_tokens(" " + fmt_scalar(s))
        gain = n * cost - est_tokens(f"&10 {fmt_scalar(s)}\n") - n * est_tokens(" *10")
        if gain > 0:
            cands.append((gain, s))
    if not cands:
        return data, []
    cands.sort(key=lambda t: (-t[0], t[1]))
    table = {s: Ref(i) for i, (_, s) in enumerate(cands)}

    def sub(v):
        if isinstance(v, str):
            return table.get(v, v)
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        if isinstance(v, list):
            return [sub(x) for x in v]
        return v

    return sub(data), [s for _, s in cands]


# ---------------------------------------------------------------------- body

def _str_col(values) -> bool:
    """Use `:str` when every non-null value is a string and it saves quotes."""
    flat = []
    for v in values:
        if isinstance(v, list):
            flat.extend(v)
        else:
            flat.append(v)
    strs = [v for v in flat if v is not None and not isinstance(v, Ref)]
    return bool(strs) and all(isinstance(v, str) for v in strs) and any(
        NUM_RE.fullmatch(v) for v in strs)


class _Enc:
    def __init__(self, keep_order: bool = False):
        self.keep_order = keep_order

    def root(self, v) -> list[str]:
        if isinstance(v, str):
            return [jstr(v)]
        if isinstance(v, dict) and v:
            lines: list[str] = []
            for k, x in v.items():
                self.entry(fmt_key(k), x, 0, lines)
            return lines
        inl = fmt_inline(v)
        if inl is not None:
            return [inl]
        return self.array("", v, 0)

    def entry(self, key: str, v, d: int, out: list[str]):
        pad = " " * d
        inl = fmt_inline(v)
        if inl is not None:
            out.append(f"{pad}{key} {inl}")
        elif isinstance(v, dict):
            out.append(pad + key)
            for k, x in v.items():
                self.entry(fmt_key(k), x, d + 1, out)
        else:
            out.extend(self.array(key, v, d))

    # --- arrays -----------------------------------------------------------
    def array(self, key: str, arr: list, d: int) -> list[str]:
        # Candidates in order of preference; ties go to the earlier one, so
        # order-preserving layouts win over the one that moves a column.
        cands = [c for c in (self.table(key, arr, d),
                             self.outline(key, arr, d, keep_order=True),
                             None if self.keep_order else self.outline(key, arr, d))
                 if c]
        if not cands or len(arr) <= 2:
            cands.append(self.items(key, arr, d))
        if len(cands) == 1:
            return cands[0]
        return min(cands, key=lambda ls: est_tokens("\n".join(ls)))

    def table(self, key, arr, d):
        if not all(isinstance(x, dict) and x for x in arr):
            return None
        cols = list(arr[0])
        for x in arr:
            if list(x) != cols or not all(is_scalar(v) for v in x.values()):
                return None
        smode = [_str_col(x[c] for x in arr) for c in cols]
        head = ",".join(fmt_key(c) + (":str" if s else "") for c, s in zip(cols, smode))
        pad = " " * d
        lines = [f"{pad}{key}[{len(arr)}]{{{head}}}"]
        for x in arr:
            lines.append(pad + ",".join(fmt_scalar(x[c], "cell", s) for c, s in zip(cols, smode)))
        return lines

    def outline(self, key, arr, d, keep_order=False):
        if not arr or not all(isinstance(x, dict) and x for x in arr):
            return None
        child, nodes = None, None
        seen = set()
        for ck in list(CHILD_KEYS) + [k for x in arr for k in x]:
            if ck in seen or not any(x.get(ck) for x in arr):
                continue
            seen.add(ck)
            nodes = _tree_nodes(arr, ck)
            if nodes is not None:
                child = ck
                break
        if child is None:
            nodes = arr
        cols: list[str] = []
        for x in nodes:
            for k in x:
                if k != child and k not in cols:
                    cols.append(k)
        for x in nodes:
            for k, v in x.items():
                if k != child and not (is_scalar(v) or v == {} or
                                       (isinstance(v, list) and all(is_scalar(y) for y in v))):
                    return None
        if keep_order:
            for x in nodes:
                ks = list(x)
                if child in x:
                    if ks[-1] != child:
                        return None
                    ks.pop()
                if ks != [c for c in cols if c in x]:
                    return None
        required = [c for c in cols if all(c in x for x in nodes)]
        if not required:
            return None
        if len(cols) == 1 and not child:
            return None  # would read back as a one-column comma table

        def text_score(c):
            vals = [x[c] for x in nodes]
            if not all(isinstance(v, str) for v in vals):
                return (0, 0)
            return (1, sum(v.count(" ") + 1 for v in vals))
        if keep_order:
            if cols[-1] not in required:
                return None
            rest = cols[-1]
        else:
            rest = max(required, key=text_score)
            if rest == cols[-1]:
                return None  # identical to the keep_order variant
        order = [c for c in cols if c != rest] + [rest]
        smode = {c: _str_col(x[c] for x in nodes if c in x) for c in order}
        optional = {c for c in order if c not in required}
        # An optional column is positional with '-' for "absent" when that is
        # cheaper than writing `name=` on every row that has it (SPEC §4.3).
        keyed = set()
        for c in optional:
            present = sum(c in x for x in nodes)
            if (len(nodes) - present) * est_tokens(" -") >= present * est_tokens(f" {fmt_key(c)}="):
                keyed.add(c)
        head = " ".join(fmt_key(c) + ("?=" if c in keyed else "?" if c in optional else "")
                        + (":str" if smode[c] else "") for c in order)
        lines = [f"{' ' * d}{key}[{len(arr)}]{{{head}}}" + (f">{fmt_key(child)}" if child else "")]

        def row(x, depth):
            parts = []
            for c in order[:-1]:
                if c not in keyed:
                    parts.append(self._cell(x[c], "pos", smode[c]) if c in x else "-")
            for c in order[:-1]:
                if c in keyed and c in x:
                    parts.append(f"{fmt_key(c)}={self._cell(x[c], 'pos', smode[c])}")
            if child and child in x and not x[child]:
                parts.append(f"{fmt_key(child)}=[]")
            parts.append(self._cell(x[rest], "last", smode[rest]))
            lines.append(" " * depth + " ".join(parts))
            for y in (x.get(child) or []) if child else []:
                row(y, depth + 1)

        for x in arr:
            row(x, d)
        return lines

    @staticmethod
    def _cell(v, ctx, strmode):
        if isinstance(v, list):
            return "[" + ",".join(fmt_scalar(y, "list", strmode) for y in v) + "]"
        if v == {}:
            return "{}"
        return fmt_scalar(v, ctx, strmode)

    def items(self, key, arr, d):
        pad = " " * d
        lines = [f"{pad}{key}[{len(arr)}]"]
        for x in arr:
            inl = fmt_inline(x, "item")
            if inl is not None:
                lines.append(f"{pad}- {inl}")
                continue
            if isinstance(x, dict):
                sub: list[str] = []
                first = True
                for k, v in x.items():
                    self.entry(fmt_key(k), v, d + 1, sub)
                    if first:
                        sub[0] = f"{pad}- " + sub[0][d + 1:]
                        first = False
                lines.extend(sub)
            else:  # nested non-inline list
                sub = self.array("", x, d + 1)
                sub[0] = f"{pad}- " + sub[0][d + 1:]
                lines.extend(sub)
        return lines


def _tree_nodes(arr, child):
    """All nodes of a tree whose recursion key is `child`, or None if not a tree."""
    nodes = []
    stack = list(reversed(arr))
    while stack:
        x = stack.pop()
        if not isinstance(x, dict) or not x:
            return None
        nodes.append(x)
        if child in x:
            kids = x[child]
            if not isinstance(kids, list):
                return None
            stack.extend(reversed(kids))
    return nodes
