"""JSON data model -> .bpp text (SPEC §1-§6)."""

from __future__ import annotations

import re
from collections import Counter

from .estimate import est_tokens
from .lexer import (MD_HEADER, NUM_RE, Ref, block_ok, fmt_inline, fmt_key, fmt_scalar, fmt_seg,
                    is_scalar, jstr)

HEADER = "bpp4"
PRIMER_LONG = (
    "# bpp4 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.\n"
    "# k[N]{a b.c d}: N rows, values space-separated in column order, b.c = key c inside object b, "
    "last column = rest of line;\n"
    "# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids (a bare > keeps "
    "the table's key), >kids{...} gives them their own columns. {a,b}: comma rows. k[N]: N '- ' items. "
    "\"...\" = JSON string. |N = the next N lines as a string. *n = &n value."
)
_NL_MERGE = re.compile(r"[!-/:-@\[-`{-~]\n|\n\n")
_TABLE_HEAD = re.compile(r"\[[0-9]+\](\{.*)$")
CHILD_KEYS = ("steps", "children", "subtasks", "tasks", "items", "nodes")
MIN_REF_LEN = 8


class _Raw(str):
    """A line of a `|N` block (never scanned for syntax)."""


def encode(data, *, primer: bool | str = False, refs: bool = True,
           keep_order: bool = False) -> str:
    """Encode a JSON-compatible value as .bpp text.

    primer: add a one-line (True) or three-line ("long") explanation comment.
        The one-line primer only explains the syntax the output uses.
    refs: allow the &n/*n dictionary for repeated long strings.
    keep_order: never reorder object keys (disables the row-table variant that
        moves its free-text column last).
    """
    return _assemble(*_body(data, refs, keep_order), primer, markdown=False)


def encode_md(text: str, *, primer: bool = False, refs: bool = True,
              keep_order: bool = False) -> str:
    """Encode a Markdown document (SPEC §7).

    The document's tree (`md_to_tree`) is encoded as usual, with the Markdown
    primer if asked for.  If the source text itself, behind a `bpp4 md` header
    (SPEC §7.2), is estimated to be shorter, that is returned instead: it
    decodes to the same tree, and `--to md` gives back the text unchanged.
    """
    from .markdown import md_to_tree

    compact = _assemble(*_body(md_to_tree(text), refs, keep_order), primer, markdown=True)
    raw = f"{MD_HEADER}\n{text}"
    return raw if est_tokens(raw) < est_tokens(compact) else compact


def _body(data, refs, keep_order):
    defs: list[str] = []
    if refs:
        data, defs = _extract_refs(data)
    enc = _Enc(keep_order)
    lines: list[str] = []
    for i, s in enumerate(defs):
        enc.line(lines, f"&{i} {enc.scalar(s)}")
    lines.extend(enc.root(data))
    return lines, bool(defs)


def _assemble(lines, has_refs, primer, markdown) -> str:
    out = [HEADER]
    if primer == "long":
        out.append(PRIMER_LONG)
    elif primer:
        out.append(_primer(lines, has_refs, markdown))
    out.extend(lines)
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------- primer

def _features(lines, has_refs) -> set:
    """The syntax a body uses, from its non-block lines."""
    f = {"ref"} if has_refs else set()
    for ln in lines:
        if isinstance(ln, _Raw):
            f.add("block")
            continue
        if '"' in ln:
            f.add("quote")
        m = _TABLE_HEAD.search(ln)
        if not m:
            continue
        spec = m.group(1)
        if " " not in spec and "," in spec and ">" not in spec:
            f.add("comma")
            continue
        f.add("table")
        f.update(k for k, pat in (("keyed", r"\?="), ("opt", r"\?(?!=)"), ("dotted", r"[^\s{]\.[^\s}]"),
                                  ("child", r"\}>[^{\s]"), ("same", r"\}>(?:\{|$)"),
                                  ("own", r"\}>[^{\s]*\{"), ("status", r"[{ ]status\?"),
                                  ("note?", r"[{ ]note\?(?!=)"), ("note?=", r"[{ ]note\?="))
                 if re.search(pat, spec))
    return f


def _primer(lines, has_refs, markdown) -> str:
    f = _features(lines, has_refs)
    if markdown:
        head = "# bpp4 Markdown:"
        rows = ["steps[N]{cols} = N headings/list items, cols in order, title = rest of line, "
                "indented rows = sub-items" + (" (>{...}: own cols)" if "own" in f else "")]
        if "status" in f:
            rows.append("status: todo/done/doing/cancelled (- none)")
        note = [x for k, x in (("note?", "note?"), ("note?=", "note=")) if k in f]
        if note:
            rows.append("/".join(note) + " its text" + (" (- none)" if "note?" in f else ""))
    else:
        head = "# bpp4: JSON as 'key value' lines, 1-space indent nests."
        rows = []
        if "table" in f:
            rows.append("k[N]{a b.c}: N rows, values in column order (b.c = key c of b), last one = rest of line"
                        if "dotted" in f else "k[N]{a b}: N rows, values in column order, last one = rest of line")
        if "comma" in f:
            rows.append("k[N]{a,b}: N comma rows")
        if "opt" in f:
            rows.append("x? optional (- = absent)")
        if "keyed" in f:
            rows.append("x?= as x=v")
        if "child" in f or "same" in f:
            rows.append({(True, False): ">k: indented rows are k",
                         (False, True): ">: indented rows are children (same key)",
                         (True, True): ">k: indented rows are k (bare >: same key)"}[
                             ("child" in f, "same" in f)])
    vals = [txt for k, txt in (("quote", '"..." = JSON string'), ("block", "|N = the next N lines"),
                               ("ref", "*n = &n")) if k in f]
    out = head
    if rows:
        out += " " + "; ".join(rows) + "."
    if vals:
        out += " " + ", ".join(vals) + "."
    return out


# ------------------------------------------------------------ block strings

def block_gain(s: str) -> int:
    """Estimated tokens saved by writing s (block_ok) as a `|N` block instead of a JSON string."""
    # A raw newline merges with the punctuation before it (`):\n\n`); an escaped
    # one does not, which the estimator alone misses (calibrated on o200k and claude2).
    return (est_tokens(" " + jstr(s)) + len(_NL_MERGE.findall(s))
            - est_tokens(f" |{s.count(chr(10)) + 1}") - est_tokens(s + "\n"))


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
        self.pending: list[str] = []  # block lines of the line being built

    # A string value that is cheaper as a `|N` block is written as `|N`; its
    # lines wait in `pending` until `line()` has written the line it belongs to.
    def scalar(self, v, ctx: str = "value", strmode: bool = False) -> str:
        if isinstance(v, str) and block_ok(v) and block_gain(v) >= 0:
            self.pending.extend(_Raw(x) for x in v.split("\n"))
            return f"|{v.count(chr(10)) + 1}"
        return fmt_scalar(v, ctx, strmode)

    def inline(self, v, ctx: str = "value", strmode: bool = False) -> str | None:
        return self.scalar(v, ctx, strmode) if is_scalar(v) else fmt_inline(v, ctx, strmode)

    def line(self, out: list[str], text: str):
        out.append(text)
        out.extend(self.pending)
        self.pending = []

    def root(self, v) -> list[str]:
        if isinstance(v, str):
            lines: list[str] = []
            text = self.scalar(v)  # a block, or else always a JSON string (SPEC §4.5)
            self.line(lines, text if self.pending else jstr(v))
            return lines
        if isinstance(v, dict) and v:
            lines = []
            for k, x in v.items():
                self.entry(fmt_key(k), x, 0, lines)
            return lines
        inl = fmt_inline(v)
        if inl is not None:
            return [inl]
        return self.array("", v, 0)

    def entry(self, key: str, v, d: int, out: list[str]):
        pad = " " * d
        inl = self.inline(v)
        if inl is not None:
            self.line(out, f"{pad}{key} {inl}")
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
        cands = []
        for c in [self.table(key, arr, d), *self.outlines(key, arr, d, keep_order=True),
                  *([] if self.keep_order else self.outlines(key, arr, d))]:
            if c and c not in cands:
                cands.append(c)
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
        head = ",".join(fmt_seg(c) + (":str" if s else "") for c, s in zip(cols, smode))
        pad = " " * d
        lines = [f"{pad}{key}[{len(arr)}]{{{head}}}"]
        for x in arr:
            self.line(lines, pad + ",".join(self.scalar(x[c], "cell", s) for c, s in zip(cols, smode)))
        return lines

    def outlines(self, key, arr, d, keep_order=False):
        out = []
        for spec in _plans(arr, keep_order):
            lines = [f"{' ' * d}{key}[{len(arr)}]{spec.header(key)}"]
            self.render(arr, spec, d, lines)
            out.append(lines)
        return out

    def cell(self, v, ctx, strmode):
        if isinstance(v, list):
            return "[" + ",".join(fmt_scalar(y, "list", strmode) for y in v) + "]"
        if v == {}:
            return "{}"
        return self.scalar(v, ctx, strmode)

    def render(self, arr, spec, depth, lines):
        last = spec.order[-1]
        for x in arr:
            flat = dict(_flat_node(x, spec.child))
            parts = []
            for p in spec.order[:-1]:
                if p not in spec.keyed:
                    parts.append(self.cell(flat[p], "pos", spec.smode[p]) if p in flat else "-")
            for p in spec.order[:-1]:
                if p in spec.keyed and p in flat:
                    parts.append(f"{_fmt_path(p)}={self.cell(flat[p], 'pos', spec.smode[p])}")
            kids = x.get(spec.child) if spec.child is not None else None
            if spec.child is not None and spec.child in x and not kids:
                parts.append(f"{fmt_seg(spec.child)}=[]")
            parts.append(self.cell(flat[last], "last", spec.smode[last]))
            self.line(lines, " " * depth + " ".join(parts))
            if kids:
                self.render(kids, spec.sub or spec, depth + 1, lines)

    def items(self, key, arr, d):
        pad = " " * d
        lines = [f"{pad}{key}[{len(arr)}]"]
        for x in arr:
            inl = self.inline(x, "item")
            if inl is not None:
                self.line(lines, f"{pad}- {inl}")
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


# ------------------------------------------------------------- row tables
# A row table (SPEC §4.3) is described by a _Spec: its columns are paths into
# the row object (('customer', 'name') is written customer.name), and it may
# have one child key whose rows are indented under their parent, either with
# the same spec (a tree, `>steps`) or with their own (`>items{...}`).

_ABSENT = object()


class _Spec:
    def __init__(self, order, required, keyed, smode, child, sub):
        self.order, self.required, self.keyed = order, required, keyed
        self.smode, self.child, self.sub = smode, child, sub

    def header(self, key: str) -> str:
        """`{cols}>child...`; `key` is the (formatted) key the rows are stored under."""
        cols = " ".join(
            _fmt_path(p) + ("?=" if p in self.keyed else "" if p in self.required else "?")
            + (":str" if self.smode[p] else "") for p in self.order)
        out = "{" + cols + "}"
        if self.child is not None:
            child = fmt_seg(self.child)
            # bpp4: a bare `>` means the children are stored under the same key
            out += ">" + ("" if child == key else child)
            if self.sub:
                out += self.sub.header(child)
        return out


def _fmt_path(p) -> str:
    return ".".join(fmt_seg(k) for k in p)


def _cellable(v) -> bool:
    return is_scalar(v) or v == {} or (isinstance(v, list) and all(is_scalar(y) for y in v))


def _flat_node(x, skip):
    """[(path, value)] of a row object with nested objects flattened, or None."""
    out = []

    def go(path, v):
        if isinstance(v, dict) and v:
            return all(go(path + (k,), y) for k, y in v.items())
        if not _cellable(v):
            return False
        out.append((path, v))
        return True

    for k, v in x.items():
        if k != skip and not go((k,), v):
            return None
    return out


def _is_rows(v) -> bool:
    return isinstance(v, list) and all(isinstance(y, dict) and y for y in v)


def _plan(arr, keep_order):
    specs = _plans(arr, keep_order)
    return specs[0] if specs else None


def _plans(arr, keep_order):
    """Lossless row-table specs for arr, best guess first: for the first usable child
    key, a tree (same columns on every level) and a child table (the top level gets
    its own columns, e.g. a positional column that is only frequent there)."""
    if not arr or not all(isinstance(x, dict) and x for x in arr):
        return []
    seen = set()
    for ck in list(CHILD_KEYS) + [k for x in arr for k in x]:
        if ck in seen:
            continue
        seen.add(ck)
        if not any(x.get(ck) for x in arr) or not all(ck not in x or _is_rows(x[ck]) for x in arr):
            continue
        specs = []
        nodes = _tree_nodes(arr, ck)
        if nodes is not None:
            specs.append(_plan_cols(arr, nodes, ck, None, keep_order))
        sub = _plan([y for x in arr for y in x.get(ck) or []], keep_order)
        if sub is not None:
            specs.append(_plan_cols(arr, arr, ck, sub, keep_order))
        specs = [sp for sp in specs if sp is not None]
        if specs:
            return specs
    spec = _plan_cols(arr, arr, None, None, keep_order)
    return [spec] if spec is not None else []


def _plan_cols(arr, nodes, child, sub, keep_order):
    flats = []
    for x in nodes:
        f = _flat_node(x, child)
        if f is None:
            return None
        flats.append(dict(f))
    cols = []
    seen = set()
    for f in flats:
        for p in f:
            if p not in seen:
                seen.add(p)
                cols.append(p)
    if any(p[:i] in seen for p in cols for i in range(1, len(p))):
        return None  # a key is an object in one row and a value in another
    required = [p for p in cols if all(p in f for f in flats)]
    if not required or (len(cols) == 1 and child is None):
        return None  # one plain column would read back as a comma table

    def text_score(p):
        # A dictionary reference stands for a (long) string, so it counts as text.
        vals = [f[p] for f in flats]
        if not all(isinstance(v, (str, Ref)) for v in vals):
            return (0, 0)
        return (1, sum(v.count(" ") + 1 if isinstance(v, str) else 1 for v in vals))

    if keep_order:
        if cols[-1] not in required:
            return None
        rest = cols[-1]
    else:
        rest = max(required, key=text_score)
    order = [p for p in cols if p != rest] + [rest]
    smode = {p: _str_col(f[p] for f in flats if p in f) for p in order}
    optional = [p for p in order if p not in required]
    # An optional column is positional with '-' for "absent" when that is
    # cheaper than writing `name=` on every row that has it.
    keyed = set()
    for p in optional:
        present = sum(p in f for f in flats)
        if (len(flats) - present) * est_tokens(" -") >= present * est_tokens(f" {_fmt_path(p)}="):
            keyed.add(p)
    spec = _Spec(order, set(required), keyed, smode, child, sub)
    if keep_order and not all(_ordered_eq(_rebuild(x, spec), x) for x in arr):
        return None
    return spec


def _rebuild(x, spec):
    """The object the decoder builds from x's row (to check key order)."""
    flat = dict(_flat_node(x, spec.child))
    out: dict = {}
    for p in spec.order:
        if p in flat:
            o = out
            for k in p[:-1]:
                o = o.setdefault(k, {})
            o[p[-1]] = flat[p]
    if spec.child is not None and spec.child in x:
        out[spec.child] = [_rebuild(y, spec.sub or spec) for y in x[spec.child]]
    return out


def _ordered_eq(a, b) -> bool:
    if isinstance(a, dict):
        return (isinstance(b, dict) and list(a) == list(b)
                and all(_ordered_eq(a[k], b[k]) for k in a))
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(map(_ordered_eq, a, b))
    return a is b or a == b
