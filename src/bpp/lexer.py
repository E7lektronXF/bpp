"""Scalar, key and inline-value syntax shared by the encoder and decoder (SPEC §2-§4)."""

from __future__ import annotations

import json
import math
import re

NUM_RE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
SPECIAL = {"null": None, "true": True, "false": False,
           "NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
BARE_KEY_RE = re.compile(r"[^\s\"\[\]{}=,:?>\x00-\x1f\x7f]+")
_KV_START = re.compile(r"(?:[^\s\"\[\]{}=,:?>]+|\"(?:[^\"\\]|\\.)*\")=")
_DECODER = json.JSONDecoder()


class BppError(ValueError):
    """Raised for malformed .bpp input."""

    def __init__(self, msg: str, line: int | None = None):
        super().__init__(f"line {line}: {msg}" if line else msg)
        self.line = line


class Ref:
    """Placeholder for a dictionary reference (`*n`) produced by the encoder."""

    __slots__ = ("idx",)

    def __init__(self, idx: int):
        self.idx = idx


def is_scalar(v) -> bool:
    return v is None or isinstance(v, (str, bool, int, float, Ref))


def jstr(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


# ---------------------------------------------------------------- formatting

def fmt_number(v) -> str:
    if isinstance(v, int):
        return str(v)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    return repr(v)


def needs_quote(s: str, ctx: str = "value", strmode: bool = False) -> bool:
    """Minimum-quoting rule (SPEC §2.1). ctx: value|cell|list|pos|item|last."""
    if (not s or s != s.strip() or _CTRL.search(s) or s[0] in '"[{*&#'
            or s in SPECIAL):
        return True
    if not strmode and NUM_RE.fullmatch(s):
        return True
    if ctx == "cell":
        return "," in s
    if ctx == "list":
        return "," in s or "]" in s
    if ctx == "pos":
        return " " in s or s == "-"
    if ctx == "item":
        return " " in s or "[" in s or "{" in s
    if ctx == "last":
        return _KV_START.match(s) is not None
    return False


def fmt_scalar(v, ctx: str = "value", strmode: bool = False) -> str:
    if isinstance(v, Ref):
        return f"*{v.idx}"
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return fmt_number(v)
    return jstr(v) if needs_quote(v, ctx, strmode) else v


def fmt_key(k: str) -> str:
    if BARE_KEY_RE.fullmatch(k) and k[0] not in "-#&*":
        return k
    return jstr(k)


def fmt_inline(v, ctx: str = "value", strmode: bool = False) -> str | None:
    """Single-line form of v, or None if v needs a block."""
    if is_scalar(v):
        return fmt_scalar(v, ctx, strmode)
    if isinstance(v, dict):
        return "{}" if not v else None
    if isinstance(v, list):
        if all(is_scalar(x) for x in v):
            return "[" + ",".join(fmt_scalar(x, "list", strmode) for x in v) + "]"
        return None
    raise TypeError(f"unsupported type {type(v).__name__}")


# ------------------------------------------------------------------- parsing

def parse_bare(tok: str, strmode: bool = False):
    """Interpret an unquoted token (no surrounding whitespace)."""
    if strmode:
        return None if tok == "null" else tok
    if tok in SPECIAL:
        return SPECIAL[tok]
    if NUM_RE.fullmatch(tok):
        if "." in tok or "e" in tok or "E" in tok:
            return float(tok)
        return int(tok)
    return tok


class Cursor:
    """Scans one line of text; `refs` resolves `*n`."""

    def __init__(self, text: str, refs: list, line: int | None):
        self.s, self.i, self.refs, self.line = text, 0, refs, line

    def err(self, msg):
        raise BppError(msg, self.line)

    def eof(self):
        return self.i >= len(self.s)

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ""

    def expect(self, ch):
        if self.peek() != ch:
            self.err(f"expected {ch!r} at column {self.i + 1}")
        self.i += 1

    def jstring(self) -> str:
        try:
            val, end = _DECODER.raw_decode(self.s, self.i)
        except json.JSONDecodeError as e:
            self.err(f"bad quoted string: {e.msg}")
        if not isinstance(val, str):
            self.err("expected string")
        self.i = end
        return val

    def key(self) -> str:
        if self.peek() == '"':
            return self.jstring()
        m = BARE_KEY_RE.match(self.s, self.i)
        if not m or self.s[self.i] in "-#&*":
            self.err("expected key")
        self.i = m.end()
        return m.group()

    def resolve(self, tok: str, strmode: bool):
        if tok.startswith("*") and tok[1:].isdigit():
            idx = int(tok[1:])
            if idx >= len(self.refs):
                self.err(f"undefined reference {tok}")
            return self.refs[idx]
        return parse_bare(tok, strmode)

    def token(self, stops: str, strmode: bool = False):
        """A scalar ending before any char in `stops` (or end of line)."""
        if self.peek() == '"':
            return self.jstring()
        j = self.i
        while j < len(self.s) and self.s[j] not in stops:
            j += 1
        tok = self.s[self.i:j]
        if not tok:
            self.err(f"empty value at column {self.i + 1}")
        self.i = j
        return self.resolve(tok, strmode)

    def inline_list(self, strmode: bool = False) -> list:
        self.expect("[")
        out = []
        if self.peek() == "]":
            self.i += 1
            return out
        while True:
            out.append(self.token(",]", strmode))
            c = self.peek()
            self.i += 1
            if c == "]":
                return out
            if c != ",":
                self.err("unterminated inline list")

    def value(self, stops: str = "", strmode: bool = False):
        """Inline value: scalar, [list], {} (for `key value` stops is empty -> rest of line)."""
        c = self.peek()
        if c == "[":
            return self.inline_list(strmode)
        if self.s.startswith("{}", self.i):
            self.i += 2
            return {}
        if not stops:
            if c == '"':
                return self.jstring()
            tok = self.s[self.i:]
            if not tok:
                self.err("missing value")
            self.i = len(self.s)
            return self.resolve(tok, strmode)
        return self.token(stops, strmode)
