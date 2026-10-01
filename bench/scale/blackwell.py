"""Reproduce blackwell-systems' bpp comprehension evaluation, with bpp refs on and off.

    python bench/scale/blackwell.py --check GCF_REPO       # our payloads == their published ones
    python bench/scale/blackwell.py --analyze-logs GCF_REPO  # classify every wrong answer in their logs
    python bench/scale/blackwell.py --dry-run --model llama3.2:3b --num-ctx 65536
    python bench/scale/blackwell.py --model llama3.2:3b --num-ctx 65536 --orders 500

GCF_REPO is a clone of https://github.com/blackwell-systems/gcf (the evaluation is in
`eval/bpp-comprehension`). The harness itself (gcf-go `eval/generic_comprehension_test.go`,
with uncommitted edits for this study) is ported here:

* data: the adversarial orders fixture (`data.orders`; identical to their
  `encodings/adv-{500,1000}-json.txt`, and our bpp and GCF encodings are byte-identical to theirs);
* 19 questions: the 13 canonical ones verbatim, plus 6 deep lookups (email, SKU of the first
  item, tier of the orders at 50% and 100% depth) whose names and answers are in their logs but
  whose wording is not published; ours follows the canonical wording;
* one request per question, no system prompt: "Here is order data in BPP format:\\n\\n<data>\\n\\n
  Question: <q>", temperature 0.2, max_tokens 200 (all as in their harness);
* grading: their numericVerify / stringVerify / unique-statuses check, ported.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as ds  # noqa: E402
from common import RES, Model, counter, render, roundtrips  # noqa: E402
from questions import flat  # noqa: E402
from taxonomy import CATEGORIES, classify, refs_of  # noqa: E402

FORMATS = ["gcf", "json", "bpp-refs", "bpp-norefs"]
EVAL = Path("eval") / "bpp-comprehension"


# ---------------------------------------------------------------- grading (ported)

def numeric_verify(expected: str, resp: str) -> bool:
    resp = resp.strip().replace(",", "").replace("$", "")
    if resp == expected:
        return True
    try:
        if math.isclose(float(expected), float(resp), abs_tol=0.1 - 1e-12):
            return True
    except ValueError:
        pass
    return expected in resp


def string_verify(expected: str, resp: str) -> bool:
    resp = resp.strip().strip('`"')
    return resp.casefold() == expected.casefold() or expected.lower() in resp.lower()


def statuses_verify(expected: str, resp: str) -> bool:
    def norm(s):
        return ", ".join(p.strip() for p in s.strip().lower().split(","))
    return norm(resp) == norm(expected) or all(t in resp.lower() for t in expected.split(", "))


# --------------------------------------------------------------------- questions

def bq(name, text, expected, verify, qtype, row=None, col=None):
    return SimpleNamespace(name=name, text=text, expected=expected, verify=verify, qtype=qtype,
                           row=row, col=col, tags=[])


def build_questions(orders: list) -> list:
    n = len(orders)
    last = orders[-1]
    shipped = [o for o in orders if o["status"] == "shipped"]
    qs = [
        bq("order_count", "How many orders are in this data? Reply with ONLY a number.",
           str(n), numeric_verify, "count"),
        bq("first_customer_name", "What is the customer name on the first order? Reply with ONLY the name.",
           orders[0]["customer"]["name"], string_verify, "lookup", 0, ("customer", "name")),
        bq("last_order_status", "What is the status of the last order? Reply with ONLY the status.",
           last["status"], string_verify, "lookup", n - 1, ("status",)),
        bq("total_items_first_order",
           "How many line items are in the first order? Reply with ONLY a number.",
           str(len(orders[0]["items"])), numeric_verify, "count"),
        bq("customer_email_order5",
           "What is the customer email on order ORD-0005? Reply with ONLY the email address.",
           orders[4]["customer"]["email"], string_verify, "lookup", 4, ("customer", "email")),
        bq("count_shipped", "How many orders have status 'shipped'? Reply with ONLY a number.",
           str(len(shipped)), numeric_verify, "count"),
        bq("count_premium_customers",
           "How many orders have a customer with tier 'premium'? Reply with ONLY a number.",
           str(sum(o["customer"]["tier"] == "premium" for o in orders)), numeric_verify, "count"),
        bq("highest_total", "What is the highest order total? Reply with ONLY the number (e.g. 123.45).",
           f"{max(o['total'] for o in orders):.2f}", numeric_verify, "aggregate"),
        bq("sku_first_item_order3",
           "What is the SKU of the first item in order ORD-0003? Reply with ONLY the SKU.",
           orders[2]["items"][0]["sku"], string_verify, "lookup", 2, ("items", 0, "sku")),
        bq("total_revenue_shipped", "What is the sum of all order totals where status is 'shipped'? "
           "Reply with ONLY the number (e.g. 1234.56).",
           f"{sum(o['total'] for o in shipped):.2f}", numeric_verify, "aggregate"),
        bq("unique_statuses",
           "List all unique order statuses, comma-separated, alphabetically. Reply with ONLY the list.",
           ", ".join(sorted({o["status"] for o in orders})), statuses_verify, "list"),
        bq("count_orders_with_3plus_items",
           "How many orders have 3 or more line items? Reply with ONLY a number.",
           str(sum(len(o["items"]) >= 3 for o in orders)), numeric_verify, "count"),
        bq("customer_tier_last_order",
           "What is the customer tier on the last order? Reply with ONLY the tier.",
           last["customer"]["tier"], string_verify, "lookup", n - 1, ("customer", "tier")),
    ]
    for depth, i in (("mid", n // 2 - 1), ("deep", n - 1)):
        oid = orders[i]["orderId"]
        qs += [
            bq(f"email_{depth}_{oid}",
               f"What is the customer email on order {oid}? Reply with ONLY the email address.",
               orders[i]["customer"]["email"], string_verify, "lookup", i, ("customer", "email")),
            bq(f"sku_{depth}_{oid}",
               f"What is the SKU of the first item in order {oid}? Reply with ONLY the SKU.",
               orders[i]["items"][0]["sku"], string_verify, "lookup", i, ("items", 0, "sku")),
            bq(f"tier_{depth}_{oid}",
               f"What is the customer tier on order {oid}? Reply with ONLY the tier.",
               orders[i]["customer"]["tier"], string_verify, "lookup", i, ("customer", "tier")),
        ]
    return qs


def prompt(fmt: str, text: str, question: str) -> str:
    name = "BPP" if fmt.startswith("bpp") else fmt.upper()
    return f"Here is order data in {name} format:\n\n{text}\n\nQuestion: {question}"


def wrong_kind(q, answer, rows, refs, stop=None):
    """Our taxonomy on one of their questions (their grading decided it is wrong)."""
    q2 = SimpleNamespace(expected=q.expected, qtype=q.qtype if q.qtype != "list" else "other",
                         row=q.row, col=q.col)
    if q.qtype in ("count", "aggregate"):
        q2.expected = float(q.expected)
    return classify(answer, q2, rows, refs, stop)


# ------------------------------------------------------------------ their logs

_LOG = re.compile(r"\s(PASS|FAIL|SKIP) (\S+)\s+(\S+)\s+(?:\[.*?\] expected=(\".*?\") got=(\".*\")|error)")


def analyze_logs(repo: Path) -> str:
    logs = sorted((repo / EVAL / "logs").glob("*.log"))
    cnt = defaultdict(Counter)
    examples = defaultdict(list)
    graded = Counter()
    cache = {}
    for path in logs:
        n = int(re.search(r"-N(\d+)-", path.name).group(1))
        if n not in cache:
            orders = ds.orders(n)["orders"]
            refs = refs_of(render("bpp-refs", {"orders": orders}))
            cache[n] = ({q.name: q for q in build_questions(orders)}, [flat(o) for o in orders], refs)
        qmap, rows, refs = cache[n]
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _LOG.search(line)
            if not m or m.group(1) == "SKIP":
                continue
            mark, name, fmt = m.group(1), m.group(2), m.group(3)
            graded[fmt] += 1
            if mark == "PASS":
                continue
            got = json.loads(m.group(5))
            kind, detail = wrong_kind(qmap[name], got, rows, refs if fmt == "bpp" else {})
            cnt[fmt][kind] += 1
            if kind == "pointer":
                examples[fmt].append(f"{path.name.split('-2026')[0]} {name}: {got!r} ({detail})")
    md = [f"Wrong answers in blackwell's {len(logs)} published logs, by cause (our taxonomy):", "",
          "| format | graded | wrong | " + " | ".join(CATEGORIES) + " |",
          "|---|---:|---:|" + "---:|" * len(CATEGORIES)]
    for fmt in ("gcf", "json", "bpp"):
        c = cnt[fmt]
        md.append(f"| {fmt} | {graded[fmt]} | {sum(c.values())} | "
                  + " | ".join(str(c[k]) for k in CATEGORIES) + " |")
    md += ["", f"bpp pointer answers ({len(examples['bpp'])}):"] + [f"* {x}" for x in examples["bpp"]]
    return "\n".join(md) + "\n"


def check(repo: Path) -> int:
    enc = repo / EVAL / "encodings"
    bad = 0
    for n in (500, 1000):
        d = ds.orders(n)
        theirs = json.loads((enc / f"adv-{n}-json.txt").read_text())
        rows = [("data", json.dumps(theirs) == json.dumps(d))]
        for fmt, f in (("bpp-refs", "bpp"), ("gcf", "gcf")):
            rows.append((fmt, render(fmt, d).rstrip("\n") == (enc / f"adv-{n}-{f}.txt").read_text().rstrip("\n")))
        for fmt in FORMATS:
            rows.append((f"{fmt} round-trip", roundtrips(fmt, render(fmt, d), d)))
        for what, ok in rows:
            print(f"N={n:5d} {what:22s} {'identical' if ok else 'DIFFERENT'}")
            bad += not ok
    return 1 if bad else 0


# ------------------------------------------------------------------------- run

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", type=Path, metavar="GCF_REPO")
    ap.add_argument("--analyze-logs", type=Path, metavar="GCF_REPO")
    ap.add_argument("--provider", default="ollama", choices=["ollama", "groq", "nvidia", "openai"])
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--host")
    ap.add_argument("--base-url")
    ap.add_argument("--num-ctx", type=int, default=65536)
    ap.add_argument("--max-tokens", type=int, default=200, help="their harness: 200")
    ap.add_argument("--temperature", type=float, default=0.2, help="their runs: 0.2")
    ap.add_argument("--orders", nargs="*", type=int, default=[500, 1000])
    ap.add_argument("--formats", nargs="*", default=FORMATS)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check(a.check)
    if a.analyze_logs:
        md = analyze_logs(a.analyze_logs)
        RES.mkdir(parents=True, exist_ok=True)
        (RES / "blackwell-logs.md").write_text(md, encoding="utf-8")
        print(md)
        return 0

    model = Model(a.provider, a.model, host=a.host, num_ctx=a.num_ctx, max_tokens=a.max_tokens,
                  base_url=a.base_url, temperature=a.temperature)
    count, exact = counter(model.fam)
    plan, skipped = [], []
    cells = {}
    for n in a.orders:
        d = ds.orders(n)
        orders = d["orders"]
        qs = build_questions(orders)
        rows = [flat(o) for o in orders]
        for fmt in a.formats:
            text = render(fmt, d)
            assert roundtrips(fmt, text, d), (n, fmt)
            refs = refs_of(text) if fmt.startswith("bpp") else {}
            tok = count(prompt(fmt, text, qs[0].text)) + 32
            cells[(n, fmt)] = tok
            if not model.fits(tok):
                skipped.append((n, fmt, tok))
                continue
            for q in qs:
                plan.append((n, fmt, q, prompt(fmt, text, q.text), rows, refs))
    print(f"{a.model} ({a.provider}), context {a.num_ctx:,}, tokenizer {model.fam}"
          f"{'' if exact else ' (estimate)'}")
    for (n, fmt), tok in cells.items():
        print(f"  N={n:5d} {fmt:11s} {tok:8,} prompt tokens{'  SKIPPED: does not fit' if (n, fmt, tok) in skipped else ''}")
    print(f"{len(plan)} requests x {a.runs} run(s)")
    if a.dry_run:
        for n in a.orders:
            print(f"\n## N={n}")
            for q in build_questions(ds.orders(n)["orders"]):
                print(f"  {q.name:30s} {q.expected!r:40s} {q.text}")
        return 0
    if not model.ready:
        raise SystemExit(f"{a.provider}: API key not set")
    RES.mkdir(parents=True, exist_ok=True)
    out = RES / f"blackwell-{model.stem}.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["orders"], r["format"], r["question"], r["run"]))
    for run in range(a.runs):
        for n, fmt, q, user, rows, refs in plan:
            if (n, fmt, q.name, run) in done:
                continue
            text, stop, n_in = model.ask(None, user)
            ok = q.verify(q.expected, text)
            kind, detail = ("", "") if ok else wrong_kind(q, text, rows, refs, stop)
            r = {"orders": n, "format": fmt, "question": q.name, "run": run, "expected": q.expected,
                 "answer": text.strip(), "ok": ok, "category": kind, "detail": detail, "stop": stop,
                 "prompt_tokens": n_in}
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"N={n} {fmt:11s} {q.name:30s} {'PASS' if ok else 'FAIL ' + kind:20s} {text.strip()[:40]!r}",
                  flush=True)
    results = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    md = [f"# blackwell's evaluation on {a.model} ({a.provider}), temperature {a.temperature}", "",
          "| N | format | error rate | wrong / graded | " + " | ".join(CATEGORIES) + " |",
          "|---:|---|---:|---:|" + "---:|" * len(CATEGORIES)]
    for n in a.orders:
        for fmt in a.formats:
            rs = [r for r in results if r["orders"] == n and r["format"] == fmt]
            if not rs:
                md.append(f"| {n} | {fmt} | skipped | | " + " | " * (len(CATEGORIES) - 1) + " |")
                continue
            w = [r for r in rs if not r["ok"]]
            c = Counter(r["category"] for r in w)
            md.append(f"| {n} | {fmt} | {100 * len(w) / len(rs):.1f}% | {len(w)}/{len(rs)} | "
                      + " | ".join(str(c[k]) for k in CATEGORIES) + " |")
    (RES / f"blackwell-{model.stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
