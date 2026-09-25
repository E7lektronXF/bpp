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
from bpp.encoder import encode_md  # noqa: E402
from bpp.formats import dumps  # noqa: E402
from bpp.tokens import available_counters  # noqa: E402

RES = ROOT / "bench" / "results"


def all_renderings(name: str) -> dict[str, str]:
    data, fmt = load(name)
    if fmt != "md":
        out = renderings(data, keep_order=fmt == "csv")
        out["bpp --no-refs"] = dumps(data, "bpp", refs=False, keep_order=fmt == "csv")
        return out
    # The source Markdown is what a user would otherwise paste; bpp is encode_md(source).
    src = (EX / EXAMPLES[name][0]).read_text(encoding="utf-8")
    out = renderings(data, source=src)
    out = {"Markdown (source)": out.pop("Markdown"), "Markdown (normalized)": dumps(data, "md"), **out}
    out["bpp --no-refs"] = encode_md(src, refs=False)
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
    (RES / "tables.md").write_text(doc_tables(results), encoding="utf-8")
    print("\n".join(md))


# ------------------------------------------------ tables for README / BENCHMARK

README_ROWS = {  # example -> (English label, Turkish label)
    "employees": ("60×10 table (CSV)", "60×10 tablo (CSV)"),
    "config": ("nested config (YAML)", "iç içe config (YAML)"),
    "plan": ("project plan with deps (JSON)", "yapılandırılmış plan (JSON)"),
    "project_plan": ("Markdown checklist plan", "Markdown checklist planı"),
    "orders": ("API response with nested objects", "iç içe nesneli API yanıtı"),
    "logs": ("repetitive logs", "tekrarlı loglar"),
}
ALT = {"JSON (indent 2)": "JSON", "JSON (minified)": "JSON min", "YAML": "YAML", "CSV": "CSV",
       "Markdown (source)": "Markdown", "TOON": "TOON"}


def _best(rows, n):
    """(name, count) of the smallest non-bpp format (the normalized Markdown is not a source)."""
    return min(((ALT[f], v[n]) for f, v in rows.items() if f in ALT), key=lambda t: t[1])


def doc_tables(results) -> str:
    """The token tables of README(.tr).md and BENCHMARK(.tr).md, from the measured results."""
    names = [n for n in ("o200k", "claude2") if n in next(iter(results.values()))["bpp"]]
    tot = {f: {n: sum(r[f][n] for r in results.values() if f in r) for n in names}
           for f in ("JSON (indent 2)", "JSON (minified)", "YAML", "TOON", "bpp", "bpp + primer")}

    def pct(a, b):
        return 100 * (a - b) / b

    def cell(rows, f, n):
        return str(rows[f][n]) if f in rows else "–"

    out = ["# Tables for the README and BENCHMARK", "",
           "Generated by `bench/run_tokens.py` from `tokens.json`; copied into the documents.", ""]
    n = names[0]
    long = {"JSON min": "minified JSON"}
    out += [f"## README.md ({n})", "",
            "| data | JSON | minified JSON | YAML | TOON | Markdown | **bpp** | bpp vs best alternative |",
            "|---|---:|---:|---:|---:|---:|---:|---|"]
    for ex, rows in results.items():
        alt, v = _best(rows, n)
        out.append(f"| {README_ROWS[ex][0]} | " + " | ".join(cell(rows, f, n) for f in (
            "JSON (indent 2)", "JSON (minified)", "YAML", "TOON", "Markdown (source)"))
            + f" | **{rows['bpp'][n]}** | −{abs(round(pct(rows['bpp'][n], v)))}% vs {long.get(alt, alt)} |")
    t = {f: tot[f][n] for f in tot}
    out.append(f"| **total** | {t['JSON (indent 2)']} | {t['JSON (minified)']} | {t['YAML']} | "
               f"{t['TOON']} | | **{t['bpp']}** | **−{abs(round(pct(t['bpp'], t['JSON (indent 2)'])))}% vs "
               f"JSON, −{abs(round(pct(t['bpp'], t['TOON'])))}% vs TOON** |")
    out += [""] + [f"{m}: bpp vs JSON {pct(tot['bpp'][m], tot['JSON (indent 2)'][m]):+.1f}%, "
                   f"vs TOON {pct(tot['bpp'][m], tot['TOON'][m]):+.1f}%" for m in names] + [""]
    tr = {"JSON min": "min. JSON"}
    out += [f"## README.tr.md ({n})", "",
            "| örnek | JSON | minified JSON | TOON | **.bpp** | .bpp en iyi rakibe göre |",
            "|---|---:|---:|---:|---:|---|"]
    for ex, rows in results.items():
        alt, v = _best(rows, n)
        best = (f"−%{abs(round(pct(rows['bpp'][n], v)))} (kaynak Markdown: {v})" if alt == "Markdown"
                else f"−%{abs(round(pct(rows['bpp'][n], v)))} ({tr.get(alt, alt)})")
        out.append(f"| {README_ROWS[ex][1]} | " + " | ".join(cell(rows, f, n) for f in (
            "JSON (indent 2)", "JSON (minified)", "TOON")) + f" | **{rows['bpp'][n]}** | {best} |")
    for m in names:
        for lang, total, vs in (("BENCHMARK.md", "**total**", "**{a:.1f}%** vs JSON, **{b:.1f}%** vs TOON"),
                                ("BENCHMARK.tr.md", "**toplam**", "JSON'a göre **{a:.1f}%**, TOON'a göre **{b:.1f}%**")):
            out += ["", f"## {lang} ({m})", "",
                    "| example | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | "
                    "bpp vs best alternative |" if lang == "BENCHMARK.md" else
                    "| örnek | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | "
                    "bpp vs en iyi rakip |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
            for ex, rows in results.items():
                alt, v = _best(rows, m)
                out.append(f"| {ex} | " + " | ".join(cell(rows, f, m) for f in (
                    "JSON (indent 2)", "JSON (minified)", "YAML", "CSV", "Markdown (source)", "TOON"))
                    + f" | **{rows['bpp'][m]}** | {rows['bpp + primer'][m]} | "
                    f"**{pct(rows['bpp'][m], v):.1f}%** ({alt}) |")
            t = {f: tot[f][m] for f in tot}
            out.append(f"| {total} | {t['JSON (indent 2)']} | {t['JSON (minified)']} | {t['YAML']} | | | "
                       f"{t['TOON']} | **{t['bpp']}** | {t['bpp + primer']} | " + vs.format(
                           a=pct(t["bpp"], t["JSON (indent 2)"]), b=pct(t["bpp"], t["TOON"])) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
