"""Exact output for the SPEC examples, hand-written input, and error handling."""

import pytest

from bpp import BppError, decode, encode


def body(text):
    lines = text.split("\n")
    assert lines[0] == "bpp3"
    return "\n".join(lines[1:]).rstrip("\n")


def test_header_and_primer():
    assert encode({"a": 1}) == "bpp3\na 1\n"
    t = encode({"a": 1}, primer=True)
    assert t.startswith("bpp3\n# bpp3:") and decode(t) == {"a": 1}
    assert encode({"a": 1}, primer="long").count("\n#") == 3


def test_key_value_and_nesting():
    assert body(encode({"s": {"name": "x y", "n": 3, "on": True, "e": {}, "l": []}})) == (
        "s\n name x y\n n 3\n on true\n e {}\n l []")


def test_minimal_quoting():
    t = body(encode({"a": "42", "b": "null", "c": " x", "d": "", "e": "plain text, ok"}))
    assert t == 'a "42"\nb "null"\nc " x"\nd ""\ne plain text, ok'


def test_unicode_not_escaped():
    assert body(encode({"ş": "Çiğdem\nİ"})) == 'ş "Çiğdem\\nİ"'


def test_inline_list():
    assert body(encode({"l": ["TR", "a,b", 1, None]})) == 'l [TR,"a,b",1,null]'


def test_row_table_and_str_column():
    x = {"steps": [{"id": "1", "title": "Plan it", "deps": []},
                   {"id": "1.1", "title": "Then do it", "deps": ["1"]}]}
    assert body(encode(x)) == ("steps[2]{id:str deps:str title}\n"
                               "1 [] Plan it\n"
                               "1.1 [1] Then do it")


def test_comma_table_when_cheaper():
    x = {"t": [{"a": "x y z w", "b": "p q r s"}, {"a": "k l m n", "b": "u v w x"}]}
    assert body(encode(x)) == "t[2]{a,b}\nx y z w,p q r s\nk l m n,u v w x"


def test_optional_columns_and_children():
    x = [{"id": "1", "t": "a b", "owner": "Ayşe",
          "steps": [{"id": "1.1", "t": "c d"}, {"id": "1.2", "t": "e", "steps": []}]}]
    t = body(encode(x))
    assert t == ("[1]{id:str owner?= t}>steps\n"
                 "1 owner=Ayşe a b\n"
                 " 1.1 c d\n"
                 " 1.2 steps=[] e")
    assert decode("bpp3\n" + t) == x


def test_frequent_optional_column_is_positional():
    x = {"steps": [{"title": "Plan", "steps": [{"title": "a b", "status": "done"},
                                              {"title": "c", "status": "todo"},
                                              {"title": "-", "status": "-"}]}]}
    t = body(encode(x))
    assert t == ('steps[1]{status? title}>steps\n'
                 '- Plan\n'
                 ' done a b\n'
                 ' todo c\n'
                 ' "-" -')
    assert decode("bpp3\n" + t) == x


def test_bpp1_files_still_decode():
    # In bpp1 `x?` meant "written as x=v"; bpp2 spells that `x?=`.
    old = "bpp1\nt[2]{id owner? title}\n1 owner=Ayşe a b\n2 c d\n"
    new = "bpp2\nt[2]{id owner?= title}\n1 owner=Ayşe a b\n2 c d\n"
    want = {"t": [{"id": 1, "owner": "Ayşe", "title": "a b"}, {"id": 2, "title": "c d"}]}
    assert decode(old) == decode(new) == want
    assert decode("bpp2\nt[2]{id owner? title}\n1 Ayşe a b\n2 - c d\n") == want


def test_dictionary():
    msg = "Connection to upstream timed out after 30000ms"
    t = encode({"logs": [{"i": i, "m": msg} for i in range(5)]})
    assert t.startswith(f"bpp3\n&0 {msg}\n") and "*0" in t


def test_generic_list_items():
    x = {"l": [1, "a b", {"k": 1, "j": {"x": 2}}, [{"q": 1}, {"r": 2}]]}
    assert body(encode(x)) == ('l[4]\n- 1\n- "a b"\n- k 1\n j\n  x 2\n'
                               '- [2]\n - q 1\n - r 2')


HAND_WRITTEN = """bpp1
# comments and blank lines are ignored

&0 a long repeated sentence
project
 name Mobil ödeme
 tags [a,b,"c d"]
people[2]{id,name,active}
1,Ayşe,true
2,"Kaya, Can",false
steps[2]{id:str status title}>steps
1 done Analiz
 1.1 done Görüşmeler
2 todo *0
misc[2]
- "free text"
- n 1
"""


def test_hand_written_document():
    assert decode(HAND_WRITTEN) == {
        "project": {"name": "Mobil ödeme", "tags": ["a", "b", "c d"]},
        "people": [{"id": 1, "name": "Ayşe", "active": True},
                   {"id": 2, "name": "Kaya, Can", "active": False}],
        "steps": [{"id": "1", "status": "done", "title": "Analiz",
                   "steps": [{"id": "1.1", "status": "done", "title": "Görüşmeler"}]},
                  {"id": "2", "status": "todo", "title": "a long repeated sentence"}],
        "misc": ["free text", {"n": 1}],
    }


def test_crlf_input():
    assert decode("bpp1\r\na 1\r\nb\r\n c x\r\n") == {"a": 1, "b": {"c": "x"}}


@pytest.mark.parametrize("text,msg", [
    ("", "header"),
    ("a 1\n", "header"),
    ("bpp2\n", "empty"),
    ("bpp2\na\n", "no value"),
    ("bpp2\na 1\n  b 2\n", "indentation"),
    ("bpp2\nt[3]{a,b}\n1,2\n", "3 table rows"),
    ("bpp2\nt[1]{a,b}\n1,2,3\n", "too many"),
    ("bpp2\nt[1]{a,b}\n1\n", "expected ','"),
    ("bpp2\na *0\n", "undefined reference"),
    ("bpp2\na \"unterminated\n", "quoted string"),
    ("bpp2\nl[2]\n- 1\n", "list items"),
    ("bpp2\n- 1\n", "outside a list"),
    ("bpp2\na [1,2\n", "unterminated"),
    ("bpp2\n&1 x\na 1\n", "dictionary"),
    ("bpp2\n&0 1\na 1\n", "must be a string"),
    ("bpp2\n a 1\n", "indentation"),
    ("bpp2\n[1,2]\na 1\n", "unexpected content"),
    ('bpp2\n"unterminated\n', "quoted string"),
    ("bpp2\na [1,2] x\n", "trailing"),
    ('bpp2\na"b 1\n', "expected space"),
    ("bpp2\na[x]\n", "bad array header"),
    ("bpp2\nt[1]{a b}>x y\n1 z\n", "bad array header"),
    ("bpp2\nt[1]{a,b c}\n1\n", "bad column list"),
    ("bpp2\nt[1]{a b?}\n1\n", "last column"),
    ("bpp2\nt[1]{a b}>k\n1 k=[1] x\n", "only be"),
    ("bpp2\nt[1]{a b}\n1 [2] q\n", "trailing"),
    ("bpp2\nt[1]{a b}\n  1 x\n", "indentation"),
    ("bpp2\nt[1]{a b}>k\n1 k=[] x\n 2 y\n", "after child"),
    ("bpp2\nt[2]{a b}\n1 x\n", "expected 2 rows"),
    ("bpp2\nl[1]\nx\n", "list item"),
    ("bpp2\nl[1]\n- [1,2] x\n", "trailing"),
    ("bpp2\nl[1]\n- a 1\n a 2\n", "duplicate"),
    ("bpp2\nl[1]\n- {} x\n", "trailing"),
])
def test_errors(text, msg):
    with pytest.raises(BppError, match=msg):
        decode(text)


def test_error_has_line_number():
    with pytest.raises(BppError) as e:
        decode("bpp2\na 1\nb\n")
    assert e.value.line == 3


# ---------------------------------------------------------------- bpp3 ---

ORDERS = {"orders": [
    {"id": "A-1", "customer": {"name": "Ada Lovelace", "city": "London"}, "status": "paid",
     "items": [{"sku": "K-1", "qty": 2, "name": "Blue pen"}, {"sku": "K-2", "qty": 1, "name": "Red pen"}]},
    {"id": "A-2", "customer": {"name": "Alan Turing", "city": "Wilmslow"}, "status": "sent",
     "items": [{"sku": "K-3", "qty": 5, "name": "Notebook"}]},
]}


def test_nested_objects_and_child_tables():
    t = body(encode(ORDERS))
    assert t == ("orders[2]{id customer.city status customer.name}>items{sku qty name}\n"
                 "A-1 London paid Ada Lovelace\n"
                 " K-1 2 Blue pen\n"
                 " K-2 1 Red pen\n"
                 "A-2 Wilmslow sent Alan Turing\n"
                 " K-3 5 Notebook")
    assert decode("bpp3\n" + t) == ORDERS


def test_nested_keep_order_is_exact():
    import json
    text = encode(ORDERS, keep_order=True)
    assert json.dumps(decode(text)) == json.dumps(ORDERS)


def test_dotted_key_is_quoted_in_headers():
    x = [{"a.b": 1, "c": "x y"}, {"a.b": 2, "c": "z w"}]
    t = body(encode(x))
    assert '"a.b"' in t.split("\n")[0]
    assert decode("bpp3\n" + t) == x


def test_bpp2_headers_keep_dots_literal():
    assert decode("bpp2\nt[1]{a.b c}\n1 x y\n") == {"t": [{"a.b": 1, "c": "x y"}]}
    assert decode("bpp3\nt[1]{a.b c}\n1 x y\n") == {"t": [{"a": {"b": 1}, "c": "x y"}]}


def test_object_or_value_conflict_falls_back():
    x = [{"k": {"a": 1}, "t": "x y"}, {"k": 5, "t": "z w"}]
    t = encode(x)
    assert "k.a" not in t
    assert decode(t) == x


def test_nested_optional_and_empty_children():
    x = [{"id": 1, "c": {"n": "a"}, "items": []},
         {"id": 2, "c": {"m": 3}, "items": [{"s": "q", "t": "long text"}]},
         {"id": 3, "t": "x"}]
    assert decode(encode(x)) == x
    assert decode(encode(x, keep_order=True)) == x


def test_grandchild_tables():
    x = [{"id": i, "parts": [{"p": j, "subs": [{"s": k, "note": f"n {k}"} for k in range(2)]}
                             for j in range(2)]} for i in range(2)]
    t = encode(x)
    assert ">parts{" in t and ">subs{" in t
    assert decode(t) == x
