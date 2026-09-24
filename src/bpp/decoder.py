""".bpp text -> JSON data model (SPEC §1-§6)."""

from __future__ import annotations

import re

from .lexer import BppError, Cursor

_HEADER_RE = re.compile(r"\[(\d+)\](?:\{(.*)\}(?:>(.+))?)?$")


class _Line:
    __slots__ = ("depth", "text", "no")

    def __init__(self, depth, text, no):
        self.depth, self.text, self.no = depth, text, no


def decode(text: str):
    """Decode .bpp text into Python/JSON values."""
    raw = text.split("\n")
    lines: list[_Line] = []
    header_seen = False
    for no, ln in enumerate(raw, 1):
        if ln.endswith("\r"):
            ln = ln[:-1]
        stripped = ln.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if not header_seen:
            if stripped != "bpp1":
                raise BppError("missing 'bpp1' header", no)
            header_seen = True
            continue
        lines.append(_Line(len(ln) - len(stripped), stripped, no))
    if not header_seen:
        raise BppError("missing 'bpp1' header")
    return _Dec(lines).document()


class _Dec:
    def __init__(self, lines: list[_Line]):
        self.L = lines
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
        m = _HEADER_RE.match(ln.text)
        if m and (m.group(2) is not None or self._items_follow(d)):
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
        m = _HEADER_RE.match(head)
        if not m:
            raise BppError("bad array header", ln.no)
        n, cols, child = int(m.group(1)), m.group(2), m.group(3)
        if cols is None:
            return self.items(n, d, ln)
        spec = self._columns(cols, ln)
        if child is not None or any(c[1] for c in spec) or (len(spec) > 1 and spec.delim == " "):
            if child is not None:
                cc = self.cur(_Line(0, child, ln.no))
                child = cc.key()
                if not cc.eof():
                    raise BppError("bad child key", ln.no)
            return self.outline(n, spec, child, d, ln)
        return self.table(n, spec, d, ln)

    def _columns(self, text: str, ln: _Line):
        c = self.cur(_Line(0, text, ln.no))
        out = _Cols()
        while True:
            name = c.key()
            opt = False
            if c.peek() == "?":
                opt = True
                c.i += 1
            smode = False
            if c.s.startswith(":str", c.i):
                smode = True
                c.i += 4
            out.append((name, opt, smode))
            if c.eof():
                break
            sep = c.peek()
            if out.delim is None:
                out.delim = sep
            if sep != out.delim or sep not in ", ":
                raise BppError("bad column list", ln.no)
            c.i += 1
        if out.delim is None:
            out.delim = ","
        return out

    def table(self, n: int, spec, d: int, ln: _Line) -> list:
        rows = []
        names = [s[0] for s in spec]
        for _ in range(n):
            if self.i >= len(self.L) or self.L[self.i].depth != d:
                raise BppError(f"expected {n} table rows", ln.no)
            r = self.L[self.i]
            self.i += 1
            c = self.cur(r)
            vals = []
            for j, (_, _, smode) in enumerate(spec):
                vals.append(c.token(",", smode))
                if j < len(spec) - 1:
                    c.expect(",")
            if not c.eof():
                raise BppError("too many cells", r.no)
            rows.append(dict(zip(names, vals)))
        return rows

    def outline(self, n: int, spec, child, d: int, ln: _Line) -> list:
        order = [s[0] for s in spec]
        smode = {s[0]: s[2] for s in spec}
        optional = {s[0] for s in spec if s[1]}
        last = order[-1]
        if last in optional:
            raise BppError("last column must be required", ln.no)
        positional = [c for c in order[:-1] if c not in optional]
        kv_names = optional | ({child} if child else set())

        def row(r: _Line):
            c = self.cur(r)
            got = {}
            for name in positional:
                got[name] = self._cell(c, smode[name])
                c.expect(" ")
            while True:
                save = c.i
                if c.peek() == '"' or c.peek() not in "[{*":
                    try:
                        name = c.key()
                    except BppError:
                        c.i = save
                        break
                    if name in kv_names and c.peek() == "=" and name not in got:
                        c.i += 1
                        if name == child:
                            v = c.value(" ")
                            if v != []:
                                raise BppError("child key may only be [] inline", r.no)
                        else:
                            v = self._cell(c, smode[name])
                        got[name] = v
                        c.expect(" ")
                        continue
                c.i = save
                break
            got[last] = c.value(strmode=smode[last])
            if not c.eof():
                raise BppError("trailing characters", r.no)
            obj = {k: got[k] for k in order if k in got}
            if child and child in got:
                obj[child] = got[child]
            return obj

        def rows_at(depth: int, count: int | None) -> list:
            out = []
            while self.i < len(self.L) and (count is None or len(out) < count):
                r = self.L[self.i]
                if r.depth < depth:
                    break
                if r.depth > depth:
                    raise BppError("unexpected indentation", r.no)
                self.i += 1
                obj = row(r)
                if child and self.depth_at(self.i) == depth + 1:
                    if child in obj:
                        raise BppError("child rows after child=[]", r.no)
                    obj[child] = rows_at(depth + 1, None)
                out.append(obj)
            if count is not None and len(out) != count:
                raise BppError(f"expected {count} rows", ln.no)
            return out

        return rows_at(d, n)

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
            m = _HEADER_RE.match(body)
            if m and (m.group(2) is not None or (
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


class _Cols(list):
    delim: str | None = None


class _Sentinel:
    pass


_NO = _Sentinel()
