"""Property-based round-trip tests (hypothesis)."""

import json
import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from bpp import decode, encode
from bpp.formats import dump_csv, dump_yaml, load_csv, load_yaml
from bpp.markdown import md_to_tree, tree_to_md

SETTINGS = settings(max_examples=400, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])

# Text that deliberately includes the format's own syntax, whitespace, Turkish letters.
TRICKY = st.sampled_from([
    "", " ", "  x", "x ", "a b", "1", "-1", "1.1", "1e5", "007", "null", "true", "false",
    "NaN", "-", "- x", "*0", "&1", "#c", "a,b", "a]b", "[x", "{}", "k=v", "x y=z", "a:b",
    "\n", "a\nb", "\t", "\r", '"', '\\', "ç ğ ı İ ö ş ü", "Iğdır", " ", "\x85", "🚀",
])
TEXT = st.text(st.characters(codec="utf-8", exclude_categories=("Cs",)), max_size=16) | TRICKY
NUM = st.integers() | st.floats(allow_nan=False, allow_infinity=False)
SCALAR = st.none() | st.booleans() | NUM | TEXT
KEYS = TEXT | st.sampled_from(["id", "title", "steps", "children", "name"])


def json_values(scalar=SCALAR):
    return st.recursive(
        scalar,
        lambda inner: (st.lists(inner, max_size=5)
                       | st.dictionaries(KEYS, inner, max_size=5)
                       # uniform / tree-shaped arrays of objects exercise tables
                       | st.lists(st.fixed_dictionaries({"id": inner, "title": inner},
                                                        optional={"steps": st.lists(
                                                            st.fixed_dictionaries({"id": inner, "title": inner}),
                                                            max_size=3),
                                                            "note": inner}),
                                  min_size=1, max_size=5)
                       # rows with nested objects and child tables (bpp3)
                       | st.lists(st.fixed_dictionaries(
                           {"id": inner, "c": st.dictionaries(st.sampled_from(["n", "m", "a.b"]), inner,
                                                              max_size=2)},
                           optional={"items": st.lists(st.fixed_dictionaries({"s": inner},
                                                                             optional={"t": inner}),
                                                       max_size=3),
                                     "t": inner}),
                           min_size=1, max_size=4)),
        max_leaves=30)


def same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@SETTINGS
@given(json_values(), st.booleans(), st.booleans())
def test_json_roundtrip(x, refs, keep_order):
    text = encode(x, refs=refs, keep_order=keep_order)
    y = decode(text)
    assert same(x, y), text
    if keep_order:
        assert json.dumps(x) == json.dumps(y), text


@SETTINGS
@given(json_values(scalar=st.none() | st.integers(0, 9) | st.sampled_from(
    ["a long repeated sentence number one", "another long value, with a comma",
     "*0 looks like a reference", "short"])))
def test_dictionary_roundtrip(x):
    text = encode(x)
    assert same(x, decode(text)), text


@SETTINGS
@given(st.lists(st.floats(), max_size=6))
def test_floats_including_nan_inf(xs):
    ys = decode(encode(xs))
    assert len(xs) == len(ys)
    for a, b in zip(xs, ys):
        assert (math.isnan(a) and math.isnan(b)) or (a == b and type(a) is type(b)
                                                       and math.copysign(1, a) == math.copysign(1, b))


CELL = (st.text(st.characters(codec="utf-8", exclude_categories=("Cs",), exclude_characters="\r\x00"),
                max_size=10)
        | st.sampled_from(["", "0", "007", "-0", "1.50", "1e5", "true", "TRUE", "null", "3.25",
                           "12345678901234567890", "a,b", 'q"q', "x\ny", " s "]))


@SETTINGS
@given(st.integers(1, 5).flatmap(lambda n: st.tuples(
    st.lists(st.text(st.characters(codec="utf-8", exclude_categories=("Cs",),
                                   exclude_characters="\r\x00"), min_size=1, max_size=8),
             min_size=n, max_size=n, unique=True),
    st.lists(st.lists(CELL, min_size=n, max_size=n), min_size=1, max_size=6))))
def test_csv_cells_roundtrip(t):
    header, rows = t
    text = dump_csv([dict(zip(header, r)) for r in rows])
    data = load_csv(text)
    back = dump_csv(decode(encode(data, keep_order=True)))
    assert load_csv(back) == data
    assert back == text


@SETTINGS
@given(json_values(scalar=st.none() | st.booleans() | st.integers() | TEXT))
def test_yaml_roundtrip(x):
    y = load_yaml(dump_yaml(x))
    assert same(decode(encode(y)), y)


TITLE = st.text(st.characters(codec="utf-8", categories=("L", "N"), include_characters=" ,.-çğıİöşü"),
                min_size=1, max_size=12).map(str.strip).filter(
                    lambda s: s and s[0].isalnum())
NODE = st.recursive(
    st.fixed_dictionaries({"title": TITLE},
                          optional={"status": st.sampled_from(["todo", "done", "doing", "cancelled"])}),
    lambda inner: st.fixed_dictionaries(
        {"title": TITLE, "steps": st.lists(inner, min_size=1, max_size=3)},
        optional={"status": st.sampled_from(["todo", "done"]), "note": TITLE}),
    max_leaves=12)


@SETTINGS
@given(st.fixed_dictionaries({"steps": st.lists(NODE, max_size=4)}, optional={"title": TITLE}))
def test_markdown_tree_roundtrip(tree):
    md = tree_to_md(tree)
    parsed = md_to_tree(md)
    assert decode(encode(parsed)) == parsed
    assert md_to_tree(tree_to_md(parsed)) == parsed
    assert parsed == tree, md
