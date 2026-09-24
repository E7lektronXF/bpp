"""Deterministic token estimator.

The encoder makes a few cost-based choices (dictionary entries, table style).
Those choices must not depend on which tokenizer happens to be installed, so we
use this small BPE-like approximation instead of tiktoken.  It tracks o200k and
the legacy Claude tokenizer closely enough to rank alternatives.
"""

from __future__ import annotations

import re

_PIECE = re.compile(
    r" ?[A-Za-z]+"          # ASCII word, leading space merges
    r"| ?[^\W\d_A-Za-z]+"   # non-ASCII letters (ç, ş, ı ...)
    r"| ?\d{1,3}"           # digits come in groups of up to 3
    r"|\n"
    r"| +"
    r"|[^\w\s]{1,2}"        # punctuation, often in pairs
    r"|."
)


def est_tokens(text: str) -> int:
    n = 0
    for m in _PIECE.finditer(text):
        p = m.group()
        L = len(p.strip())
        if p[-1:].isalpha() and p.strip().isascii():
            n += 1 + max(0, L - 1) // 7
        elif p.strip() and p.strip()[0].isalpha():
            n += 1 + max(0, L - 1) // 3
        else:
            n += 1
    return n
