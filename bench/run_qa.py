"""Comprehension benchmark: ask a model the same questions about the same data in
every format and compare accuracy.

    python bench/run_qa.py --dry-run          # show questions, answers, prompt sizes
    ANTHROPIC_API_KEY=... python bench/run_qa.py [--model claude-opus-5] [--repeats 3]
    NVIDIA_API_KEY=nvapi-... python bench/run_qa.py --provider nvidia [--model openai/gpt-oss-20b]
    OPENAI_API_KEY=... python bench/run_qa.py --provider openai --base-url URL --model NAME

`--provider nvidia` uses NVIDIA's OpenAI-compatible API (build.nvidia.com); `openai`
works with any OpenAI-compatible endpoint. These need no extra package.

Each (example, format) pair is one request containing the data and all 10
questions. Expected answers are computed from the data, so grading is
automatic. Without an API key the script only prints what it would do.
The Anthropic provider requires `pip install anthropic` (or `pip install ".[api]"`).

Refusal fallbacks are deliberately NOT enabled: a fallback would answer with a
different model and contaminate the comparison. Refusals are counted as wrong
and reported.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

from make_examples import EX, EXAMPLES, load  # noqa: E402

from bpp.cli import renderings  # noqa: E402

RES = ROOT / "bench" / "results"
STATUS_HINT = "(answer with one of: todo, doing, done, cancelled; checkboxes mean [ ]=todo, [x]=done, [/]=doing, [-]=cancelled)"

SYSTEM = ("You answer questions about the data you are given. Use only the data. "
          "Reply with one line per question in the form `<number>: <answer>` and nothing else. "
          "Give bare values: numbers as digits, yes/no for yes/no questions, "
          "lists as comma-separated values.")


# ---------------------------------------------------------------- questions
# Each question: (text, expected, kind); kind in num | str | list | bool | contains

def q_employees(rows):
    by = {r["id"]: r for r in rows}
    top = max(rows, key=lambda r: r["salary"])
    assert sum(r["salary"] == top["salary"] for r in rows) == 1
    return [
        ("How many employees are listed?", len(rows), "num"),
        ("What is the name of the employee with id 17?", by[17]["name"], "str"),
        ("What is the salary of the employee with id 42?", by[42]["salary"], "num"),
        ("In which city does the employee with id 8 work?", by[8]["city"], "str"),
        ("How many employees work in the Sales department?",
         sum(r["department"] == "Sales" for r in rows), "num"),
        ("How many employees are active?", sum(r["active"] is True for r in rows), "num"),
        ("What is the manager_id of the employee with id 25?", by[25]["manager_id"], "num"),
        ("What is the email address of the employee with id 33?", by[33]["email"], "str"),
        ("What is the name of the employee with the highest salary?", top["name"], "str"),
        ("How many employees have a rating of 4.5 or higher?",
         sum(r["rating"] >= 4.5 for r in rows), "num"),
    ]


def q_config(c):
    return [
        ("What port does the server listen on?", c["server"]["port"], "num"),
        ("What is the cache TTL in seconds?", c["cache"]["ttl_s"], "num"),
        ("What is the maximum pool size of the primary database?",
         c["database"]["primary"]["pool"]["max"], "num"),
        ("What is the host of the second database replica?",
         c["database"]["replicas"][1]["host"], "str"),
        ("Is the gift_cards feature enabled?", c["features"]["gift_cards"], "bool"),
        ("How many rotated log files are kept?", c["logging"]["file"]["keep"], "num"),
        ("What is the per-minute rate limit for GET /v1/orders?",
         next(r["per_minute"] for r in c["rate_limits"]
              if r["method"] == "GET" and r["route"] == "/v1/orders"), "num"),
        ("What is the minimum TLS version?", c["server"]["tls"]["min_version"], "str"),
        ("Which beta regions are configured?", c["features"]["beta_regions"], "list"),
        ("What is the service version?", c["service"]["version"], "str"),
    ]


def _flat(steps, parent=None):
    for s in steps:
        yield s, parent
        yield from _flat(s.get("steps", []), s)


def q_plan(p):
    by = {s["id"]: s for s, _ in _flat(p["steps"])}
    return [
        ("What is the status of step 3.2?", by["3.2"]["status"], "str"),
        ("Which step ids does step 5.2 depend on?", by["5.2"]["deps"], "list"),
        ("Who owns step 4?", by["4"]["owner"], "str"),
        ("How many direct sub-steps does step 3 have?", len(by["3"]["steps"]), "num"),
        ("What is the priority of step 4.4?", by["4.4"]["priority"], "str"),
        ("What is the id of the step titled 'Yük testi: 200 işlem/sn'?",
         next(i for i, s in by.items() if s["title"] == "Yük testi: 200 işlem/sn"), "str"),
        ("How many sub-steps (not counting the 6 top-level steps) have status todo?",
         sum(s["status"] == "todo" for s, par in _flat(p["steps"]) if par), "num"),
        ("Which step ids does step 6.1 depend on?", by["6.1"]["deps"], "list"),
        ("Who owns step 5.4?", by["5.4"]["owner"], "str"),
        ("What is the title of step 2.1?", by["2.1"]["title"], "str"),
    ]


def q_project_plan(t):
    flat = list(_flat(t["steps"]))

    class _Nodes:
        # An item's wrapped lines are part of its title (SPEC §7), so look items
        # up by the start of their title.
        def __getitem__(self, title):
            return next((s, par) for s, par in flat
                        if s["title"] == title or s["title"].startswith(title + " "))
    nodes = _Nodes()

    def status(title):
        return nodes[title][0].get("status")
    return [
        (f"What is the status of 'IAM rol modeli'? {STATUS_HINT}", status("IAM rol modeli"), "str"),
        ("How many direct items are in the section 'Keşif ve envanter'?",
         len(nodes["Keşif ve envanter"][0]["steps"]), "num"),
        (f"What is the status of 'Eski raporlama sunucusunun taşınması'? {STATUS_HINT}",
         status("Eski raporlama sunucusunun taşınması"), "str"),
        ("Under which item is 'Hukuk ve uyum' listed? Give that item's title.",
         nodes["Hukuk ve uyum"][1]["title"], "str"),
        ("How many Airflow DAGs were found in the inventory?", 312, "num"),
        ("How many sub-items does 'Veri kalitesi kuralları (Great Expectations)' have?",
         len(nodes["Veri kalitesi kuralları (Great Expectations)"][0]["steps"]), "num"),
        (f"What is the status of 'Katalog: AWS Glue yerine Nessie'? {STATUS_HINT}",
         status("Katalog: AWS Glue yerine Nessie"), "str"),
        ("Which migration wave contains 'Hukuk onayı'? Answer with the wave number only.", 3, "num"),
        (f"How many items in the whole plan have status done? {STATUS_HINT}",
         sum(s.get("status") == "done" for s, _ in _flat(t["steps"])), "num"),
        ("What is the RPO in the disaster recovery plan?", "1 saat", "contains"),
    ]


def q_orders(d):
    o = {x["order_id"]: x for x in d["orders"]}
    it = o["ORD-2026-00007"]["items"][0]
    return [
        ("What is the total of order ORD-2026-00005?", o["ORD-2026-00005"]["total"], "num"),
        ("In which city is the customer of order ORD-2026-00003?",
         o["ORD-2026-00003"]["customer"]["city"], "str"),
        ("How many orders are cancelled?", sum(x["status"] == "cancelled" for x in d["orders"]), "num"),
        ("How many orders use express shipping?",
         sum(x["shipping_method"] == "express" for x in d["orders"]), "num"),
        (f"What quantity of SKU {it['sku']} is in order ORD-2026-00007?", it["qty"], "num"),
        ("How many line items does order ORD-2026-00012 have?", len(o["ORD-2026-00012"]["items"]), "num"),
        ("How many pages of results are there in total?", d["page"]["total_pages"], "num"),
        ("What is the status of order ORD-2026-00018?", o["ORD-2026-00018"]["status"], "str"),
        ("What is the customer name for order ORD-2026-00010?",
         o["ORD-2026-00010"]["customer"]["name"], "str"),
        ("What is the unit price of the first item in order ORD-2026-00015?",
         o["ORD-2026-00015"]["items"][0]["unit_price"], "num"),
    ]


def q_logs(rows):
    by = {r["ts"]: r for r in rows}
    top = max(rows, key=lambda r: r["latency_ms"])
    assert sum(r["latency_ms"] == top["latency_ms"] for r in rows) == 1
    rl = "Rate limit exceeded for API key; request rejected with 429"
    return [
        ("How many log entries have level ERROR?", sum(r["level"] == "ERROR" for r in rows), "num"),
        ("Which service logged the entry at 2026-09-24T10:00:12Z?",
         by["2026-09-24T10:00:12Z"]["service"], "str"),
        ("What is the message of the entry at 2026-09-24T10:00:30Z?",
         by["2026-09-24T10:00:30Z"]["message"], "str"),
        ("What is the latency_ms of the entry at 2026-09-24T10:01:05Z?",
         by["2026-09-24T10:01:05Z"]["latency_ms"], "num"),
        ("How many entries come from auth-service-eu-west-1?",
         sum(r["service"] == "auth-service-eu-west-1" for r in rows), "num"),
        ("How many entries have latency_ms above 25000?", sum(r["latency_ms"] > 25000 for r in rows), "num"),
        ("What is the level of the entry at 2026-09-24T10:00:45Z?",
         by["2026-09-24T10:00:45Z"]["level"], "str"),
        ("How many log entries have level WARN?", sum(r["level"] == "WARN" for r in rows), "num"),
        ("Which service logged the entry with the highest latency_ms?", top["service"], "str"),
        (f"How many entries have the message '{rl}'?", sum(r["message"] == rl for r in rows), "num"),
    ]


QUESTIONS = {"employees": q_employees, "config": q_config, "plan": q_plan,
             "project_plan": q_project_plan, "orders": q_orders, "logs": q_logs}


# ------------------------------------------------------------------- grading

def _norm(s) -> str:
    s = str(s).strip().strip("`'\"*. ")
    return re.sub(r"\s+", " ", s).casefold()


def _num(s):
    try:
        return float(str(s).replace(",", "").strip().strip("`*'\"").rstrip("."))
    except ValueError:
        return None


def grade(answer: str | None, expected, kind: str) -> bool:
    if answer is None:
        return False
    if kind == "num":
        a, e = _num(answer), float(expected)
        return a is not None and abs(a - e) < 1e-6
    if kind == "bool":
        return _norm(answer) in (("yes", "true") if expected else ("no", "false"))
    if kind == "list":
        return {_norm(x) for x in answer.split(",") if x.strip()} == {_norm(x) for x in expected}
    if kind == "contains":
        return _norm(expected) in _norm(answer)
    return _norm(answer) == _norm(expected)


def parse_answers(text: str, n: int) -> list[str | None]:
    out: list[str | None] = [None] * n
    for line in text.splitlines():
        m = re.match(r"\s*\**(\d+)\**\s*[:.)]\s*(.*)$", line)
        if m and 1 <= int(m.group(1)) <= n:
            out[int(m.group(1)) - 1] = m.group(2).strip()
    return out


# ------------------------------------------------------------------ running

def formats_for(name) -> dict[str, str]:
    data, fmt = load(name)
    if fmt == "md":
        # The Markdown source itself, and bpp exactly as `bpp FILE.md` writes it (encode_md).
        source = (EX / EXAMPLES[name][0]).read_text(encoding="utf-8")
        return renderings(data, source=source)
    return renderings(data, keep_order=fmt == "csv")


def prompt(fmt_name: str, text: str, qs) -> str:
    qlines = "\n".join(f"{i}. {q}" for i, (q, _, _) in enumerate(qs, 1))
    return f"Data ({fmt_name}):\n```\n{text}```\n\nQuestions:\n{qlines}"


PROVIDERS = {
    "anthropic": {"env": "ANTHROPIC_API_KEY", "model": "claude-opus-5", "base_url": None},
    "nvidia": {"env": "NVIDIA_API_KEY", "model": "deepseek-ai/deepseek-v4.1-flash",
               "base_url": "https://integrate.api.nvidia.com/v1"},
    "openai": {"env": "OPENAI_API_KEY", "model": "gpt-5-mini", "base_url": "https://api.openai.com/v1"},
}

_THINK = re.compile(r"<think>.*?(</think>|$)", re.S)


def ask_openai(base_url, key, model, user, max_tokens=16000):
    """One chat completion from an OpenAI-compatible endpoint (stdlib only)."""
    body = json.dumps({"model": model, "temperature": 0, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(60, 2 ** attempt * 5))
                continue
            raise RuntimeError(f"HTTP {e.code} from {base_url}: {detail}") from None
        except (urllib.error.URLError, TimeoutError):
            time.sleep(min(60, 2 ** attempt * 5))
    else:
        raise RuntimeError("API kept failing")
    choice = d["choices"][0]
    text = _THINK.sub("", choice["message"].get("content") or "")
    return text, choice.get("finish_reason"), (d.get("usage") or {}).get("prompt_tokens")


def ask(client, model, effort, user):
    import anthropic

    for attempt in range(5):
        try:
            r = client.messages.create(
                model=model, max_tokens=16000, system=SYSTEM,
                output_config={"effort": effort},
                messages=[{"role": "user", "content": user}])
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError):
            time.sleep(2 ** attempt * 5)
    else:
        raise RuntimeError("API kept failing")
    text = "".join(b.text for b in r.content if b.type == "text")
    return text, r.stop_reason, r.usage.input_tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS),
                    help="default: the first provider whose API key is set (anthropic, nvidia, openai)")
    ap.add_argument("--model", default=os.environ.get("BPP_QA_MODEL"),
                    help="default: claude-opus-5 / deepseek-ai/deepseek-v4.1-flash / gpt-5-mini")
    ap.add_argument("--base-url", help="OpenAI-compatible endpoint (overrides the provider's)")
    ap.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"],
                    help="Anthropic only")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--examples", nargs="*", default=list(EXAMPLES))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.provider:
        a.provider = next((p for p, c in PROVIDERS.items() if os.environ.get(c["env"])), "anthropic")
    prov = PROVIDERS[a.provider]
    a.model = a.model or prov["model"]
    base_url = a.base_url or prov["base_url"]
    key = os.environ.get(prov["env"])

    plan = []
    for name in a.examples:
        data, _ = load(name)
        qs = QUESTIONS[name](data)
        assert len(qs) == 10
        for fmt_name, text in formats_for(name).items():
            plan.append((name, fmt_name, prompt(fmt_name, text, qs), qs))

    if a.dry_run or not key:
        if not a.dry_run:
            print(f"{prov['env']} is not set: skipping the API run. Showing the plan instead.\n")
        for name in a.examples:
            data, _ = load(name)
            print(f"## {name}")
            for i, (q, e, k) in enumerate(QUESTIONS[name](data), 1):
                print(f"  {i:2}. [{k}] {q}\n      -> {e}")
        chars = sum(len(p) for _, _, p, _ in plan)
        print(f"\n{len(plan)} requests x {a.repeats} repeat(s), ~{chars // 4:,} input tokens total "
              f"(provider {a.provider}, model {a.model}).")
        return 0

    if a.provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic()

        def run(user):
            return ask(client, a.model, a.effort, user)
        label = f"{a.model}, effort {a.effort}"
        stem = "qa"
    else:
        def run(user):
            return ask_openai(base_url, key, a.model, user)
        label = f"{a.model} via {a.provider}, temperature 0"
        stem = "qa-" + re.sub(r"[^A-Za-z0-9.]+", "-", a.model).strip("-").lower()

    results = []
    for rep in range(a.repeats):
        for name, fmt_name, user, qs in plan:
            text, stop, in_tok = run(user)
            answers = parse_answers(text, len(qs))
            ok = [grade(ans, e, k) for ans, (_, e, k) in zip(answers, qs)]
            results.append({"example": name, "format": fmt_name, "repeat": rep, "stop_reason": stop,
                            "input_tokens": in_tok, "correct": sum(ok), "total": len(qs),
                            "answers": answers, "expected": [e for _, e, _ in qs]})
            print(f"{name:13s} {fmt_name:22s} {sum(ok):2d}/10  in={in_tok}  {stop}", flush=True)

    RES.mkdir(parents=True, exist_ok=True)
    (RES / f"{stem}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    fmts = list(dict.fromkeys(r["format"] for r in results))
    md = [f"# Comprehension benchmark ({label}, {a.repeats} repeat(s))", "",
          "| format | " + " | ".join(a.examples) + " | total | accuracy | mean input tokens |",
          "|---|" + "---:|" * (len(a.examples) + 3)]
    for f in fmts:
        rs = [r for r in results if r["format"] == f]
        cells = []
        for ex in a.examples:
            e = [r for r in rs if r["example"] == ex]
            cells.append(f"{sum(r['correct'] for r in e)}/{sum(r['total'] for r in e)}" if e else "–")
        c, t = sum(r["correct"] for r in rs), sum(r["total"] for r in rs)
        toks = [r["input_tokens"] for r in rs if r["input_tokens"] is not None]
        mean = f"{sum(toks) / len(toks):.0f}" if toks else "–"
        md.append(f"| {f} | " + " | ".join(cells) + f" | {c}/{t} | {100 * c / t:.1f}% | {mean} |")
    refusals = [r for r in results if r["stop_reason"] in ("refusal", "content_filter")]
    cut = [r for r in results if r["stop_reason"] in ("max_tokens", "length")]
    md += ["", f"Refusals: {len(refusals)}  ·  Cut off by the output limit: {len(cut)}"]
    (RES / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
