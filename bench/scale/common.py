"""Shared by run_scale.py and blackwell.py: formats, token counts, model calls."""

from __future__ import annotations

import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

import bpp  # noqa: E402
from run_qa import PROVIDERS, _THINK, ask_openai  # noqa: E402

RES = ROOT / "bench" / "results" / "scale"

# ------------------------------------------------------------------ formats
# A format name is json, gcf, or bpp with optional encoder options:
#   bpp            the library default
#   bpp-refs       refs=True        bpp-norefs   refs=False
#   bpp:refs=0,keep_order=1,primer=1   any encode() keyword (0/1 for booleans)
# Every bpp variant is shown to the model under the same label, "BPP".

ALIASES = {"bpp-refs": "bpp:refs=1", "bpp-norefs": "bpp:refs=0"}
DEFAULT_FORMATS = ["json", "gcf", "bpp-refs", "bpp-norefs"]


def bpp_options(fmt: str) -> dict:
    fmt = ALIASES.get(fmt, fmt)
    if fmt == "bpp":
        return {}
    if not fmt.startswith("bpp:"):
        raise ValueError(f"unknown format {fmt!r}")
    out = {}
    for kv in fmt[4:].split(","):
        k, _, v = kv.partition("=")
        out[k] = {"0": False, "1": True}.get(v, int(v) if v.isdigit() else v)
    return out


def label(fmt: str) -> str:
    return "BPP" if fmt.startswith("bpp") else fmt.upper()


def render(fmt: str, data) -> str:
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if fmt == "gcf":
        import gcf
        return gcf.encode_generic(data)
    return bpp.encode(data, **bpp_options(fmt))


def same(a, b, ordered: bool = False) -> bool:
    """Equal with types (1 != 1.0 != True), as tests/conftest.py checks; `ordered` also
    compares key order (bpp may move a text column last unless keep_order, SPEC §4.3)."""
    return a == b and (json.dumps(a, ensure_ascii=False, sort_keys=not ordered)
                       == json.dumps(b, ensure_ascii=False, sort_keys=not ordered))


def decoded(fmt: str, text: str):
    if fmt.startswith("bpp"):
        return bpp.decode(text)
    if fmt == "json":
        return json.loads(text)
    import gcf
    return gcf.decode_generic(text)


def roundtrips(fmt: str, text: str, data, ordered: bool = False) -> bool:
    """Lossless check (values and types; key order too with `ordered`)."""
    try:
        return same(decoded(fmt, text), data, ordered)
    except Exception:
        return False


# ------------------------------------------------------------------- tokens
# The local models' own tokenizers are taken from npm (@lenml/tokenizer-*), since
# Hugging Face is not reachable everywhere; they need `pip install tokenizers`.

TOKENIZER_PKGS = {"llama3": "@lenml/tokenizer-llama3", "qwen3": "@lenml/tokenizer-qwen3"}
TOK_DIR = Path(os.environ.get("BPP_CACHE_DIR") or Path.home() / ".cache" / "bpp") / "tokenizers"


def fetch_tokenizers() -> None:
    """Download the Llama 3 and Qwen3 tokenizer.json files (once)."""
    TOK_DIR.mkdir(parents=True, exist_ok=True)
    for fam, pkg in TOKENIZER_PKGS.items():
        dest = TOK_DIR / f"{fam}.json"
        if dest.exists():
            continue
        name = pkg.split("/")[1]
        url = f"https://registry.npmjs.org/{pkg}/-/{name}-3.7.2.tgz"
        tgz = TOK_DIR / f"{name}.tgz"
        urllib.request.urlretrieve(url, tgz)
        with tarfile.open(tgz) as t:
            dest.write_bytes(t.extractfile("package/models/tokenizer.json").read())
        tgz.unlink()
        print(f"saved {dest}")


def family(model: str) -> str:
    m = model.lower()
    if "llama" in m:
        return "llama3"
    if "qwen" in m:
        return "qwen3"
    if "gpt-oss" in m:
        return "o200k"
    return "cl100k"


@lru_cache(maxsize=None)
def counter(fam: str):
    """(count function, exact?) for a tokenizer family; falls back to cl100k + 30%."""
    if fam in TOKENIZER_PKGS:
        path = TOK_DIR / f"{fam}.json"
        try:
            from tokenizers import Tokenizer
            tok = Tokenizer.from_file(str(path))
            return (lambda s: len(tok.encode(s, add_special_tokens=False).ids)), True
        except Exception:
            base, _ = counter("cl100k")
            return (lambda s: int(base(s) * 1.3) + 1), False
    try:
        import tiktoken
        enc = tiktoken.get_encoding({"o200k": "o200k_base"}.get(fam, "cl100k_base"))
        return (lambda s: len(enc.encode(s, disallowed_special=()))), True
    except Exception:
        from bpp.estimate import est_tokens
        return (lambda s: int(est_tokens(s) * 1.3) + 1), False


# ------------------------------------------------------------------- models

def ask_ollama(host, model, system, user, num_ctx, num_predict, temperature=0.0):
    """One chat request to Ollama's native API (num_ctx can only be set there)."""
    body = {"model": model, "stream": False, "keep_alive": "30m",
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": user}],
            "options": {"temperature": temperature, "seed": 42, "num_ctx": num_ctx,
                        "num_predict": num_predict}}
    if family(model) == "qwen3" or "gpt-oss" in model:
        body["think"] = False if family(model) == "qwen3" else "low"
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == 4:
                raise RuntimeError(f"Ollama not reachable at {host}: {e}") from None
            time.sleep(5 * (attempt + 1))
    text = _THINK.sub("", (d.get("message") or {}).get("content") or "")
    return text, d.get("done_reason"), d.get("prompt_eval_count"), d.get("total_duration")


class Model:
    """provider ollama, or any OpenAI-compatible provider of run_qa.PROVIDERS."""

    def __init__(self, provider, model, *, host=None, num_ctx=32768, max_tokens=None,
                 base_url=None, temperature=0.0):
        self.provider, self.model, self.temperature = provider, model, temperature
        self.fam = family(model)
        if provider == "ollama":
            self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            if not self.host.startswith("http"):
                self.host = "http://" + self.host
            self.ctx = num_ctx
            self.max_tokens = max_tokens or 600
        else:
            prov = PROVIDERS[provider]
            self.key = os.environ.get(prov["env"])
            self.base_url = base_url or prov["base_url"]
            self.extra = next((v for k, v in prov.get("extra", {}).items() if model.startswith(k)), None)
            self.max_tokens = max_tokens or prov.get("max_tokens", 4000)
            self.ctx = num_ctx

    @property
    def ready(self) -> bool:
        return self.provider == "ollama" or bool(self.key)

    def fits(self, n_tokens: int) -> bool:
        return n_tokens + self.max_tokens <= self.ctx

    def ask(self, system, user):
        """(text, stop_reason, prompt_tokens)"""
        if self.provider == "ollama":
            text, stop, n_in, _ = ask_ollama(self.host, self.model, system, user, self.ctx,
                                             self.max_tokens, self.temperature)
            return text, stop, n_in
        return ask_openai(self.base_url, self.key, self.model, user, self.max_tokens, self.extra,
                          system=system, temperature=self.temperature)

    @property
    def stem(self) -> str:
        return re.sub(r"[^A-Za-z0-9.]+", "-", self.model).strip("-").lower()
