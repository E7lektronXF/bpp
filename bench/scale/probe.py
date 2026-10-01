"""Which models does this API key actually serve? (A model can be listed by /v1/models and
still answer 404 "Function ... Not found for account".)

    python bench/scale/probe.py                      # the default NVIDIA candidates
    python bench/scale/probe.py google/gemma-3-4b-it openai/gpt-oss-20b
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROVIDERS, ask_openai  # noqa: E402

CANDIDATES = [
    "google/gemma-3-4b-it", "google/gemma-3-12b-it", "google/gemma-4-31b-it",
    "mistralai/mistral-7b-instruct-v0.3", "nv-mistralai/mistral-nemo-12b-instruct",
    "ibm/granite-3.0-8b-instruct", "zyphra/zamba2-7b-instruct",
    "nvidia/nemotron-nano-3-30b-a3b", "nvidia/nemotron-3.5-lightning-30b-a3b",
    "openai/gpt-oss-20b", "deepseek-ai/deepseek-v4.1-flash", "z-ai/glm-5.3-flash",
    "moonshotai/kimi-k2.6", "nvidia/llama-3.1-nemotron-70b-instruct",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("models", nargs="*", default=CANDIDATES)
    ap.add_argument("--provider", default="nvidia", choices=["nvidia", "groq", "openai"])
    a = ap.parse_args()
    import os
    prov = PROVIDERS[a.provider]
    key = os.environ.get(prov["env"])
    if not key:
        raise SystemExit(f"{prov['env']} is not set")
    for m in a.models:
        t0 = time.time()
        try:
            text, stop, _ = ask_openai(prov["base_url"], key, m, "Reply with the word OK.", max_tokens=200)
            status = f"OK    {time.time() - t0:5.1f}s  {text.strip()[:30]!r}"
        except Exception as e:  # noqa: BLE001 - report every failure and go on
            status = "FAIL  " + str(e).replace("\n", " ")[:110]
        print(f"{m:45s} {status}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
