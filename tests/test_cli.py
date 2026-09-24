"""End-to-end CLI tests."""

import json
import subprocess
import sys

import pytest

import datasets as ds
from bpp.cli import main
from bpp.formats import dump_csv


def run(*args):
    return main([str(a) for a in args])


@pytest.fixture
def files(tmp_path):
    (tmp_path / "c.json").write_text(json.dumps(ds.config(), ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    (tmp_path / "e.csv").write_text(dump_csv(ds.employees()), encoding="utf-8")
    (tmp_path / "p.md").write_text("# Plan\n\n## Adım 1\n- [x] a\n- [ ] b\n", encoding="utf-8")
    (tmp_path / "y.yaml").write_text("a: 1\nb: [x, y]\nd: 2026-01-01\n", encoding="utf-8")
    return tmp_path


def test_json_roundtrip(files):
    assert run("encode", files / "c.json", "-o", files / "c.bpp", "--keep-order") == 0
    assert (files / "c.bpp").read_text(encoding="utf-8").startswith("bpp1\n")
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
    assert capsys.readouterr().out.split("\n")[1].startswith("# bpp1")
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
