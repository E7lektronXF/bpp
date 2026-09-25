"""The JavaScript port (js/bpp.js) must produce byte-identical output."""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

import datasets as ds
from bpp import decode, encode
from bpp.formats import dump_csv
from bpp.markdown import md_to_tree
from test_roundtrip import CASES

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")

TRICKY = ["", " ", "a b", "1", "-1", "1.1", "1e5", "007", "null", "true", "NaN", "-", "- x",
          "*0", "&1", "#c", "a,b", "a]b", "[x", "{}", "k=v", "x y=z", "a:b", "\n", "a\nb",
          "\t", '"', "\\", "ç ğ ı İ ö ş ü", "Iğdır", "🚀 launch", "漢字", "Connection timed out",
          "a long repeated sentence number one", "another long value, with a comma"]
KEYS = ["id", "title", "status", "steps", "name", "note", "a b", "şehir", "", "42", "x?", "k:v"]


def rand_value(r: random.Random, depth=0):
    roll = r.random()
    if depth > 3 or roll < 0.45:
        k = r.randrange(7)
        if k == 0:
            return None
        if k == 1:
            return r.random() < 0.5
        if k == 2:
            return r.choice([0, 1, -7, 42, 2**40, -(2**63), 10**20])
        if k == 3:
            return r.choice([0.0, -0.0, 1.0, 0.5, 1e-7, 1e16, 1.5e-5, 123.456, 2.5e300, 0.1 + 0.2])
        if k == 4:
            return "".join(r.choice("abcçğıİşü XYZ,-=:[]\"\\#*&019\n") for _ in range(r.randrange(8)))
        return r.choice(TRICKY)
    if roll < 0.6:
        return [rand_value(r, depth + 1) for _ in range(r.randrange(5))]
    if roll < 0.75:
        return {r.choice(KEYS): rand_value(r, depth + 1) for _ in range(r.randrange(5))}
    # arrays of objects: tables, sparse rows and trees
    keys = r.sample(["id", "title", "status", "note", "owner", "n"], r.randrange(1, 5))
    rows = []
    for _ in range(r.randrange(1, 6)):
        row = {k: rand_value(r, 4) for k in keys if r.random() < 0.8} or {keys[0]: 1}
        if depth < 2 and r.random() < 0.3:
            row["steps"] = [{k: rand_value(r, 4) for k in keys} for _ in range(r.randrange(3))]
        if r.random() < 0.4:  # nested object -> dotted columns (bpp3)
            row["meta"] = {k: rand_value(r, 4) for k in r.sample(["x", "y", "a.b"], r.randrange(1, 3))}
        if depth < 2 and r.random() < 0.3:  # child table with its own columns (bpp3)
            row["items"] = [{"sku": rand_value(r, 4), "qty": r.randrange(9)} for _ in range(r.randrange(3))]
        rows.append(row)
    return rows


def _back(text):
    return json.dumps(decode(text), ensure_ascii=False, separators=(",", ":"))


def corpus():
    cases = []

    def add_json(x, **opts):
        cases.append({"json": json.dumps(x, ensure_ascii=False), "opts": {
            "primer": opts.get("primer", False), "refs": opts.get("refs", True),
            "keepOrder": opts.get("keep_order", False)},
            "bpp": encode(x, **opts), "back": _back(encode(x, **opts))})

    for name in ds.ALL:
        add_json(ds.ALL[name]())
        add_json(ds.ALL[name](), keep_order=True)
    for x in CASES.values():
        add_json(x)
        add_json(x, refs=False, primer=True)
    r = random.Random(20260924)
    for _ in range(1500):
        add_json(rand_value(r), keep_order=r.random() < 0.3)
    for md in (ROOT / "examples").glob("*.md"):
        text = md.read_text(encoding="utf-8")
        tree = md_to_tree(text)
        cases.append({"md": text, "opts": {}, "bpp": encode(tree),
                      "back": _back(encode(tree))})
    csv_text = dump_csv(ds.employees())
    from bpp.formats import load_csv
    rows = load_csv(csv_text)
    cases.append({"csv": csv_text, "opts": {"keepOrder": True}, "bpp": encode(rows, keep_order=True),
                  "back": _back(encode(rows, keep_order=True))})
    return cases


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_js_port_matches_python(tmp_path):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus(), ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([NODE, str(ROOT / "js/test/parity.mjs"), str(path)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stdout + p.stderr[-4000:]
