"""JSON / YAML / CSV readers and writers, through bpp and back."""

import json

import pytest
import yaml

import datasets as ds
from bpp import decode, encode
from bpp.formats import detect, dump_csv, dump_yaml, dumps, load_csv, load_yaml, loads


def via_bpp(data, **kw):
    return decode(encode(data, **kw))


# --------------------------------------------------------------------- JSON

@pytest.mark.parametrize("name", list(ds.ALL))
def test_json_text_roundtrip(name):
    text = json.dumps(ds.ALL[name](), ensure_ascii=False, indent=2) + "\n"
    back = dumps(via_bpp(loads(text, "json"), keep_order=True), "json")
    assert back == text


def test_json_minified():
    assert dumps({"a": [1, "ş"]}, "json", indent=None) == '{"a":[1,"ş"]}'


# --------------------------------------------------------------------- YAML

YAML_DOC = """\
service:
  name: order-api
  released: 2026-09-24        # a date: must stay the string it was
  timeout: 1.5
  retries: 3
  debug: no                   # YAML 1.1 boolean
  tags: [a, b]
  empty:
  inf: .inf
  motto: |
    İki satırlık
    Türkçe metin
servers:
  - host: a.internal
    port: 80
  - host: b.internal
    port: 81
1: numeric key
true: bool key
"""


def test_yaml_load_keeps_dates_as_strings():
    d = load_yaml(YAML_DOC)
    assert d["service"]["released"] == "2026-09-24"
    assert d["service"]["debug"] is False and d["service"]["empty"] is None
    assert d["1"] == "numeric key" and d["true"] == "bool key"


def test_yaml_roundtrip_through_bpp():
    d = load_yaml(YAML_DOC)
    back = via_bpp(d)
    assert back == d
    assert load_yaml(dump_yaml(back)) == d


def test_yaml_dump_quotes_date_like_strings():
    assert load_yaml(dump_yaml({"d": "2026-09-24", "n": "1"})) == {"d": "2026-09-24", "n": "1"}


# ---------------------------------------------------------------------- CSV

CSV_TEXT = "\n".join([
    "id,name,zip,price,ratio,active,note,empty",
    '1,"Yılmaz, Ayşe",01234,10.50,0.5,true,"multi',
    'line",',
    "2,Can,34000,7,1.25,false,null,",
    '-0,"quote ""x""",00,1e5,-3.0,TRUE,,',
    "",
])


def test_csv_types_only_when_lossless():
    rows = load_csv(CSV_TEXT)
    r1, r2, r3 = rows
    assert r1 == {"id": 1, "name": "Yılmaz, Ayşe", "zip": "01234", "price": "10.50",
                  "ratio": 0.5, "active": True, "note": "multi\nline", "empty": None}
    assert r2["price"] == 7 and r2["note"] == "null"
    assert r3["id"] == "-0" and r3["zip"] == "00" and r3["price"] == "1e5"
    assert r3["ratio"] == -3.0 and r3["active"] == "TRUE" and r3["note"] is None


def test_csv_text_roundtrip():
    rows = load_csv(CSV_TEXT)
    back = dump_csv(via_bpp(rows, keep_order=True))
    assert back == CSV_TEXT


def test_csv_employees_byte_identical(tmp_path):
    emp = ds.employees()
    text = dump_csv(emp)
    assert dump_csv(via_bpp(load_csv(text), keep_order=True)) == text


def test_csv_rejects_nul_on_every_python():
    with pytest.raises(ValueError, match="NUL"):
        load_csv("a\nx\x00y\n")
    with pytest.raises(ValueError, match="NUL"):
        dump_csv([{"a": "x\x00y"}])


def test_csv_rejects_bad_input():
    with pytest.raises(ValueError, match="duplicate"):
        load_csv("a,a\n1,2\n")
    with pytest.raises(ValueError, match="cells"):
        load_csv("a,b\n1\n")
    with pytest.raises(ValueError, match="flat objects"):
        dump_csv({"a": 1})


def test_detect():
    assert detect("x.JSON") == "json" and detect("a/b.yml") == "yaml" and detect("p.md") == "md"
    with pytest.raises(ValueError):
        detect("noext")


def test_yaml_is_real_yaml():
    assert yaml.safe_load(dump_yaml({"ş": [1, "a: b"]})) == {"ş": [1, "a: b"]}
