"""Markdown plans -> tree -> bpp -> tree -> Markdown."""

from bpp import decode, encode
from bpp.markdown import md_to_tree, tree_to_md

PLAN = """\
Giriş metni.

# Sürüm 2.0 planı

Bu plan Q3 hedeflerini kapsar.

## Hazırlık
- [x] Gereksinimleri topla  
  Paydaşlarla 3 toplantı yapıldı.
- [ ] Uzun bir madde başlığı
  iki satıra kaydırılmış
- [ ] Tasarım dokümanı
  - [x] Taslak
  - [/] İnceleme
    ```yaml
    key: 1
      nested: true
    ```
  - [-] Eski yaklaşım
* Serbest madde, virgüllü
+ Artı işaretli madde

## [ ] Geliştirme
1. API
2) İstemci
   1. iOS
   2. Android

Son paragraf.

### Alt başlık
Başlık notu.

İkinci paragraf.
"""


def test_structure():
    t = md_to_tree(PLAN)
    assert t["title"] == "Sürüm 2.0 planı"
    assert t["note"] == "Giriş metni.\n\nBu plan Q3 hedeflerini kapsar."
    prep, dev = t["steps"]
    assert prep["title"] == "Hazırlık" and "status" not in prep
    gather, wrapped, design, free, plus = prep["steps"]
    # a hard break (two trailing spaces) ends the title; a soft wrap continues it
    assert gather == {"title": "Gereksinimleri topla", "status": "done",
                      "note": "Paydaşlarla 3 toplantı yapıldı."}
    assert wrapped == {"title": "Uzun bir madde başlığı iki satıra kaydırılmış", "status": "todo"}
    assert [s["status"] for s in design["steps"]] == ["done", "doing", "cancelled"]
    assert design["steps"][1]["note"] == "```yaml\nkey: 1\n  nested: true\n```"
    assert free["title"] == "Serbest madde, virgüllü" and plus["title"] == "Artı işaretli madde"
    assert dev["status"] == "todo" and dev["note"] == "Son paragraf."
    api, client, sub = dev["steps"]
    assert [s["title"] for s in client["steps"]] == ["iOS", "Android"]
    assert sub == {"title": "Alt başlık", "note": "Başlık notu.\n\nİkinci paragraf."}


def test_structure_roundtrip_through_bpp_and_markdown():
    t = md_to_tree(PLAN)
    t2 = decode(encode(t))
    assert t2 == t
    md = tree_to_md(t2)
    assert md_to_tree(md) == t
    assert tree_to_md(md_to_tree(md)) == md  # normalized form is a fixed point


def test_no_title_when_several_h1():
    t = md_to_tree("# A\n- x\n# B\n- y\n")
    assert "title" not in t and [s["title"] for s in t["steps"]] == ["A", "B"]
    assert md_to_tree(tree_to_md(t)) == t


def test_plain_list_document():
    t = md_to_tree("- a\n  - b\n- [x] c\n")
    assert t == {"steps": [{"title": "a", "steps": [{"title": "b"}]},
                           {"title": "c", "status": "done"}]}
    assert md_to_tree(tree_to_md(t)) == t


def test_empty_document():
    assert md_to_tree("") == {"steps": []}
    assert md_to_tree(tree_to_md({"steps": []})) == {"steps": []}


def test_json_plan_to_markdown():
    plan = {"title": "P", "steps": [{"title": "a", "status": "done",
                                     "steps": [{"title": "b", "status": "blocked"}]}]}
    md = tree_to_md(plan)
    assert md.startswith("# P\n\n## [x] a\n") and "- b" in md
