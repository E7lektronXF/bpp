"""decode(encode(x)) == x for the edge cases named in the task and SPEC."""

import math

import pytest

import datasets as ds
from bpp import decode, encode
from conftest import canon, roundtrip

TURKISH = "çğıİöşü ÇĞIİÖŞÜ — Iğdır'da ılık bir gün; İstanbul, Şişli"

CASES = {
    # empty containers
    "empty object": {},
    "empty list": [],
    "empty nested": {"a": {}, "b": [], "c": [[]], "d": [{}], "e": {"f": {}}},
    "list of empty lists": [[], [], []],
    # scalars
    "root string": "hello",
    "root string with spaces": "a b c",
    "root empty string": "",
    "root int": 42,
    "root negative float": -3.25,
    "root null": None,
    "root true": True,
    "int vs float": {"i": 1, "f": 1.0, "z": 0, "fz": 0.0, "nz": -0.0},
    "big and small numbers": {"big": 2**70, "neg": -(2**63), "tiny": 1e-300, "exp": 6.02e23},
    "null values": {"a": None, "b": [None, None], "c": [{"x": None, "y": 1}, {"x": 2, "y": None}]},
    # strings that look like other things
    "number-like strings": {"a": "42", "b": "1.1", "c": "-0", "d": "1e5", "e": "007", "f": "0.10"},
    "keyword strings": {"a": "null", "b": "true", "c": "false", "d": "NaN", "e": "Infinity"},
    "syntax-like strings": {"a": "*0", "b": "&1", "c": "#x", "d": "- x", "e": "[a]", "f": "{}",
                            "g": "k=v", "h": "a,b", "i": '"q"', "j": "a]b", "k": "-", "l": "x y=z"},
    # delimiters inside strings
    "delimiters in table cells": [{"a": "x,y", "b": "p q"}, {"a": "1,2,3", "b": " lead"},
                                  {"a": "trail ", "b": "t\tab"}],
    "delimiters in inline list": {"l": ["a,b", "c]d", "e f", "", " "]},
    "quotes and backslashes": {"a": 'say "hi"', "b": "C:\\path\\to", "c": "\\n is not newline",
                               "d": "\\", "e": '"', "f": "a\\\"b"},
    # multi-line text
    "multiline": {"text": "line 1\nline 2\n\nline 4", "crlf": "a\r\nb", "trail": "x\n",
                  "only": "\n", "tabs": "\tindented"},
    "multiline in table": [{"id": 1, "t": "a\nb"}, {"id": 2, "t": "c"}],
    # unicode
    "turkish": {"şehir": "İstanbul", "ad": "Çiğdem Öztürk", "not": TURKISH,
                "liste": ["ç", "ğ", "ı", "İ", "ö", "ş", "ü"]},
    "turkish table": [{"ad": "Ilgın Işık", "şehir": "Iğdır"}, {"ad": "Gülşen", "şehir": "Muş"}],
    "unicode misc": {"emoji": "🚀 launch", "cjk": "漢字", "rtl": "مرحبا", "zwj": "👩‍💻",
                     "nbsp": "a\u00a0b", "ls": "a\u2028b", "nel": "a\x85b", "bom": "\ufeffx"},
    "control chars": {"c": "\x00\x01\x1f\x7f", "k\x01": 1},
    # keys
    "special keys": {"": 1, " ": 2, "a b": 3, "a:b": 4, "a=b": 5, "a,b": 6, "-a": 7, "#a": 8,
                     "*a": 9, "&a": 10, "a?": 11, "a>b": 12, "[a]": 13, "{a}": 14, '"a"': 15,
                     "42": 16, "null": 17, "ş": 18, "a.b": 19},
    "special column names": [{"a b": 1, "c:str": 2, "d?": 3, "": 4}, {"a b": 5, "c:str": 6, "d?": 7, "": 8}],
    # nesting
    "list of lists": [[1, 2], [3, [4, [5, []]]], ["a", {"b": [1]}]],
    "heterogeneous list": [1, "two", None, True, 2.5, [1], {"a": 1}, [], {}],
    "list items that look like entries": ["a b", "key value", "k[2]", "x{}", "- y", "a"],
    "objects in lists with nested first key": [{"a": {"b": {"c": 1}}, "d": 2}, {"a": [{"x": 1}]}],
    "non-uniform objects": [{"a": 1}, {"b": 2}, {"a": 3, "b": 4}, {}],
    "table with lists": [{"id": 1, "tags": ["x", "y"]}, {"id": 2, "tags": []}],
    "tree": [{"id": "1", "t": "root", "steps": [{"id": "1.1", "t": "kid",
              "steps": [{"id": "1.1.1", "t": "grandkid"}]}]}, {"id": "2", "t": "leaf", "steps": []}],
}


@pytest.mark.parametrize("name", list(CASES))
def test_edge_cases(name):
    roundtrip(CASES[name])


@pytest.mark.parametrize("name", list(CASES))
def test_edge_cases_keep_order(name):
    x = CASES[name]
    assert canon(decode(encode(x, keep_order=True))) == canon(x)


@pytest.mark.parametrize("name", list(CASES))
def test_edge_cases_without_refs_and_with_primer(name):
    roundtrip(CASES[name], refs=False)
    roundtrip(CASES[name], primer=True)
    roundtrip(CASES[name], primer="long")


def test_deep_nesting_objects():
    x = v = {}
    for i in range(80):
        v["k"] = {"i": i}
        v = v["k"]
    roundtrip(x)


def test_deep_nesting_lists():
    x = v = []
    for i in range(80):
        nxt = [i]
        v.append(nxt)
        v.append({"d": i})
        v = nxt
    roundtrip(x)


def test_deep_tree():
    node = {"id": "leaf", "title": "bottom"}
    for i in range(40):
        node = {"id": str(i), "title": f"level {i}", "steps": [node]}
    roundtrip({"steps": [node]})


def test_special_floats():
    back = decode(encode({"a": math.inf, "b": -math.inf, "c": math.nan}))
    assert back["a"] == math.inf and back["b"] == -math.inf and math.isnan(back["c"])


@pytest.mark.parametrize("name", list(ds.ALL))
def test_datasets(name):
    x = ds.ALL[name]()
    roundtrip(x)
    assert canon(decode(encode(x, keep_order=True))) == canon(x)


def test_refs_roundtrip_and_used():
    long = "a fairly long repeated value, with a comma"
    x = {"rows": [{"id": i, "msg": long, "other": "*0"} for i in range(10)], "tail": [long, long]}
    text = roundtrip(x)
    assert text.count(long) == 1 and "&0 " in text


def test_large_table():
    x = [{"id": i, "name": f"user {i}", "score": i * 1.5, "ok": i % 2 == 0} for i in range(2000)]
    roundtrip(x)
