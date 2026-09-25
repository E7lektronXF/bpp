""".bpp text -> JSON data model (SPEC §1-§6)."""

from __future__ import annotations

import re

from .lexer import BppError, Cursor

_COUNT_RE = re.compile(r"\[(\d+)\]")


def _header(text: str):
    """`[N]` or `[N]{...}` at the start of text -> (N, rest) or None."""
    m = _COUNT_RE.match(text)
    if not m or (m.end() < len(text) and text[m.end()] != "{"):
        return None
    return int(m.group(1)), text[m.end():]


class _Spec:
    """Parsed column spec of a table or row table (see encoder._Spec)."""

    def __init__(self, cols, delim, child, sub):
        self.cols, self.delim, self.child, self.sub = cols, delim, child, sub
        self.order = [c[0] for c in cols]
        self.smode = {c[0]: c[3] for c in cols}
        self.optional = {c[0] for c in cols if c[1]}
        self.keyed = {c[0] for c in cols if c[2]}
        self.positional = [p for p in self.order[:-1] if p not in self.keyed]


def _set_path(obj: dict, path: tuple, v, line):
    for k in path[:-1]:
        nxt = obj.setdefault(k, {})
        if not isinstance(nxt, dict):
            raise BppError(f"column {'.'.join(path)!r} conflicts with {k!r}", line)
        obj = nxt
    obj[path[-1]] = v


class _Line:
    __slots__ = ("depth", "text", "no")

    def __init__(self, depth, text, no):
        self.depth, self.text, self.no = depth, text, no


def decode(text: str):
    """Decode .bpp text into Python/JSON values."""
    raw = text.split("\n")
    lines: list[_Line] = []
    version = 0
    for no, ln in enumerate(raw, 1):
        if ln.endswith("\r"):
            ln = ln[:-1]
        stripped = ln.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if not version:
            if stripped not in ("bpp1", "bpp2", "bpp3"):
                raise BppError("missing 'bpp3' header", no)
            version = int(stripped[3])
            continue
        lines.append(_Line(len(ln) - len(stripped), stripped, no))
    if not version:
        raise BppError("missing 'bpp3' header")
    return _Dec(lines, version).document()


class _Dec:
    def __init__(self, lines: list[_Line], version: int = 2):
        self.L = lines
        self.version = version
        self.i = 0
        self.refs: list = []

    # -- helpers ---------------------------------------------------------------
    def cur(self, ln: _Line, start: int = 0) -> Cursor:
        c = Cursor(ln.text, self.refs, ln.no)
        c.i = start
        return c

    def depth_at(self, i: int) -> int:
        return self.L[i].depth if i < len(self.L) else -1

    # -- document ----------------------------------------------------------------
    def document(self):
        while self.i < len(self.L) and self.L[self.i].text.startswith("&"):
            ln = self.L[self.i]
            m = re.match(r"&(\d+) ", ln.text)
            if not m or ln.depth or int(m.group(1)) != len(self.refs):
                raise BppError("bad dictionary definition", ln.no)
            c = self.cur(ln, m.end())
            v = c.value()
            if not isinstance(v, str) or not c.eof():
                raise BppError("dictionary value must be a string", ln.no)
            self.refs.append(v)
            self.i += 1
        if self.i >= len(self.L):
            raise BppError("empty document")
        first = self.L[self.i]
        if first.depth:
            raise BppError("unexpected indentation", first.no)
        if self.i == len(self.L) - 1:
            v = self._root_inline(first)
            if v is not _NO:
                self.i += 1
                return v
        if first.text.startswith("["):
            v = self.keyless(first, 0)
        else:
            v = self.object(0)
        if self.i < len(self.L):
            raise BppError("unexpected content", self.L[self.i].no)
        return v

    def _root_inline(self, ln: _Line):
        c = self.cur(ln)
        ch = c.peek()
        try:
            if ch == '"':
                v = c.jstring()
            elif ch in "[{" or ch == "*":
                v = c.value(stops=" ")
            else:
                v = c.token(" ")
                if isinstance(v, str):
                    return _NO
        except BppError:
            return _NO
        return v if c.eof() else _NO

    # -- objects -----------------------------------------------------------------
    def object(self, d: int) -> dict:
        obj: dict = {}
        while self.i < len(self.L):
            ln = self.L[self.i]
            if ln.depth < d:
                break
            if ln.depth > d:
                raise BppError("unexpected indentation", ln.no)
            if ln.text.startswith("- ") or ln.text == "-":
                raise BppError("list item outside a list", ln.no)
            self.i += 1
            k, v = self.entry(ln, 0, d)
            obj[k] = v
        return obj

    def entry(self, ln: _Line, start: int, d: int):
        """Parse `key ...` beginning at column `start`; `d` is its logical depth."""
        c = self.cur(ln, start)
        key = c.key()
        rest = ln.text[c.i:]
        if rest == "":
            if self.depth_at(self.i) != d + 1:
                raise BppError(f"key {key!r} has no value", ln.no)
            return key, self.object(d + 1)
        if rest[0] == " ":
            c.i += 1
            v = c.value()
            if not c.eof():
                raise BppError("trailing characters", ln.no)
            return key, v
        if rest[0] == "[":
            return key, self.block(rest, ln, d)
        raise BppError(f"expected space after key {key!r}", ln.no)

    # -- arrays ------------------------------------------------------------------
    def keyless(self, ln: _Line, d: int):
        """A line at depth d beginning with '[': header `[N]...` or inline list."""
        h = _header(ln.text)
        if h and (h[1] or self._items_follow(d)):
            self.i += 1
            return self.block(ln.text, ln, d)
        c = self.cur(ln)
        v = c.inline_list()
        if not c.eof():
            raise BppError("trailing characters", ln.no)
        self.i += 1
        return v

    def _items_follow(self, d: int) -> bool:
        j = self.i + 1
        return j < len(self.L) and self.L[j].depth == d and (
            self.L[j].text.startswith("- ") or self.L[j].text == "-")

    def block(self, head: str, ln: _Line, d: int) -> list:
        h = _header(head)
        if not h:
            raise BppError("bad array header", ln.no)
        n, rest = h
        if not rest:
            return self.items(n, d, ln)
        c = self.cur(_Line(0, rest, ln.no))
        spec = self._spec(c)
        if not c.eof():
            raise BppError("bad array header", ln.no)
        if spec.child is None and not spec.optional and (len(spec.cols) == 1 or spec.delim == ","):
            return self.table(n, spec, d, ln)
        return self.outline(n, spec, d, ln)

    def _spec(self, c: Cursor) -> _Spec:
        dotted = self.version >= 3
        c.expect("{")
        cols = []
        delim = None
        while True:
            path = c.path(dotted)
            opt = keyed = False
            if c.peek() == "?":
                opt = True
                c.i += 1
                # bpp2+: `x?` = positional, '-' when absent; `x?=` = written as x=v.
                # bpp1 only had the x=v form, spelled `x?`.
                if self.version == 1:
                    keyed = True
                elif c.peek() == "=":
                    keyed = True
                    c.i += 1
            smode = False
            if c.s.startswith(":str", c.i):
                smode = True
                c.i += 4
            cols.append((path, opt, keyed, smode))
            sep = c.peek()
            if sep == "}":
                c.i += 1
                break
            if delim is None:
                delim = sep
            if sep != delim or sep not in ", ":
                c.err("bad column list")
            c.i += 1
        child = sub = None
        if c.peek() == ">":
            c.i += 1
            child = c.segment() if dotted else c.key()
            if dotted and c.peek() == "{":
                sub = self._spec(c)
        return _Spec(cols, delim or ",", child, sub)

    def table(self, n: int, spec: _Spec, d: int, ln: _Line) -> list:
        rows = []
        for _ in range(n):
            if self.i >= len(self.L) or self.L[self.i].depth != d:
                raise BppError(f"expected {n} table rows", ln.no)
            r = self.L[self.i]
            self.i += 1
            c = self.cur(r)
            obj: dict = {}
            for j, p in enumerate(spec.order):
                _set_path(obj, p, c.token(",", spec.smode[p]), r.no)
                if j < len(spec.order) - 1:
                    c.expect(",")
            if not c.eof():
                raise BppError("too many cells", r.no)
            rows.append(obj)
        return rows

    def outline(self, n: int, spec: _Spec, d: int, ln: _Line) -> list:
        dotted = self.version >= 3

        def check(sp):
            if sp.order[-1] in sp.optional:
                raise BppError("last column must be required", ln.no)
            if sp.sub is not None:
                check(sp.sub)
        check(spec)

        def row(r: _Line, sp: _Spec):
            c = self.cur(r)
            got = {}
            child_empty = False
            for p in sp.positional:
                if p in sp.optional and c.s.startswith("- ", c.i):
                    c.i += 2  # '-' = this optional column is absent
                    continue
                got[p] = self._cell(c, sp.smode[p])
                c.expect(" ")
            while True:
                save = c.i
                if c.peek() == '"' or c.peek() not in "[{*":
                    try:
                        p = c.path(dotted)
                    except BppError:
                        c.i = save
                        break
                    if c.peek() == "=":
                        if sp.child is not None and p == (sp.child,) and not child_empty:
                            c.i += 1
                            if c.value(" ") != []:
                                raise BppError("child key may only be [] inline", r.no)
                            child_empty = True
                            c.expect(" ")
                            continue
                        if p in sp.keyed and p not in got:
                            c.i += 1
                            got[p] = self._cell(c, sp.smode[p])
                            c.expect(" ")
                            continue
                c.i = save
                break
            last = sp.order[-1]
            got[last] = c.value(strmode=sp.smode[last])
            if not c.eof():
                raise BppError("trailing characters", r.no)
            obj: dict = {}
            for p in sp.order:
                if p in got:
                    _set_path(obj, p, got[p], r.no)
            if child_empty:
                obj[sp.child] = []
            return obj

        def rows_at(depth: int, count, sp: _Spec) -> list:
            out = []
            while self.i < len(self.L) and (count is None or len(out) < count):
                r = self.L[self.i]
                if r.depth < depth:
                    break
                if r.depth > depth:
                    raise BppError("unexpected indentation", r.no)
                self.i += 1
                obj = row(r, sp)
                if sp.child is not None and self.depth_at(self.i) == depth + 1:
                    if sp.child in obj:
                        raise BppError("child rows after child=[]", r.no)
                    obj[sp.child] = rows_at(depth + 1, None, sp.sub or sp)
                out.append(obj)
            if count is not None and len(out) != count:
                raise BppError(f"expected {count} rows", ln.no)
            return out

        return rows_at(d, n, spec)

    @staticmethod
    def _cell(c: Cursor, smode: bool):
        if c.peek() == "[":
            return c.inline_list(smode)
        return c.value(" ", smode)

    def items(self, n: int, d: int, ln: _Line) -> list:
        out = []
        for _ in range(n):
            if self.i >= len(self.L) or self.L[self.i].depth != d:
                raise BppError(f"expected {n} list items", ln.no)
            it = self.L[self.i]
            if not it.text.startswith("- "):
                raise BppError("expected '- ' list item", it.no)
            self.i += 1
            out.append(self.item(it, d))
        return out

    def item(self, it: _Line, d: int):
        body = it.text[2:]
        sub = _Line(d + 1, body, it.no)
        if body.startswith("["):
            h = _header(body)
            if h and (h[1] or (
                    self.i < len(self.L) and self.L[self.i].depth == d + 1
                    and self.L[self.i].text.startswith("- "))):
                return self.block(body, sub, d + 1)
            c = self.cur(sub)
            v = c.inline_list()
            if not c.eof():
                raise BppError("trailing characters", it.no)
            return v
        if body == "{}":
            return {}
        c = self.cur(sub)
        try:
            key = c.key()
            rest = body[c.i:]
        except BppError:
            key, rest = None, None
        if key is not None:
            is_entry = (rest.startswith(" ") or rest.startswith("[")
                        or (rest == "" and self.depth_at(self.i) == d + 2))
            if is_entry:
                k, v = self.entry(sub, 0, d + 1)
                obj = {k: v}
                more = self.object(d + 1)
                for kk, vv in more.items():
                    if kk in obj:
                        raise BppError(f"duplicate key {kk!r}", it.no)
                    obj[kk] = vv
                return obj
        c = self.cur(sub)
        if c.peek() == '"':
            v = c.jstring()
        else:
            v = c.value()
        if not c.eof():
            raise BppError("trailing characters", it.no)
        return v


class _Sentinel:
    pass


_NO = _Sentinel()
