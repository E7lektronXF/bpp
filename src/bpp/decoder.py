""".bpp text -> JSON data model (SPEC §1-§6)."""

from __future__ import annotations

import re

from .lexer import BLOCK_RE, MD_HEADER, BppError, Cursor

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
    __slots__ = ("depth", "text", "no", "idx")

    def __init__(self, depth, text, no, idx=-1):
        self.depth, self.text, self.no, self.idx = depth, text, no, idx


HEADERS = ("bpp1", "bpp2", "bpp3", "bpp4")


def _head(text: str):
    """(version, raw lines, index of the first body line); version 0 = Markdown source."""
    raw = text.split("\n")
    for idx, ln in enumerate(raw):
        if ln.endswith("\r"):
            ln = ln[:-1]
        stripped = ln.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == MD_HEADER:
            return 0, raw, idx + 1
        if stripped not in HEADERS:
            raise BppError("missing 'bpp4' header", idx + 1)
        return int(stripped[3]), raw, idx + 1
    raise BppError("missing 'bpp4' header")


def md_source(text: str) -> str | None:
    """The Markdown text of a `bpp4 md` file (SPEC §7.2), or None for any other file."""
    version, _, start = _head(text)
    if version:
        return None
    parts = text.split("\n", start)
    return parts[start] if len(parts) > start else ""


def decode(text: str):
    """Decode .bpp text into Python/JSON values."""
    version, raw, start = _head(text)
    if not version:
        from .markdown import md_to_tree
        return md_to_tree(md_source(text))
    return _Dec(raw, start, version).document()


class _Dec:
    def __init__(self, raw: list[str], start: int, version: int = 2):
        self.raw = raw
        self.version = version
        self.i = start      # index into raw of the next unread line
        self.bpos = start   # where the next `|N` block of the current line begins
        self.refs: list = []

    # -- lines -------------------------------------------------------------------
    # Blank and comment lines are skipped when looking for the next logical line,
    # but `|N` blocks are read straight from `raw`, so they may contain anything.
    def line_at(self, j: int) -> _Line | None:
        while j < len(self.raw):
            ln = self.raw[j]
            if ln.endswith("\r"):
                ln = ln[:-1]
            stripped = ln.lstrip(" ")
            if stripped and not stripped.startswith("#"):
                return _Line(len(ln) - len(stripped), stripped, j + 1, j)
            j += 1
        return None

    def peek(self) -> _Line | None:
        return self.line_at(self.i)

    def take(self) -> _Line:
        ln = self.line_at(self.i)
        self.i = self.bpos = ln.idx + 1
        return ln

    def block(self, n: int) -> str:
        """The n raw lines after the current line (and after its earlier blocks)."""
        if n < 1 or self.bpos + n > len(self.raw):
            raise BppError(f"block |{n} runs past the end of the file", self.bpos)
        out = [ln[:-1] if ln.endswith("\r") else ln for ln in self.raw[self.bpos:self.bpos + n]]
        self.bpos += n
        self.i = self.bpos
        return "\n".join(out)

    # -- helpers ---------------------------------------------------------------
    def cur(self, ln: _Line, start: int = 0) -> Cursor:
        c = Cursor(ln.text, self.refs, ln.no, self.block if self.version >= 4 else None)
        c.i = start
        return c

    def depth_at(self) -> int:
        ln = self.peek()
        return ln.depth if ln else -1

    # -- document ----------------------------------------------------------------
    def document(self):
        while self.peek() is not None and self.peek().text.startswith("&"):
            ln = self.take()
            m = re.match(r"&(\d+) ", ln.text)
            if not m or ln.depth or int(m.group(1)) != len(self.refs):
                raise BppError("bad dictionary definition", ln.no)
            c = self.cur(ln, m.end())
            v = c.value()
            if not isinstance(v, str) or not c.eof():
                raise BppError("dictionary value must be a string", ln.no)
            self.refs.append(v)
        first = self.peek()
        if first is None:
            raise BppError("empty document")
        if first.depth:
            raise BppError("unexpected indentation", first.no)
        if self.version >= 4 and BLOCK_RE.fullmatch(first.text):
            self.take()
            v = self.block(int(first.text[1:]))  # a root string written as a block
        elif self.line_at(first.idx + 1) is None and (v := self._root_inline(first)) is not _NO:
            self.take()
        elif first.text.startswith("["):
            v = self.keyless(first, 0)
        else:
            v = self.object(0)
        if self.peek() is not None:
            raise BppError("unexpected content", self.peek().no)
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
        while (ln := self.peek()) is not None:
            if ln.depth < d:
                break
            if ln.depth > d:
                raise BppError("unexpected indentation", ln.no)
            if ln.text.startswith("- ") or ln.text == "-":
                raise BppError("list item outside a list", ln.no)
            self.take()
            k, v = self.entry(ln, 0, d)
            obj[k] = v
        return obj

    def entry(self, ln: _Line, start: int, d: int):
        """Parse `key ...` beginning at column `start`; `d` is its logical depth."""
        c = self.cur(ln, start)
        key = c.key()
        rest = ln.text[c.i:]
        if rest == "":
            if self.depth_at() != d + 1:
                raise BppError(f"key {key!r} has no value", ln.no)
            return key, self.object(d + 1)
        if rest[0] == " ":
            c.i += 1
            v = c.value()
            if not c.eof():
                raise BppError("trailing characters", ln.no)
            return key, v
        if rest[0] == "[":
            return key, self.array(rest, ln, d, key)
        raise BppError(f"expected space after key {key!r}", ln.no)

    # -- arrays ------------------------------------------------------------------
    def keyless(self, ln: _Line, d: int):
        """A line at depth d beginning with '[': header `[N]...` or inline list."""
        h = _header(ln.text)
        if h and (h[1] or self._items_follow(ln, d)):
            self.take()
            return self.array(ln.text, ln, d)
        self.take()
        c = self.cur(ln)
        v = c.inline_list()
        if not c.eof():
            raise BppError("trailing characters", ln.no)
        return v

    def _items_follow(self, ln: _Line, d: int) -> bool:
        nxt = self.line_at(ln.idx + 1)
        return nxt is not None and nxt.depth == d and (
            nxt.text.startswith("- ") or nxt.text == "-")

    def array(self, head: str, ln: _Line, d: int, key: str | None = None) -> list:
        h = _header(head)
        if not h:
            raise BppError("bad array header", ln.no)
        n, rest = h
        if not rest:
            return self.items(n, d, ln)
        c = self.cur(_Line(0, rest, ln.no))
        spec = self._spec(c, key)
        if not c.eof():
            raise BppError("bad array header", ln.no)
        if spec.child is None and not spec.optional and (len(spec.cols) == 1 or spec.delim == ","):
            return self.table(n, spec, d, ln)
        return self.outline(n, spec, d, ln)

    def _spec(self, c: Cursor, key: str | None) -> _Spec:
        """Column spec; `key` is the key its rows are stored under (None: keyless)."""
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
            if self.version >= 4 and c.peek() in ("{", ""):
                if key is None:  # bpp4: a bare `>` repeats the table's own key
                    c.err("'>' without a name needs a keyed table")
                child = key
            else:
                child = c.segment() if dotted else c.key()
            if dotted and c.peek() == "{":
                sub = self._spec(c, child)
        return _Spec(cols, delim or ",", child, sub)

    def table(self, n: int, spec: _Spec, d: int, ln: _Line) -> list:
        rows = []
        for _ in range(n):
            if self.depth_at() != d:
                raise BppError(f"expected {n} table rows", ln.no)
            r = self.take()
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
            while (r := self.peek()) is not None and (count is None or len(out) < count):
                if r.depth < depth:
                    break
                if r.depth > depth:
                    raise BppError("unexpected indentation", r.no)
                self.take()
                obj = row(r, sp)
                if sp.child is not None and self.depth_at() == depth + 1:
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
            if self.depth_at() != d:
                raise BppError(f"expected {n} list items", ln.no)
            it = self.take()
            if not it.text.startswith("- "):
                raise BppError("expected '- ' list item", it.no)
            out.append(self.item(it, d))
        return out

    def item(self, it: _Line, d: int):
        body = it.text[2:]
        sub = _Line(d + 1, body, it.no, it.idx)
        if self.version >= 4 and BLOCK_RE.fullmatch(body):
            return self.block(int(body[1:]))
        if body.startswith("["):
            h = _header(body)
            nxt = self.peek()
            if h and (h[1] or (nxt is not None and nxt.depth == d + 1
                               and nxt.text.startswith("- "))):
                return self.array(body, sub, d + 1)
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
                        or (rest == "" and self.depth_at() == d + 2))
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
