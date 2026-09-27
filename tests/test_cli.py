"""End-to-end CLI tests."""

import json
import subprocess
import sys

import pytest

import datasets as ds
from bpp.cli import main
from conftest import ROOT
from bpp.formats import dump_csv


def run(*args):
    return main([str(a) for a in args])


def _write(path, text):
    path.write_bytes(text.encode("utf-8"))  # LF endings on every OS


@pytest.fixture
def files(tmp_path):
    _write(tmp_path / "c.json", json.dumps(ds.config(), ensure_ascii=False, indent=2) + "\n")
    _write(tmp_path / "e.csv", dump_csv(ds.employees()))
    _write(tmp_path / "p.md", "# Plan\n\n## Adım 1\n- [x] a\n- [ ] b\n")
    _write(tmp_path / "y.yaml", "a: 1\nb: [x, y]\nd: 2026-01-01\n")
    return tmp_path


def test_json_roundtrip(files):
    assert run("encode", files / "c.json", "-o", files / "c.bpp", "--keep-order") == 0
    assert (files / "c.bpp").read_text(encoding="utf-8").startswith("bpp4\n")
    assert run("decode", files / "c.bpp", "-o", files / "c2.json") == 0
    assert (files / "c2.json").read_text(encoding="utf-8") == (files / "c.json").read_text(encoding="utf-8")


def test_csv_roundtrip_identical(files):
    run("encode", files / "e.csv", "-o", files / "e.bpp")
    run("decode", files / "e.bpp", "-o", files / "e2.csv")
    assert (files / "e2.csv").read_bytes() == (files / "e.csv").read_bytes()


def test_yaml_and_md(files, capsys):
    run("encode", files / "y.yaml", "-o", files / "y.bpp")
    run("decode", files / "y.bpp", "--to", "yaml")
    assert "d: '2026-01-01'" in capsys.readouterr().out
    run("encode", files / "p.md", "-o", files / "p.bpp")
    run("decode", files / "p.bpp", "--to", "md")
    out = capsys.readouterr().out
    assert out.startswith("# Plan\n") and "- [x] a" in out


def test_primer_and_minified(files, capsys):
    run("encode", files / "c.json", "--primer", "short")
    assert capsys.readouterr().out.split("\n")[1].startswith("# bpp4")
    run("encode", files / "c.json", "-o", files / "c.bpp")
    run("decode", files / "c.bpp", "--indent", "-1")
    assert json.loads(capsys.readouterr().out) == ds.config()


def test_stats(files, capsys):
    assert run("stats", files / "e.csv") == 0
    out = capsys.readouterr().out
    for name in ("JSON (indent 2)", "JSON (minified)", "YAML", "CSV", "bpp"):
        assert name in out
    run("stats", files / "p.md", "--markdown")
    assert "| Markdown |" in capsys.readouterr().out


def test_errors(files, capsys):
    assert run("encode", files / "missing.json") == 1
    (files / "bad.bpp").write_text("nope\n")
    assert run("decode", files / "bad.bpp") == 1
    assert "header" in capsys.readouterr().err
    assert run("decode", files / "c.json", "--to", "csv") == 1  # not a .bpp file


def test_stdin_and_console_script(files):
    src = (files / "c.json").read_text(encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "bpp.cli", "encode", "-", "--from", "json"],
                       input=src, capture_output=True, text=True, encoding="utf-8", check=True)
    q = subprocess.run([sys.executable, "-m", "bpp.cli", "decode", "-"],
                       input=p.stdout, capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(q.stdout) == json.loads(src)


def test_one_step_mode(files, capsys):
    assert run(files / "c.json") == 0
    assert (files / "c.bpp").exists()
    assert "c.bpp" in capsys.readouterr().err
    assert run(files / "c.bpp") == 1  # would overwrite c.json
    assert run(files / "c.bpp", "-o", files / "back.json") == 0
    assert json.loads((files / "back.json").read_text(encoding="utf-8")) == ds.config()
    assert run(files / "c.bpp", "--to", "yaml") == 0 and (files / "c.yaml").exists()
    assert run(files / "e.csv") == 0 and run(files / "e.bpp", "-o", "-", "--to", "csv") == 0
    assert capsys.readouterr().out == (files / "e.csv").read_text(encoding="utf-8")
    # a tiny Markdown file is shorter as itself: `bpp4 md` + the source (SPEC §7.2)
    assert run(files / "p.md", "-o", "-", "--primer") == 0
    assert capsys.readouterr().out == "bpp4 md\n" + (files / "p.md").read_text(encoding="utf-8")
    plan = ROOT / "examples/project_plan.md"
    assert run(plan, "-o", "-", "--primer") == 0
    assert capsys.readouterr().out.startswith("bpp4\n# bpp4 Markdown:")


def test_markdown_passthrough_decodes_verbatim(files, capsys):
    src = "Some *text*\nwrapped here.\n\n| a | b |\n|---|---|\n"
    _write(files / "t.md", src)
    assert run(files / "t.md") == 0
    assert (files / "t.bpp").read_text(encoding="utf-8") == "bpp4 md\n" + src
    assert run(files / "t.bpp", "-o", files / "t2.md") == 0
    assert (files / "t2.md").read_text(encoding="utf-8") == src
    assert run("decode", files / "t.bpp") == 0  # JSON: the tree of the source
    assert json.loads(capsys.readouterr().out) == {
        "note": "Some *text* wrapped here.\n\n| a | b |\n|---|---|", "steps": []}


def test_python_api(files):
    import bpp

    d = bpp.load(files / "y.yaml")
    assert d == {"a": 1, "b": ["x", "y"], "d": "2026-01-01"}
    assert bpp.loads(bpp.dumps(d)) == d
    bpp.dump(d, files / "y.bpp")
    bpp.dump(d, files / "y2.json")
    assert bpp.load(files / "y.bpp") == bpp.load(files / "y2.json") == d
