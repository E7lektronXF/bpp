"""Token benchmark: every example in every format, every available counter.

    python bench/run_tokens.py            # writes bench/results/tokens.md and tokens.json

Counters: o200k (tiktoken), claude2 (legacy Claude tokenizer) and, when
ANTHROPIC_API_KEY is set, the real count_tokens endpoint ("anthropic").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

from make_examples import EX, EXAMPLES, load  # noqa: E402

from bpp.cli import renderings  # noqa: E402
from bpp.formats import dumps  # noqa: E402
from bpp.tokens import available_counters  # noqa: E402

RES = ROOT / "bench" / "results"


def all_renderings(name: str) -> dict[str, str]:
    data, fmt = load(name)
    out = renderings(data, keep_order=fmt == "csv")
    if fmt == "md":
        # The source Markdown is what a user would otherwise paste.
        out = {"Markdown (source)": (EX / EXAMPLES[name][0]).read_text(encoding="utf-8"),
               "Markdown (normalized)": dumps(data, "md"), **out}
    out["bpp --no-refs"] = dumps(data, "bpp", refs=False, keep_order=fmt == "csv")
    return out


def main():
    counters = available_counters()
    names = list(counters)
    results: dict = {}
    for ex in EXAMPLES:
        results[ex] = {fmt: {c: fn(text) for c, fn in counters.items()}
                       for fmt, text in all_renderings(ex).items()}

    md = ["# Token benchmark", "",
          f"Counters: {', '.join(names)}. Lower is better. "
          "Δ columns are relative to pretty-printed JSON.", ""]
    for ex, rows in results.items():
        fname, desc = EXAMPLES[ex]
        base = rows["JSON (indent 2)"]
        md += [f"## {ex} — `examples/{fname}`", "", desc, "",
               "| format | " + " | ".join(names) + " | " + " | ".join(f"Δ {n}" for n in names) + " |",
               "|---|" + "---:|" * (2 * len(names))]
        best = {n: min(v[n] for f, v in rows.items() if not f.startswith("bpp")) for n in names}
        for fmt, cnt in rows.items():
            cells = []
            for n in names:
                s = str(cnt[n])
                cells.append(f"**{s}**" if fmt == "bpp" else s)
            md.append(f"| {fmt} | " + " | ".join(cells) + " | "
                      + " | ".join(f"{100 * (cnt[n] - base[n]) / base[n]:+.1f}%" for n in names) + " |")
        md.append("")
        md.append("bpp vs best non-bpp format: " + ", ".join(
            f"{n} {100 * (rows['bpp'][n] - best[n]) / best[n]:+.1f}%" for n in names))
        md.append("")

    # summary
    fmts = ["JSON (indent 2)", "JSON (minified)", "YAML", "TOON", "bpp", "bpp + primer"]
    md += ["## Summary (sum over all examples)", "",
           "| format | " + " | ".join(names) + " | " + " | ".join(f"vs JSON {n}" for n in names) + " |",
           "|---|" + "---:|" * (2 * len(names))]
    tot = {f: {n: sum(results[e][f][n] for e in results if f in results[e]) for n in names}
           for f in fmts}
    for f in fmts:
        md.append(f"| {f} | " + " | ".join(str(tot[f][n]) for n in names) + " | " + " | ".join(
            f"{100 * (tot[f][n] - tot[fmts[0]][n]) / tot[fmts[0]][n]:+.1f}%" for n in names) + " |")

    RES.mkdir(parents=True, exist_ok=True)
    (RES / "tokens.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (RES / "tokens.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
