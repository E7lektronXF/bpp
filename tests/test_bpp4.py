"""bpp4: `|N` block strings, bare `>`, `bpp4 md` passthrough, Markdown line joining, primers."""

import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from bpp import BppError, decode, encode, encode_md, md_source
from bpp.markdown import md_to_tree, tree_to_md

SETTINGS = settings(max_examples=300, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])

LONG = "First paragraph, with `code`.\n\nSecond one:\n- a list\n- inside"


def exact(a, b):
    return json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)


# ------------------------------------------------------------ block strings

def test_key_block():
    t = encode({"note": LONG, "n": 1})
    assert t == "bpp4\nnote |5\n" + LONG + "\nn 1\n"
    assert decode(t) == {"note": LONG, "n": 1}


def test_block_is_raw_and_counted():
    # Lines that look like bpp syntax, comments, headers or indentation are text.
    s = "|2\n  indented\n# not a comment\nbpp3\n\n- item\nkey value\n*0\n"
    t = "bpp4\nx |9\n" + s + "\ny 2\n"  # 9 lines: s ends with an empty one
    assert decode(t) == {"x": s, "y": 2}
    assert exact(decode(encode({"x": s, "y": 2})), {"x": s, "y": 2})


def test_blank_lines_and_trailing_newline():
    for s in ["a\n", "\na", "a\n\n\nb", "\n\n", "x\n" * 5]:
        assert decode(encode({"k": s})) == {"k": s}
        assert decode(encode([s, s + "!"])) == [s, s + "!"]


def test_blocks_in_rows_come_left_to_right():
    rows = [{"id": 1, "a": LONG, "b": LONG + " (b)", "title": "first row"},
            {"id": 2, "a": "short", "b": LONG, "title": "second row"}]
    t = encode({"rows": rows}, refs=False)
    assert t.split("\n")[2].count("|5") == 2  # both blocks of row 1, in column order
    assert decode(t) == {"rows": rows}
    hand = "bpp4\nt[1]{a b c}\n|2 |1 |2\na1\na2\nb1\nc1\nc2\n"
    assert decode(hand) == {"t": [{"a": "a1\na2", "b": "b1", "c": "c1\nc2"}]}


def test_block_cells_in_comma_tables_and_keyed_columns():
    assert decode("bpp4\nt[2]{a,b}\n|2,x\n1\n2\ny,|2\n3\n4\n") == {
        "t": [{"a": "1\n2", "b": "x"}, {"a": "y", "b": "3\n4"}]}
    assert decode("bpp4\nt[2]{id n?= t}\n1 n=|2 one\np\nq\n2 two\n") == {
        "t": [{"id": 1, "n": "p\nq", "t": "one"}, {"id": 2, "t": "two"}]}


def test_blocks_under_nested_steps():
    tree = {"steps": [{"title": "A", "note": LONG, "steps": [
        {"title": "a1", "note": "x\ny"}, {"title": "a2", "steps": [{"title": "deep", "note": LONG}]}]},
        {"title": "B"}]}
    assert decode(encode(tree)) == tree
    assert decode(encode(tree, refs=False)) == tree
    hand = "bpp4\nsteps[2]{note?= title}>\nnote=|2 A\n x\n  y\n a1\n  note=|1 deep\n  z\nB\n"
    assert decode(hand) == {"steps": [
        {"note": " x\n  y", "title": "A", "steps": [{"title": "a1", "steps": [
            {"note": "  z", "title": "deep"}]}]}, {"title": "B"}]}


def test_root_items_and_dictionary_blocks():
    assert decode(encode(LONG)) == LONG
    assert encode(LONG).startswith("bpp4\n|5\n")
    for root in ["|abc", "| x", "|3", "*x", "|"]:  # one-line root strings are always quoted
        assert encode(root) == f'bpp4\n"{root}"\n' and decode(encode(root)) == root
    assert decode("bpp4\nl[2]\n- |2\na\nb\n- x\n") == {"l": ["a\nb", "x"]}
    assert decode("bpp4\n&0 |2\nlong repeated\nvalue\nl [*0,|2]\nm *0\n") == {
        "l": ["long repeated\nvalue", "|2"], "m": "long repeated\nvalue"}  # no blocks in [..]


def test_block_marker_quoting():
    assert encode({"a": "|3", "b": "*12", "c": "**bold** text", "d": "*x"}) == (
        'bpp4\na "|3"\nb "*12"\nc **bold** text\nd *x\n')
    assert encode({"|3": {"x": 1}}) == 'bpp4\n"|3"\n x 1\n'
    for x in [["|3", "|0"], {"|1": "|2"}, [{"a": "|4", "b": "- x"}]]:
        assert exact(decode(encode(x)), x)


def test_blocks_only_for_safe_multiline_strings():
    assert "|" not in encode({"a": "x\r\ny\nz more text"})  # \r is escaped
    assert "|" not in encode({"a": "x\ty\nz more text"})  # so are other controls
    assert "|" not in encode({"a": "a\nb"})  # too short to gain anything


def test_block_errors_and_old_versions():
    with pytest.raises(BppError):
        decode("bpp4\nx |3\na\n")
    with pytest.raises(BppError):
        decode("bpp4\nx |0\n")
    # bpp3 has no blocks: `|2` is an ordinary string there
    assert decode("bpp3\nx |2\ny 1\n") == {"x": "|2", "y": 1}


def test_crlf_block_lines():
    assert decode("bpp4\r\nx |2\r\na\r\nb\r\ny 1\r\n") == {"x": "a\nb", "y": 1}


# ------------------------------------------------------------- bare `>`

def test_bare_child_key():
    x = {"steps": [{"title": "a b", "steps": [{"title": "c"}]}]}
    assert encode(x) == "bpp4\nsteps[1]{title}>\na b\n c\n"
    assert decode("bpp4\nsteps[1]{title}>\na b\n c\n") == x
    orders = {"o": [{"id": 1, "items": [{"sku": "k", "items": [{"sku": "q"}]}]}]}
    assert exact(decode(encode(orders)), orders)
    with pytest.raises(BppError):
        decode("bpp4\n[1]{title}>\na\n")  # a keyless table has no key to repeat
    with pytest.raises(BppError):
        decode("bpp3\nsteps[1]{title}>\na\n")


# ------------------------------------------------------ Markdown source

def test_md_passthrough():
    src = "Tiny *note*\nwrapped.\n"
    out = encode_md(src)
    assert out == "bpp4 md\n" + src
    assert md_source(out) == src
    assert decode(out) == md_to_tree(src)
    assert md_source("bpp4 md") == "" and decode("bpp4 md") == {"steps": []}
    assert md_source("bpp4\na 1\n") is None
    assert md_source("# comment\n\nbpp4 md\r\nx\r\n") == "x\r\n"


def test_md_compact_when_shorter():
    from conftest import ROOT
    src = (ROOT / "examples/project_plan.md").read_text(encoding="utf-8")
    out = encode_md(src)
    assert out.startswith("bpp4\n") and decode(out) == md_to_tree(src)
    assert md_source(out) is None


# ------------------------------------------------------------ line joining

def test_item_title_joins_wrapped_lines():
    t = md_to_tree("- first line\n  continues here\nand lazily here\n- second\n")
    assert t["steps"][0] == {"title": "first line continues here and lazily here"}
    t = md_to_tree("- a\n  - b\n  lazy for b\n")
    assert t["steps"][0]["steps"][0]["title"] == "b lazy for b"


def test_hard_breaks_blocks_and_lists_are_not_joined():
    t = md_to_tree("- a  \n  b\n- c\\\n  d\n- e\n  ```\n  x\n  ```\n- f\n  > q\n- g\n  | t |\n- h\n  ---\n")
    s = t["steps"]
    assert s[0] == {"title": "a", "note": "b"}
    assert s[1] == {"title": "c\\", "note": "d"}
    assert s[2]["note"] == "```\nx\n```" and s[3]["note"] == "> q"
    assert s[4]["note"] == "| t |" and s[5]["note"] == "---"


def test_note_soft_wraps():
    md = ("# T\n\n## H\none\ntwo  \nthree\n\n```\nkeep\nlines\n```\n\n| a |\n|---|\n\n"
          "<pre>\np\nq\n</pre>\nr\ns\n\n$$\nm\nn\n$$\n\n[x]: /u\nnext\n")
    h = md_to_tree(md)["steps"][0]
    assert h["note"] == ("one two  \nthree\n\n```\nkeep\nlines\n```\n\n| a |\n|---|\n\n"
                         "<pre>\np\nq\n</pre>\nr s\n\n$$\nm\nn\n$$\n\n[x]: /u\nnext")


def test_front_matter_is_kept():
    t = md_to_tree("---\ntitle: x\ndate: y\n---\n\n# Doc\n")
    assert t["note"].startswith("---\ntitle: x\ndate: y\n---")


def test_normalized_markdown_is_stable():
    md = "# T\n\n- a  \n  b\n- c\n  d\n\n  e\n  f\n"
    tree = md_to_tree(md)
    assert tree["steps"] == [{"title": "a", "note": "b"}, {"title": "c d", "note": "e f"}]
    assert md_to_tree(tree_to_md(tree)) == tree


# ----------------------------------------------------------------- primers

def test_primers_explain_what_is_used():
    p = encode({"steps": [{"title": "a b", "note": LONG, "steps": [{"title": "c"}]}]},
               primer=True).split("\n")[1]
    assert "|N" in p and "same key" in p and "*n" not in p
    assert "|N" not in encode({"a": 1}, primer=True)
    from conftest import ROOT
    md = encode_md((ROOT / "examples/project_plan.md").read_text(encoding="utf-8"), primer=True)
    head = md.split("\n")[1]
    assert head.startswith("# bpp4 Markdown:") and "status" in head and "JSON as" not in head


# -------------------------------------------------------------- properties

LINES = st.lists(st.sampled_from([
    "", "plain text", "more words here", "  indented", "    code", "|2", "| a | b |", "|---|",
    "- item", "  - sub item", "1. one", "* star", "# not a heading?", "## Heading", "### Sub",
    "```\ncode\n\n```", "~~~ py\nx\n~~~", "> quote", "<div>", "</div>", "<pre>", "</pre>", "<!--", "-->", "$$",
    "---", "===", "***", "[r]: /x", "hard break  ", "back\\", "- [x] done", "- [ ] todo",
    "bpp4", "bpp4 md", "*0", "&0 x", "k=v title", "\tTab", "ç ğ ı İ",
]), max_size=14).map("\n".join)


@SETTINGS
@given(LINES)
def test_markdown_roundtrips(src):
    tree = md_to_tree(src)
    out = encode_md(src)
    assert decode(out) == tree
    assert decode(encode_md(src, primer=True)) == tree
    if out.startswith("bpp4 md\n"):
        assert md_source(out) == src
    md = tree_to_md(tree)
    assert md_to_tree(md) == tree  # md -> tree -> md -> tree is stable


MULTI = st.text(st.characters(codec="utf-8", exclude_categories=("Cs",)), max_size=30) | st.lists(
    st.sampled_from(["", "a", "|3", "# c", "  x", "bpp3", "- y", "k v", "\t", "z\r", "q=1 w"]),
    min_size=2, max_size=6).map("\n".join)


@SETTINGS
@given(st.recursive(MULTI | st.integers(), lambda inner: st.lists(inner, max_size=4)
                    | st.dictionaries(st.sampled_from(["a", "title", "note", "|2", "steps"]), inner,
                                      max_size=4)
                    | st.lists(st.fixed_dictionaries({"title": MULTI}, optional={"note": MULTI}),
                               min_size=1, max_size=4), max_leaves=20))
def test_multiline_strings_roundtrip(x):
    assert decode(encode(x)) == x
    assert decode(encode(x, refs=False)) == x
    assert exact(decode(encode(x, keep_order=True)), x)
