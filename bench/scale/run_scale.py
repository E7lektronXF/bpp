"""Scale comprehension benchmark: 100/500/1000-row payloads, every wrong answer classified.

    python bench/scale/run_scale.py --dry-run                      # questions, answers, sizes, plan
    python bench/scale/run_scale.py --model llama3.2:3b            # Ollama on this machine
    python bench/scale/run_scale.py --model qwen3:8b --num-ctx 32768
    NVIDIA_API_KEY=... python bench/scale/run_scale.py --provider nvidia --model openai/gpt-oss-120b \\
        --num-ctx 131072
    python bench/scale/run_scale.py --report --model llama3.2:3b   # rebuild the report only

Datasets: NetClaw's five network tables (BGP peers, route table, interfaces, OSPF neighbors,
NSG rules; generators from netclaw `benchmarks/gcf_vs_toon_benchmark.py`, seed 42) and nested
orders (blackwell-systems' adversarial fixture). Formats: pretty JSON, GCF generic
(`gcf-python`), bpp with and without the &n dictionary; more with `--formats`, e.g.
`bpp:keep_order=1`. Every bpp payload must round-trip losslessly or the run stops.

Each request carries one payload in one format and all 15 questions (`--mode batch`), or a single
question (`--mode single`, blackwell's protocol; Ollama reuses the cached payload prefix).
The data is labelled with the format name only, no primer. A prompt that does not fit the
model's context (`--num-ctx`, counted with the model's own tokenizer) is skipped and reported,
never truncated. Answers are saved as they arrive; running the same command again resumes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as ds  # noqa: E402
from common import (DEFAULT_FORMATS, RES, Model, counter, fetch_tokenizers, label,  # noqa: E402
                    render, roundtrips)
from questions import flat, questions  # noqa: E402
from taxonomy import CATEGORIES, classify, refs_of  # noqa: E402

from run_qa import grade, parse_answers  # noqa: E402

SYSTEM_BATCH = ("You answer questions about the data you are given. Use only the data. "
                "Reply with one line per question in the form `<number>: <answer>` and nothing else. "
                "Give bare values: numbers as digits, text exactly as it appears in the data.")
SYSTEM_SINGLE = ("You answer a question about the data you are given. Use only the data. "
                 "Reply with the answer only: a bare value, numbers as digits, "
                 "text exactly as it appears in the data.")
TEMPLATE_TOKENS = 64
REORDERED: set = set()  # (dataset, rows, format) whose decoded key order differs (SPEC §4.3)  # chat template overhead, kept free in the context budget

# Rough prompt-processing speeds (tokens/s) on an RTX 3070 8 GB, for the time estimate only.
PP_SPEED = {"llama3": 2500, "qwen3": 1000, "o200k": 3000}


def prompt_batch(fmt, text, qs):
    qlines = "\n".join(f"{i}. {q.text}" for i, q in enumerate(qs, 1))
    return f"Data ({label(fmt)}):\n```\n{text}```\n\nQuestions:\n{qlines}"


def prompt_single(fmt, text, q):
    return f"Data ({label(fmt)}):\n```\n{text}```\n\nQuestion: {q.text}"


def build(datasets, sizes, formats):
    """[(dataset, n, payload, rows, questions, {fmt: text})], checking every round trip."""
    out = []
    for name in datasets:
        for n in sizes:
            p = ds.payload(name, n)
            texts = {f: render(f, p) for f in formats}
            for f, t in texts.items():
                if not roundtrips(f, t, p):
                    if f.startswith("bpp"):
                        raise SystemExit(f"LOSSLESS CHECK FAILED: {name} n={n} format {f}")
                    print(f"note: {f} does not round-trip {name} n={n}", file=sys.stderr)
                elif not roundtrips(f, t, p, ordered=True):
                    REORDERED.add((name, n, f))
            from bpp.encoder import _extract_refs
            interned = set(_extract_refs(p)[1])
            qs = questions(name, p, interned)
            assert len(qs) >= 15, (name, n)
            out.append((name, n, p, [flat(r) for r in p[ds.ROWS_KEY[name]]], qs, texts))
    return out


def requests(built, mode, formats):
    """[(key, dataset, n, fmt, system, user, [question indexes])] in cache-friendly order."""
    out = []
    for name, n, _, _, qs, texts in built:
        for f in formats:
            if mode == "batch":
                out.append(((name, n, f, -1), name, n, f, SYSTEM_BATCH,
                            prompt_batch(f, texts[f], qs), list(range(len(qs)))))
            else:
                for i, q in enumerate(qs):
                    out.append(((name, n, f, i), name, n, f, SYSTEM_SINGLE,
                                prompt_single(f, texts[f], q), [i]))
    return out


def size_table(built, formats, fams):
    import tiktoken
    o200k = tiktoken.get_encoding("o200k_base")
    lines = ["| dataset | rows | " + " | ".join(formats) + " |", "|---|---:|" + "---:|" * len(formats)]
    per = {}
    for name, n, _, _, _, texts in built:
        cells = []
        for f in formats:
            t = texts[f]
            o = len(o200k.encode(t, disallowed_special=()))
            per[(name, n, f)] = o
            extra = " / ".join(f"{counter(fam)[0](t):,}" for fam in fams)
            cells.append(f"{o:,}" + (f" ({extra})" if extra else ""))
        lines.append(f"| {name} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines), per


def report(results, model_label, formats, skipped, mode):
    md = [f"# Scale comprehension benchmark: {model_label}", "",
          f"Mode `{mode}`, temperature 0, format name only (no primer). Error rate = wrong / asked; "
          "a skipped cell (prompt does not fit the context) is not asked and is listed below.", ""]
    by = defaultdict(list)
    for r in results:
        by[(r["format"], r["rows"])].append(r)
    sizes = sorted({r["rows"] for r in results})
    md += ["## Error rate by format and size", "",
           "| format | " + " | ".join(f"{n} rows" for n in sizes) + " | all | pointer errors | mean prompt tokens |",
           "|---|" + "---:|" * (len(sizes) + 3)]
    for f in formats:
        rs = [r for r in results if r["format"] == f]
        if not rs:
            continue
        cells = []
        for n in sizes:
            x = by[(f, n)]
            cells.append(f"{100 * sum(not r['ok'] for r in x) / len(x):.1f}% ({len(x)})" if x else "–")
        ptr = sum(r["category"] == "pointer" for r in rs)
        toks = [r["prompt_tokens"] for r in rs if r.get("prompt_tokens")]
        md.append(f"| {f} | " + " | ".join(cells)
                  + f" | **{100 * sum(not r['ok'] for r in rs) / len(rs):.1f}%** | {ptr} | "
                  + (f"{sum(toks) / len(toks):,.0f}" if toks else "–") + " |")
    md += ["", "## Wrong answers by cause", "",
           "| format | " + " | ".join(CATEGORIES) + " |", "|---|" + "---:|" * len(CATEGORIES)]
    for f in formats:
        c = Counter(r["category"] for r in results if r["format"] == f and not r["ok"])
        if any(r["format"] == f for r in results):
            md.append(f"| {f} | " + " | ".join(str(c[k]) for k in CATEGORIES) + " |")
    qtypes = ["lookup", "reverse", "count", "aggregate", "position"]
    md += ["", "## Error rate by question type", "",
           "| format | " + " | ".join(qtypes) + " | interned value |", "|---|" + "---:|" * (len(qtypes) + 1)]
    for f in formats:
        rs = [r for r in results if r["format"] == f]
        if not rs:
            continue
        cells = []
        for sel in [[r for r in rs if r["qtype"] == t] for t in qtypes] + [[r for r in rs if r["interned"]]]:
            cells.append(f"{100 * sum(not r['ok'] for r in sel) / len(sel):.0f}% ({len(sel)})" if sel else "–")
        md.append(f"| {f} | " + " | ".join(cells) + " |")
    md += ["", "## Per dataset (errors / asked)", "",
           "| dataset | rows | " + " | ".join(formats) + " |", "|---|---:|" + "---:|" * len(formats)]
    for name, n in sorted({(r["dataset"], r["rows"]) for r in results}, key=lambda t: (t[0], t[1])):
        cells = []
        for f in formats:
            x = [r for r in results if (r["dataset"], r["rows"], r["format"]) == (name, n, f)]
            cells.append(f"{sum(not r['ok'] for r in x)}/{len(x)}" if x else "skipped")
        md.append(f"| {name} | {n} | " + " | ".join(cells) + " |")
    if skipped:
        md += ["", "## Skipped (does not fit the context)", ""]
        md += [f"* {name} {n} rows, {f}: {tok:,} prompt tokens" for name, n, f, tok in skipped]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", default="ollama", choices=["ollama", "groq", "nvidia", "openai"])
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--host", help="Ollama URL (default $OLLAMA_HOST or http://localhost:11434)")
    ap.add_argument("--base-url", help="OpenAI-compatible endpoint (overrides the provider's)")
    ap.add_argument("--no-think", action="store_true",
                    help="turn off reasoning (chat_template_kwargs enable_thinking=false)")
    ap.add_argument("--num-ctx", type=int, default=32768,
                    help="context window; Ollama loads the model with it (default 32768)")
    ap.add_argument("--max-tokens", type=int, help="output limit (default: Ollama 600, groq 2000, else 4000)")
    ap.add_argument("--mode", choices=["batch", "single"], default="batch")
    ap.add_argument("--datasets", nargs="*", default=list(ds.GENERATORS))
    ap.add_argument("--sizes", nargs="*", type=int, default=list(ds.SIZES))
    ap.add_argument("--formats", nargs="*", default=DEFAULT_FORMATS)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--tag", default="", help="suffix for the result files (e.g. a variant name)")
    ap.add_argument("--dry-run", action="store_true", help="print questions, sizes and the plan; no model calls")
    ap.add_argument("--report", action="store_true", help="rebuild the report from saved answers")
    ap.add_argument("--fetch-tokenizers", action="store_true",
                    help="download the Llama 3 / Qwen3 / Gemma 3 / DeepSeek V3 tokenizers (npm) for context checks")
    a = ap.parse_args()
    if a.fetch_tokenizers:
        fetch_tokenizers()
        return 0

    model = Model(a.provider, a.model, host=a.host, num_ctx=a.num_ctx, max_tokens=a.max_tokens,
                  base_url=a.base_url, no_think=a.no_think)
    count, exact = counter(model.fam)
    built = build(a.datasets, a.sizes, a.formats)
    reqs = requests(built, a.mode, a.formats)
    ntok, data_tok = {}, {}
    for key, name, n, f, system, user, qidx in reqs:
        if a.mode == "batch":
            ntok[key] = count(system) + count(user) + TEMPLATE_TOKENS
        else:  # the payload is shared by the 15 requests: count it once
            if (name, n, f) not in data_tok:
                data_tok[(name, n, f)] = count(system) + count(user.rsplit("\n\nQuestion: ", 1)[0])
            ntok[key] = data_tok[(name, n, f)] + count(user.rsplit("\n\nQuestion: ", 1)[1]) + TEMPLATE_TOKENS + 4
    skipped = sorted({(k[0], k[1], k[2], ntok[k]) for k in ntok if not model.fits(ntok[k])},
                     key=lambda t: (t[0], t[1], a.formats.index(t[2])))
    todo = [r for r in reqs if model.fits(ntok[r[0]])]
    stem = model.stem + ("-" + a.tag if a.tag else "") + ("-single" if a.mode == "single" else "")
    RES.mkdir(parents=True, exist_ok=True)

    if a.dry_run:
        for name, n, _, _, qs, _ in built:
            print(f"## {name}, {n} rows")
            for i, q in enumerate(qs, 1):
                tags = f" [{', '.join(q.tags)}]" if q.tags else ""
                print(f"  {i:2}. ({q.qtype}{tags}) {q.text}\n      -> {q.expected!r}")
        fams = [model.fam] if exact and model.fam != "o200k" else []
        table, _ = size_table(built, a.formats, fams)
        print("\nPayload sizes, o200k tokens" + (f" ({model.fam} tokenizer)" if fams else "") + ":\n")
        print(table)
        if REORDERED:
            print("\nKey order changed on decode (values and types equal; a column moved last):")
            print("  " + ", ".join(sorted({f"{d}/{f}" for d, _, f in REORDERED})))
        print(f"\nModel {a.model} ({a.provider}), context {a.num_ctx:,}, output limit {model.max_tokens}, "
              f"tokenizer {model.fam}"
              + ("" if exact else " (estimate: cl100k + 30%)" if model.fam == "unknown"
                 else " (ESTIMATE: run --fetch-tokenizers)"))
        tot = sum(ntok[r[0]] for r in todo)
        print(f"{len(todo)} requests x {a.repeats} repeat(s) ({a.mode} mode), "
              f"{tot * a.repeats:,} prompt tokens; {len(skipped)} cells skipped as too large:")
        for name, n, f, tok in skipped:
            print(f"  skip {name} {n} rows {f}: {tok:,} tokens")
        if a.provider == "ollama":
            secs = tot * a.repeats / PP_SPEED.get(model.fam, 1500) + len(todo) * a.repeats * 8
            print(f"rough time on an RTX 3070 (no prefix cache): {secs / 60:.0f} min")
        return 0

    partial = RES / f"{stem}.jsonl"
    done = {}
    if partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["dataset"], r["rows"], r["format"], r["qindex"], r["repeat"])] = r
    if not a.report:
        if not model.ready:
            raise SystemExit(f"{a.provider}: API key not set")
        print(f"{len(todo)} requests x {a.repeats}, {len(skipped)} skipped as too large; "
              f"{len(done)} answers already saved in {partial.name}", flush=True)
    index = {(name, n): (rows, qs, texts) for name, n, _, rows, qs, texts in built}
    refs = {(name, n, f): refs_of(t) if f.startswith("bpp") else {}
            for name, n, _, _, _, ts in built for f, t in ts.items()}
    for rep in range(a.repeats):
        for key, name, n, f, system, user, qidx in todo:
            if a.report or all((name, n, f, i, rep) in done for i in qidx):
                continue
            t0 = time.time()
            text, stop, n_in = model.ask(system, user)
            rows, qs, _ = index[(name, n)]
            answers = parse_answers(text, len(qs)) if a.mode == "batch" else [text.strip()]
            with partial.open("a", encoding="utf-8") as fh:
                for i, ans in zip(qidx, answers):
                    q = qs[i]
                    ok = grade(ans, q.expected, q.kind)
                    cat, detail = ("", "") if ok else classify(ans, q, rows, refs[(name, n, f)], stop)
                    r = {"dataset": name, "rows": n, "format": f, "qindex": i, "repeat": rep,
                         "qtype": q.qtype, "interned": "interned" in q.tags, "question": q.text,
                         "expected": q.expected, "answer": ans, "ok": ok, "category": cat,
                         "detail": detail, "stop": stop, "prompt_tokens": n_in,
                         "est_tokens": ntok[key]}
                    done[(name, n, f, i, rep)] = r
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            wrong = sum(not done[(name, n, f, i, rep)]["ok"] for i in qidx)
            print(f"{name:15s} {n:5d} {f:12s} {'' if a.mode == 'batch' else f'q{qidx[0] + 1:<3d}'}"
                  f"wrong {wrong}/{len(qidx)}  in={n_in} est={ntok[key]}  {stop}  {time.time() - t0:.0f}s",
                  flush=True)
    results = [r for r in done.values() if r["format"] in a.formats and r["dataset"] in a.datasets
               and r["rows"] in a.sizes]
    if not results:
        print("no answers yet")
        return 0
    md = report(results, f"{a.model} ({a.provider})", a.formats, skipped, a.mode)
    (RES / f"{stem}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
