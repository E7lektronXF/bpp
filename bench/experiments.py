"""Design experiments for the .bpp format.

Each experiment renders the same data several ways and counts tokens with every
available counter.  The output (bench/results/experiments.md) is the evidence
behind the decisions in SPEC.md.

    python bench/experiments.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

import datasets as ds  # noqa: E402
from bpp.tokens import available_counters  # noqa: E402

COUNTERS = available_counters()


def toon(data, delim="comma") -> str:
    p = subprocess.run(["node", str(ROOT / "bench/toon/toon.mjs"), "encode", delim],
                       input=json.dumps(data, ensure_ascii=False), capture_output=True,
                       text=True, check=True)
    return p.stdout


# --------------------------------------------------------------------------
# Parametric prototype renderer (not the real encoder - just enough to compare
# layout choices on identical data).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Opt:
    indent: str = " "
    kv: str = ":"          # separator between key and scalar value
    delim: str = ","
    count: bool = True     # key[N]
    row_indent: bool = False
    quote_all: bool = False
    dotted: bool = False   # flatten nested objects into a.b.c keys
    header_open: str = "{"
    header_close: str = "}"
    null: str = "null"
    true: str = "true"
    false: str = "false"
    inline_list: str = "count"  # count -> k[2]:a,b | bracket -> k:[a,b]


NUM_RE = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?$")


def scalar(v, o: Opt) -> str:
    if v is None:
        return o.null
    if v is True:
        return o.true
    if v is False:
        return o.false
    if isinstance(v, (int, float)):
        return json.dumps(v)
    s = str(v)
    needs = (o.quote_all or s == "" or s != s.strip() or NUM_RE.match(s)
             or s in (o.null, o.true, o.false) or any(c in s for c in (o.delim, '"', "\n", "\\"))
             or s.startswith(("-", "[", "{")))
    if needs:
        return json.dumps(s, ensure_ascii=False)
    return s


def is_prim(v):
    return v is None or isinstance(v, (str, int, float, bool))


def tabular(arr):
    if not arr or not all(isinstance(x, dict) for x in arr):
        return None
    keys = list(arr[0])
    if not keys:
        return None
    for x in arr:
        if list(x) != keys or not all(is_prim(v) for v in x.values()):
            return None
    return keys


def cnt(n, o):
    return f"[{n}]" if o.count else ""


def render(value, o: Opt, depth=0) -> list[str]:
    pad = o.indent * depth
    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            lines += render_kv(k, v, o, depth)
    elif isinstance(value, list):
        lines += render_kv("", value, o, depth)
    else:
        lines.append(pad + scalar(value, o))
    return lines


def render_kv(k, v, o: Opt, depth, prefix="") -> list[str]:
    pad = o.indent * depth
    key = prefix + k
    if is_prim(v):
        return [f"{pad}{key}{o.kv}{scalar(v, o)}"]
    if isinstance(v, dict):
        if not v:
            return [f"{pad}{key}{o.kv}{{}}"]
        if o.dotted:
            out = []
            for kk, vv in v.items():
                out += render_kv(kk, vv, o, depth, key + ".")
            return out
        out = [f"{pad}{key}:"]
        for kk, vv in v.items():
            out += render_kv(kk, vv, o, depth + 1)
        return out
    # list
    if all(is_prim(x) for x in v):
        items = o.delim.join(scalar(x, o) for x in v)
        if o.inline_list == "bracket":
            return [f"{pad}{key}{o.kv}[{items}]"]
        return [f"{pad}{key}{cnt(len(v), o)}:{items}"]
    keys = tabular(v)
    if keys:
        hdr = f"{pad}{key}{cnt(len(v), o)}{o.header_open}{o.delim.join(keys)}{o.header_close}:"
        rpad = pad + (o.indent if o.row_indent else "")
        return [hdr] + [rpad + o.delim.join(scalar(x[kk], o) for kk in keys) for x in v]
    out = [f"{pad}{key}{cnt(len(v), o)}:"]
    for x in v:
        sub = render(x, o, depth + 1)
        first = sub[0].lstrip()
        out.append(f"{pad}{o.indent}-{first}")
        out += sub[1:]
    return out


def proto(data, **kw) -> str:
    return "\n".join(render(data, replace(Opt(), **kw)))


# --------------------------------------------------------------------------

def count_all(text: str) -> dict[str, int]:
    return {name: fn(text) for name, fn in COUNTERS.items()}


def table(title: str, variants: dict[str, str], note: str = "") -> str:
    names = list(COUNTERS)
    rows = [(k, count_all(v)) for k, v in variants.items()]
    base = rows[0][1]
    head = f"### {title}\n\n" + (note + "\n\n" if note else "")
    head += "| variant | " + " | ".join(names) + " | " + " | ".join(f"Δ% {n}" for n in names) + " |\n"
    head += "|---|" + "---:|" * (2 * len(names)) + "\n"
    for k, c in rows:
        head += f"| {k} | " + " | ".join(str(c[n]) for n in names) + " | "
        head += " | ".join((f"{100 * (c[n] - base[n]) / base[n]:+.1f}" if base[n] else "-") for n in names) + " |\n"
    return head


def main():
    emp = ds.employees()
    cfg = ds.config()
    plan = ds.plan()
    mixed = ds.mixed()
    logs = ds.repetitive_logs()
    out = ["# .bpp design experiments\n",
           f"Counters: {', '.join(COUNTERS)}. Δ% is relative to the first row.\n"]

    # E1 tabular layout ---------------------------------------------------
    rec = {"employees": emp}
    out.append(table("E1 Tabular data (60 rows x 10 cols): layout", {
        "JSON pretty": json.dumps(rec, ensure_ascii=False, indent=2),
        "JSON minified": json.dumps(rec, ensure_ascii=False, separators=(",", ":")),
        "YAML": yaml.safe_dump(rec, allow_unicode=True, sort_keys=False),
        "CSV": "id,name,email,department,city,salary,rating,active,manager_id,start_date\n" + "\n".join(
            ",".join("" if v is None else str(v) for v in r.values()) for r in emp),
        "TOON comma": toon(rec),
        "TOON tab": toon(rec, "tab"),
        "proto comma, no row indent": proto(rec),
        "proto comma, row indent": proto(rec, row_indent=True),
        "proto tab": proto(rec, delim="\t"),
        "proto pipe": proto(rec, delim="|"),
        "proto comma, no [N]": proto(rec, count=False),
        "proto comma, null as empty": proto(rec, null=""),
        "proto comma, bools as 1/0": proto(rec, true="1", false="0"),
        "proto comma, bools as T/F": proto(rec, true="T", false="F"),
        "proto comma, header (a,b)": proto(rec, header_open="(", header_close=")"),
        "proto comma, header [a,b]": proto(rec, header_open="[", header_close="]", count=False),
        "proto comma, quote all strings": proto(rec, quote_all=True),
    }))

    # E2 nested objects ---------------------------------------------------
    out.append(table("E2 Nested config: indentation and key/value separator", {
        "JSON pretty": json.dumps(cfg, ensure_ascii=False, indent=2),
        "JSON minified": json.dumps(cfg, ensure_ascii=False, separators=(",", ":")),
        "YAML": yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        "TOON": toon(cfg),
        "proto indent 2sp, ': '": proto(cfg, indent="  ", kv=": "),
        "proto indent 1sp, ':'": proto(cfg),
        "proto indent 1sp, ': '": proto(cfg, kv=": "),
        "proto indent tab, ':'": proto(cfg, indent="\t"),
        "proto indent 1sp, '='": proto(cfg, kv="="),
        "proto indent 1sp, ' '": proto(cfg, kv=" "),
        "proto dotted keys, ':'": proto(cfg, dotted=True),
        "proto dotted keys, '='": proto(cfg, dotted=True, kv="="),
        "proto inline list [a,b]": proto(cfg, inline_list="bracket"),
    }))

    # E3 dictionary / references -----------------------------------------
    rec = {"logs": logs}
    base = proto(rec)
    uniq = sorted({r["message"] for r in logs} | {r["service"] for r in logs})
    ids = {v: f"*{i}" for i, v in enumerate(uniq)}
    defs = "\n".join(f"&{i}={v}" for i, v in enumerate(uniq))
    subst = [{k: (ids.get(v, v) if isinstance(v, str) else v) for k, v in r.items()} for r in logs]
    msgs_only = sorted({r["message"] for r in logs})
    ids2 = {v: f"*{i}" for i, v in enumerate(msgs_only)}
    defs2 = "\n".join(f"&{i}={v}" for i, v in enumerate(msgs_only))
    subst2 = [{k: (ids2.get(v, v) if k == "message" else v) for k, v in r.items()} for r in logs]
    out.append(table("E3 Repeated long strings (80 log rows): dictionary", {
        "proto inline values": base,
        "TOON": toon(rec),
        "proto + dict (messages+services)": defs + "\n" + proto({"logs": subst}),
        "proto + dict (messages only)": defs2 + "\n" + proto({"logs": subst2}),
    }))
    # dictionary on data without long repeats
    uniq_e = sorted({r["department"] for r in emp} | {r["city"] for r in emp})
    ide = {v: f"*{i}" for i, v in enumerate(uniq_e)}
    dfe = "\n".join(f"&{i}={v}" for i, v in enumerate(uniq_e))
    se = [{k: (ide.get(v, v) if isinstance(v, str) else v) for k, v in r.items()} for r in emp]
    out.append(table("E3b Short repeated strings (department/city): dictionary", {
        "proto inline values": proto({"employees": emp}),
        "proto + dict": dfe + "\n" + proto({"employees": se}),
    }, "Short values are usually 1-2 tokens, so a `*n` reference cannot beat them."))

    # E4 plans -------------------------------------------------------------
    flat = []

    def walk(steps, parent):
        for s in steps:
            flat.append({"id": s["id"], "parent": parent, "title": s["title"],
                         "status": s["status"], "priority": s["priority"],
                         "deps": " ".join(s["deps"]), "owner": s.get("owner"),
                         "note": s.get("note")})
            walk(s.get("steps", []), s["id"])
    walk(plan["steps"], None)
    no_parent = [{k: v for k, v in r.items() if k != "parent"} for r in flat]

    def outline(steps, d=0):
        lines = []
        for s in steps:
            extra = ""
            if s["deps"]:
                extra += " <" + " ".join(s["deps"])
            if s.get("owner"):
                extra += " @" + s["owner"]
            if s.get("note"):
                extra += " #" + s["note"]
            lines.append(" " * d + f"{s['id']} {s['status']} {s['priority']} {s['title']}{extra}")
            lines += outline(s.get("steps", []), d + 1)
        return lines

    def md(steps, d=0):
        lines = []
        for s in steps:
            box = "x" if s["status"] == "done" else " "
            meta = f" ({s['priority']}, {s['status']}"
            if s["deps"]:
                meta += ", deps: " + ", ".join(s["deps"])
            if s.get("owner"):
                meta += ", owner: " + s["owner"]
            meta += ")"
            lines.append("  " * d + f"- [{box}] {s['id']} {s['title']}{meta}")
            if s.get("note"):
                lines.append("  " * (d + 1) + f"- Note: {s['note']}")
            lines += md(s.get("steps", []), d + 1)
        return lines

    head = f"title:{plan['title']}\ngoal:{plan['goal']}\n"
    out.append(table("E4 Plan (6 steps, 21 sub-steps)", {
        "JSON pretty": json.dumps(plan, ensure_ascii=False, indent=2),
        "JSON minified": json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
        "YAML": yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        "Markdown checklist": f"# {plan['title']}\n\n{plan['goal']}\n\n" + "\n".join(md(plan["steps"])),
        "TOON (nested)": toon(plan),
        "proto nested tree": proto(plan),
        "flat table + parent col": head + proto({"steps": flat}),
        "flat table, hierarchical id": head + proto({"steps": no_parent}),
        "positional outline": head + "\n".join(outline(plan["steps"])),
    }))

    # E5 mixed ---------------------------------------------------------------
    out.append(table("E5 Mixed document (API response, 20 orders)", {
        "JSON pretty": json.dumps(mixed, ensure_ascii=False, indent=2),
        "JSON minified": json.dumps(mixed, ensure_ascii=False, separators=(",", ":")),
        "YAML": yaml.safe_dump(mixed, allow_unicode=True, sort_keys=False),
        "TOON": toon(mixed),
        "proto": proto(mixed),
    }))

    # E6 primer --------------------------------------------------------------
    primers = {
        "none": "",
        "1 line": ("# bpp1: JSON as indented 'key value' lines; k[N]{a,b} = N CSV rows; "
                   "\"...\" = JSON string; *n = &n."),
        "3 lines": ("# bpp1 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent).\n"
                    "# k[N]{a,b}: N rows of comma values for a,b. k[N]{a b? c}>kids: space rows, last col = rest of line,\n"
                    "# optional col as a=v, indented rows are kids. '- ' = list item. \"...\" = JSON string. *n = &n value."),
    }
    out.append(table("E6 Primer cost (absolute tokens)", primers | {"(ref) 'bpp1' header": "bpp1"}))

    # E7 quoting of Turkish text ---------------------------------------------
    tr = ["Çiğdem Öztürk", "İstanbul", "Şule Yıldız", "Kapıya bırakın, zili çalmayın."]
    out.append(table("E7 Unicode handling (Turkish text)", {
        "raw UTF-8": "\n".join(tr),
        "JSON \\u escapes": "\n".join(json.dumps(x) for x in tr),
        "JSON quoted, raw": "\n".join(json.dumps(x, ensure_ascii=False) for x in tr),
    }))

    # E8 generic tree-table for recursive arrays (plans) --------------------
    cols = ["id", "title", "status", "priority", "deps", "owner", "note"]

    def cell(v, delim, lst):
        if v is None:
            return ""
        if isinstance(v, list):
            return lst(v)
        s = str(v)
        if s == "" or delim in s or s != s.strip() or s[0] in '"[':
            return json.dumps(s, ensure_ascii=False)
        return s

    def tree(steps, delim, lst, d=0, pad=" "):
        lines = []
        for s in steps:
            lines.append(pad * d + delim.join(cell(s.get(c), delim, lst) for c in cols))
            lines += tree(s.get("steps", []), delim, lst, d + 1, pad)
        return lines

    hdr = lambda delim: f"steps[{len(plan['steps'])}]{{{delim.join(cols)}}}>steps\n"  # noqa: E731
    out.append(table("E8 Plan as tree-table (children indented under parent row)", {
        "positional outline (E4 best)": head + "\n".join(outline(plan["steps"])),
        "tree, comma, deps [a b]": head + hdr(",") + "\n".join(
            tree(plan["steps"], ",", lambda l: "[" + " ".join(l) + "]")),
        "tree, comma, deps [a;b]": head + hdr(",") + "\n".join(
            tree(plan["steps"], ",", lambda l: "[" + ";".join(l) + "]")),
        "tree, comma, deps a b": head + hdr(",") + "\n".join(
            tree(plan["steps"], ",", lambda l: " ".join(l))),
        "tree, tab, deps [a,b]": head + hdr("\t") + "\n".join(
            tree(plan["steps"], "\t", lambda l: "[" + ",".join(l) + "]")),
        "tree, ' | ', deps [a,b]": head + hdr(" | ") + "\n".join(
            tree(plan["steps"], " | ", lambda l: "[" + ",".join(l) + "]")),
        "tree, '|', deps [a,b]": head + hdr("|") + "\n".join(
            tree(plan["steps"], "|", lambda l: "[" + ",".join(l) + "]")),
    }, "Missing fields are empty cells. The `>steps` suffix names the child key."))

    # E8b positional rows: fixed columns, optional k=v tail, free-text last ---
    def q(s):
        return json.dumps(s, ensure_ascii=False) if (" " in s or s == "") else s

    def pos(steps, style, d=0):
        lines = []
        for s in steps:
            opt = []
            if s["deps"]:
                opt.append(("deps", ",".join(s["deps"])))
            if s.get("owner"):
                opt.append(("owner", s["owner"]))
            if s.get("note"):
                opt.append(("note", s["note"]))
            if style == "kv-tail":
                tail = "".join(f" {k}={q(v) if k != 'deps' else v}" for k, v in opt)
                line = f"{s['id']} {s['status']} {s['priority']} {s['title']}{tail}"
            elif style == "kv-mid":
                mid = "".join(f" {k}={q(v) if k != 'deps' else v}" for k, v in opt)
                line = f"{s['id']} {s['status']} {s['priority']}{mid} {s['title']}"
            elif style == "title-quoted":
                mid = "".join(f" {k}={q(v) if k != 'deps' else v}" for k, v in opt)
                line = f"{s['id']} {s['status']} {s['priority']} {q(s['title'])}{mid}"
            elif style == "comma-fixed":
                mid = "".join(f",{k}={json.dumps(v, ensure_ascii=False) if ',' in v or k == 'note' else v}"
                              for k, v in opt if k != "deps")
                line = (f"{s['id']},{s['status']},{s['priority']},[{' '.join(s['deps'])}],"
                        f"{json.dumps(s['title'], ensure_ascii=False) if ',' in s['title'] else s['title']}{mid}")
            lines.append(" " * d + line)
            lines += pos(s.get("steps", []), style, d + 1)
        return lines

    out.append(table("E8b Plan rows: positional variants", {
        "positional outline (sigils < @ #)": head + "\n".join(outline(plan["steps"])),
        "id status pri title k=v...": head + "\n".join(pos(plan["steps"], "kv-tail")),
        "id status pri k=v... title": head + "\n".join(pos(plan["steps"], "kv-mid")),
        "id status pri \"title\" k=v...": head + "\n".join(pos(plan["steps"], "title-quoted")),
        "comma columns + k=v optional": head + "\n".join(pos(plan["steps"], "comma-fixed")),
    }))

    # E9 key/value separator and inline lists on whole documents -------------
    out.append(table("E9 Separator `key:value` vs `key value` on other documents", {
        "config ':'": proto(cfg),
        "config ' '": proto(cfg, kv=" "),
        "config ' ' + lists [a,b]": proto(cfg, kv=" ", inline_list="bracket"),
        "mixed ':'": proto(mixed),
        "mixed ' '": proto(mixed, kv=" "),
        "plan-nested ':'": proto(plan),
        "plan-nested ' '": proto(plan, kv=" "),
    }, "Δ% only meaningful between rows of the same document."))

    out += bpp4_experiments(plan)

    res = ROOT / "bench/results/experiments.md"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


# --------------------------------------------------------------------------
# bpp4 (Markdown) experiments.  These use the real encoder with one rule
# switched off at a time, on a frozen corpus: bench/corpus/ holds this repo's
# README, SPEC, BENCHMARK and RELEASING as of v0.3.0 plus the example plan, so
# the numbers do not move when the documents themselves are edited.
# --------------------------------------------------------------------------

CORPUS = ["README.md", "SPEC.md", "BENCHMARK.md", "RELEASING.md", "project_plan.md"]


@contextmanager
def patched(*changes):
    """Temporarily set (object, attribute, value) triples."""
    old = [(o, a, getattr(o, a)) for o, a, _ in changes]
    for o, a, v in changes:
        setattr(o, a, v)
    try:
        yield
    finally:
        for o, a, v in old:
            setattr(o, a, v)


def table_docs(title: str, variants: dict, note: str = "") -> str:
    """Rows = variants (name -> fn(source) -> text), columns = corpus files, per counter."""
    srcs = {f: (ROOT / "bench/corpus" / f).read_text(encoding="utf-8") for f in CORPUS}
    out = f"### {title}\n\n" + (note + "\n\n" if note else "")
    for cname, fn in COUNTERS.items():
        out += f"{cname}:\n\n| variant | " + " | ".join(CORPUS) + " | total |\n"
        out += "|---|" + "---:|" * (len(CORPUS) + 1) + "\n"
        for vname, make in variants.items():
            ns = [fn(make(srcs[f])) for f in CORPUS]
            out += f"| {vname} | " + " | ".join(map(str, ns)) + f" | {sum(ns)} |\n"
        out += "\n"
    return out


def bpp4_experiments(plan) -> list[str]:
    import bpp.encoder as E
    import bpp.estimate as ES
    import bpp.lexer as L
    import bpp.markdown as M
    from bpp import encode, encode_md

    def tree(src, **kw):
        return encode(M.md_to_tree(src), **kw)

    old_piece = re.compile(ES._PIECE.pattern.replace('(?![?\\"]=|=\\|)', "").replace(r"|\n+|", r"|\n|"))
    assert old_piece.pattern != ES._PIECE.pattern
    orig_header = E._Spec.header
    orig_quote = L.needs_quote

    def with_(*changes, md=True, **kw):
        def run(src):
            with patched(*changes):
                return tree(src, **kw) if md else encode(src, **kw)
        return run

    no_blocks = (E, "block_ok", lambda s: False)
    all_blocks = (E, "block_gain", lambda s: 0)
    named_child = (E._Spec, "header", lambda self, key: orig_header(self, None))
    star_quoted = (L, "needs_quote", lambda s, ctx="value", strmode=False:
                   s[:1] == "*" or orig_quote(s, ctx, strmode))
    tree_only = (E, "_plans", lambda arr, k, f=E._plans: f(arr, k)[:1])
    old_est = (ES, "_PIECE", old_piece)
    out = []
    out.append(table_docs("E10 Multi-line strings: JSON string vs `|N` block (bpp4)", {
        "all quoted (bpp3)": with_(no_blocks),
        "all blocks": with_(all_blocks),
        "block when estimated gain >= 0 (chosen)": with_(),
    }, "Whole documents, encoded as trees with every other bpp4 rule on."))
    out.append(table_docs("E11 Markdown soft line breaks", {
        "keep every line break (bpp3)": lambda src: encode(M.md_to_tree(src, join=False)),
        "join item titles only": with_((M, "_join_soft", lambda lines: lines)),
        "join item titles and note paragraphs (chosen)": with_(),
    }))
    out.append(table_docs("E12 Child key of a tree: `>steps` vs bare `>`", {
        "`>steps` (bpp3)": with_(named_child),
        "bare `>` (chosen)": with_(),
    }))
    out.append(table("E12b Bare `>` on the JSON plan (examples/plan.json)", {
        "`>steps` (bpp3)": with_(named_child, md=False)(plan),
        "bare `>` (chosen)": encode(plan),
    }))
    out.append(table_docs("E13 Strings starting with `*`: always quoted vs only `*n`", {
        "quote every leading `*` (bpp3)": with_(star_quoted),
        "quote only `*<digits>` (chosen)": with_(),
    }))
    out.append(table_docs("E14 Layout of Markdown trees and the estimator", {
        "tree only, bpp3 estimator": with_(tree_only, old_est),
        "tree or child table, bpp3 estimator": with_(old_est),
        "tree or child table, bpp4 estimator (chosen)": with_(),
    }, "bpp4 estimator: `?=`, `=|` and `\"=` stay two tokens, and a run of newlines is one. "
       "The child table gives the top level (headings) its own columns, so a heading's note can "
       "be positional (`|7 Title`) instead of keyed (`note=|7 Title`)."))
    out.append(table_docs("E15 Markdown: source vs bpp, primers and the `bpp4 md` fallback", {
        "Markdown source": lambda src: src,
        "`bpp4 md` + source": lambda src: "bpp4 md\n" + src,
        "bpp tree (no primer)": tree,
        "bpp tree + JSON primer": lambda src: tree(src, primer=True),
        "bpp tree + Markdown primer": lambda src: E._assemble(
            *E._body(M.md_to_tree(src), True, False), True, markdown=True),
        "encode_md (chosen)": encode_md,
        "encode_md + primer (chosen)": lambda src: encode_md(src, primer=True),
    }))
    out.append(table("E16 Primer length (absolute tokens)", {
        "bpp3 one-line primer": "# bpp3: JSON as 'key value' lines, 1-space indent nests. k[N]{a b.c}: N "
        "rows, values in column order (b.c = key c of b), last one = rest of line; x? optional "
        "(- = absent), x?= as x=v; >k: indented rows are k. \"...\" = JSON string, *n = &n.",
        "bpp4 primer, project_plan.md": encode_md(
            (ROOT / "bench/corpus/project_plan.md").read_text(encoding="utf-8"), primer=True
        ).split("\n")[1],
        "bpp4 primer, plan.json": encode(plan, primer=True).split("\n")[1],
        "bpp4 primer, examples/quickstart.json": encode(
            json.loads((ROOT / "examples/quickstart.json").read_text(encoding="utf-8")),
            primer=True).split("\n")[1],
        "bpp4 primer, every feature": E._primer([E._Raw("x"), "a[1]{x,y}", 'k[1]{a b.c? d?=}>e{f}>', '"'],
                                                True, markdown=False),
        "bpp4 3-line primer (--primer long)": E.PRIMER_LONG,
    }, "The bpp4 one-line primer lists only the syntax the output uses (SPEC §8)."))
    return out


if __name__ == "__main__":
    main()
