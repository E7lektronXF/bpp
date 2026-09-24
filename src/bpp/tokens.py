"""Token counters used by `bpp stats` and the benchmarks.

Three counters, all optional:

* ``o200k``   - tiktoken ``o200k_base`` (modern OpenAI BPE; a rough proxy).
* ``claude2`` - the legacy Claude tokenizer Anthropic published in the
  ``@anthropic-ai/tokenizer`` npm package (Claude 2 era; a second proxy that
  behaves more like Claude on non-English text).
* ``anthropic`` - the real ``messages.count_tokens`` endpoint.  Used only when
  the ``anthropic`` SDK is installed and ``ANTHROPIC_API_KEY`` is set.

Neither proxy is exact for current Claude models; relative comparisons between
formats are what matter here.

tiktoken normally downloads its rank files from a blob store that some
networks block.  If that fails we fetch the same ranks from the npm registry
(``js-tiktoken`` ships them), verify the published SHA-256, and drop the file
into tiktoken's own cache so later calls work offline.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tarfile
import tempfile
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Callable

O200K_URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
O200K_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
JS_TIKTOKEN_TGZ = "https://registry.npmjs.org/js-tiktoken/-/js-tiktoken-1.0.21.tgz"
CLAUDE_TGZ = "https://registry.npmjs.org/@anthropic-ai/tokenizer/-/tokenizer-0.0.4.tgz"

ANTHROPIC_MODEL = os.environ.get("BPP_ANTHROPIC_MODEL", "claude-opus-5")


def _cache_dir() -> Path:
    d = os.environ.get("BPP_CACHE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "bpp"
    )
    Path(d).mkdir(parents=True, exist_ok=True)
    return Path(d)


def _tiktoken_cache_dir() -> Path:
    # Mirrors tiktoken.load.read_file_cached
    if "TIKTOKEN_CACHE_DIR" in os.environ:
        d = os.environ["TIKTOKEN_CACHE_DIR"]
    elif "DATA_GYM_CACHE_DIR" in os.environ:
        d = os.environ["DATA_GYM_CACHE_DIR"]
    else:
        d = os.path.join(tempfile.gettempdir(), "data-gym-cache")
    Path(d).mkdir(parents=True, exist_ok=True)
    return Path(d)


def _fetch_tgz_member(url: str, member_suffix: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.name.endswith(member_suffix):
                f = tf.extractfile(m)
                assert f is not None
                return f.read()
    raise FileNotFoundError(f"{member_suffix} not in {url}")


def _parse_js_ranks(text: str) -> dict:
    """Parse js-tiktoken's compressed rank format: '! <offset> <b64> <b64> ...'."""
    if not text.lstrip().startswith("{"):
        text = text[text.index("{") :].rstrip().rstrip(";")
    return json.loads(text)


def _expand_ranks(bpe_ranks: str) -> dict[bytes, int]:
    ranks: dict[bytes, int] = {}
    for line in bpe_ranks.split("\n"):
        if not line:
            continue
        _, offset, *toks = line.split(" ")
        for i, t in enumerate(toks):
            ranks[base64.b64decode(t)] = int(offset) + i
    return ranks


def bootstrap_o200k() -> None:
    """Populate tiktoken's cache with o200k_base fetched via npm."""
    path = _tiktoken_cache_dir() / hashlib.sha1(O200K_URL.encode()).hexdigest()
    if path.exists():
        return
    d = _parse_js_ranks(
        _fetch_tgz_member(JS_TIKTOKEN_TGZ, "dist/ranks/o200k_base.js").decode()
    )
    ranks = _expand_ranks(d["bpe_ranks"])
    body = "".join(
        base64.b64encode(b).decode() + " " + str(r) + "\n"
        for b, r in sorted(ranks.items(), key=lambda kv: kv[1])
    ).encode()
    if hashlib.sha256(body).hexdigest() != O200K_SHA256:
        raise ValueError("o200k_base rebuilt from npm does not match tiktoken's hash")
    path.write_bytes(body)


@lru_cache(maxsize=None)
def _o200k():
    import tiktoken

    try:
        return tiktoken.get_encoding("o200k_base")
    except Exception:
        bootstrap_o200k()
        return tiktoken.get_encoding("o200k_base")


@lru_cache(maxsize=None)
def _claude2():
    import tiktoken

    path = _cache_dir() / "claude.json"
    if not path.exists():
        path.write_bytes(_fetch_tgz_member(CLAUDE_TGZ, "package/claude.json"))
    d = json.loads(path.read_text(encoding="utf-8"))
    return tiktoken.Encoding(
        name="claude2",
        pat_str=d["pat_str"],
        mergeable_ranks=_expand_ranks(d["bpe_ranks"]),
        special_tokens=d["special_tokens"],
    )


@lru_cache(maxsize=None)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()


@lru_cache(maxsize=4096)
def _count_anthropic(text: str) -> int:
    resp = _anthropic_client().messages.count_tokens(
        model=ANTHROPIC_MODEL, messages=[{"role": "user", "content": text}]
    )
    return resp.input_tokens


def _count_anthropic_net(text: str) -> int:
    # count_tokens includes a fixed per-message overhead; subtract it so that
    # the numbers are comparable to the local tokenizers.
    return _count_anthropic(text) - _count_anthropic("x") + 1


def available_counters() -> dict[str, Callable[[str], int]]:
    """Return the counters that work in this environment, name -> fn(text)."""
    out: dict[str, Callable[[str], int]] = {}
    try:
        enc = _o200k()
        out["o200k"] = lambda s: len(enc.encode_ordinary(s))
    except Exception:
        pass
    try:
        enc2 = _claude2()
        out["claude2"] = lambda s: len(enc2.encode_ordinary(s))
    except Exception:
        pass
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            _count_anthropic("x")
            out["anthropic"] = _count_anthropic_net
        except Exception:
            pass
    if not out:
        # Last resort so `bpp stats` still prints something useful: the
        # encoder's own estimator (ranks formats like the real tokenizers do;
        # a plain chars/4 gets the direction wrong for Turkish text).
        from .estimate import est_tokens

        out["estimate"] = est_tokens
    return out
