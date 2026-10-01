"""Which models does this API key actually serve? (A model can be listed by /v1/models and
still answer 404 "Function ... Not found for account".)

    python bench/scale/probe.py                      # the default NVIDIA candidates
    python bench/scale/probe.py google/gemma-3-4b-it openai/gpt-oss-20b
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROVIDERS  # noqa: E402

CANDIDATES = [
    "google/gemma-3-4b-it", "google/gemma-3-12b-it", "google/gemma-4-31b-it",
    "mistralai/mistral-7b-instruct-v0.3", "nv-mistralai/mistral-nemo-12b-instruct",
    "ibm/granite-3.0-8b-instruct", "zyphra/zamba2-7b-instruct",
    "nvidia/nemotron-nano-3-30b-a3b", "nvidia/nemotron-3.5-lightning-30b-a3b",
    "openai/gpt-oss-20b", "deepseek-ai/deepseek-v4.1-flash", "z-ai/glm-5.3-flash",
    "moonshotai/kimi-k2.6", "nvidia/llama-3.1-nemotron-70b-instruct",
]


def probe(base_url: str, key: str, model: str, timeout: float) -> str:
    """One tiny request, no retries: 'OK ...' or 'FAIL ...'."""
    body = json.dumps({"model": model, "max_tokens": 200, "temperature": 0,
                       "messages": [{"role": "user", "content": "Reply with the word OK."}]}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": "bpp-bench/0.4 (+https://github.com/E7lektronXF/bpp)"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        text = (d["choices"][0]["message"].get("content") or "").strip()
        return f"OK    {time.time() - t0:5.1f}s  {text[:30]!r}"
    except urllib.error.HTTPError as e:
        return f"FAIL  HTTP {e.code}: {e.read()[:90].decode('utf-8', 'replace')}"
    except Exception as e:  # noqa: BLE001 - timeouts, connection errors: report and go on
        return f"FAIL  {type(e).__name__} after {time.time() - t0:.0f}s"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("models", nargs="*", default=CANDIDATES)
    ap.add_argument("--provider", default="nvidia", choices=["nvidia", "groq", "openai"])
    ap.add_argument("--timeout", type=float, default=60, help="seconds per model (default 60)")
    a = ap.parse_args()
    prov = PROVIDERS[a.provider]
    key = os.environ.get(prov["env"])
    if not key:
        raise SystemExit(f"{prov['env']} is not set")
    for m in a.models:
        print(f"{m:45s} {probe(prov['base_url'], key, m, a.timeout)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
