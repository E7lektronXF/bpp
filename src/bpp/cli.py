"""Command line interface: bpp encode | decode | stats."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .formats import FORMATS, detect, dumps, loads


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _write(path: str | None, text: str):
    if not path or path == "-":
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8", newline="\n")


def _load(path: str, fmt: str | None):
    fmt = fmt or (detect(path) if path != "-" else None)
    if not fmt:
        raise ValueError("reading stdin needs --from")
    return loads(_read(path), fmt), fmt


def cmd_encode(a) -> int:
    data, fmt = _load(a.input, a.from_)
    primer = {"none": False, "short": True, "long": "long"}[a.primer]
    # CSV column order is part of the data, so never move a column there.
    _write(a.output, dumps(data, "bpp", primer=primer, refs=not a.no_refs,
                           keep_order=a.keep_order or fmt == "csv"))
    return 0


def cmd_decode(a) -> int:
    data, _ = _load(a.input, a.from_ or "bpp")
    to = a.to or (detect(a.output) if a.output and a.output != "-" else "json")
    kw = {"indent": None if a.indent < 0 else a.indent} if to == "json" else {}
    _write(a.output, dumps(data, to, **kw))
    return 0


# ---------------------------------------------------------------------- stats

def _toon_bridge() -> list[str] | None:
    """Command that runs the reference TOON encoder, if available."""
    node = shutil.which("node")
    if not node:
        return None
    candidates = [os.environ.get("BPP_TOON_BRIDGE"),
                  Path.cwd() / "bench/toon/toon.mjs",
                  Path(__file__).resolve().parents[2] / "bench/toon/toon.mjs"]
    for c in candidates:
        if c and Path(c).exists() and (Path(c).parent / "node_modules").exists():
            return [node, str(c), "encode"]
    return None


def renderings(data, keep_order: bool = False, markdown: bool = False) -> dict[str, str]:
    """The same data in every format we compare."""
    import json

    out = {
        "JSON (indent 2)": dumps(data, "json"),
        "JSON (minified)": dumps(data, "json", indent=None),
        "YAML": dumps(data, "yaml"),
    }
    try:
        out["CSV"] = dumps(data, "csv")
    except ValueError:
        pass
    if markdown:
        out["Markdown"] = dumps(data, "md")
    bridge = _toon_bridge()
    if bridge:
        p = subprocess.run(bridge, input=json.dumps(data, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode == 0:
            out["TOON"] = p.stdout
    out["bpp"] = dumps(data, "bpp", keep_order=keep_order)
    out["bpp + primer"] = dumps(data, "bpp", primer=True, keep_order=keep_order)
    return out


def cmd_stats(a) -> int:
    from .tokens import available_counters

    data, fmt = _load(a.input, a.from_)
    counters = available_counters()
    rows = [(name, text, {c: fn(text) for c, fn in counters.items()})
            for name, text in renderings(data, keep_order=fmt == "csv",
                                             markdown=fmt == "md").items()]
    base = rows[0][2]
    names = list(counters)
    head = ["format", "chars"] + names + [f"vs JSON ({n})" for n in names]
    table = [head]
    for name, text, cnt in rows:
        table.append([name, str(len(text))] + [str(cnt[n]) for n in names]
                     + [f"{100 * (cnt[n] - base[n]) / base[n]:+.1f}%" for n in names])
    if a.markdown:
        print("| " + " | ".join(head) + " |")
        print("|" + "---|" * len(head))
        for r in table[1:]:
            print("| " + " | ".join(r) + " |")
    else:
        w = [max(len(r[i]) for r in table) for i in range(len(head))]
        for r in table:
            print("  ".join(c.ljust(w[i]) if i == 0 else c.rjust(w[i]) for i, c in enumerate(r)))
    if "anthropic" not in counters:
        print("\nnote: o200k/claude2 are proxies; set ANTHROPIC_API_KEY for real Claude counts.",
              file=sys.stderr)
    return 0


# ------------------------------------------------------------ one-step mode

def _savings(src: str, out: str) -> str:
    try:
        from .tokens import available_counters

        name, fn = next(iter(available_counters().items()))
    except Exception:
        return ""
    if name == "chars/4":
        return ""
    a, b = fn(src), fn(out)
    return f" ({name}: {a} -> {b} tokens, {100 * (b - a) / a:+.0f}%)" if a else ""


def cmd_auto(a) -> int:
    """`bpp FILE`: .bpp files are decoded, everything else is encoded."""
    src = Path(a.input)
    if src.suffix.lower() == ".bpp":
        to = a.to or (detect(a.output) if a.output and a.output != "-" else "json")
        out = a.output or str(src.with_suffix("." + {"yaml": "yaml", "md": "md",
                                                        "csv": "csv"}.get(to, "json")))
        if out != "-" and Path(out).exists() and not a.force:
            raise ValueError(f"{out} exists; use -o to pick another name or --force to overwrite")
        text = dumps(loads(_read(a.input), "bpp"), to)
        _write(out, text)
    else:
        fmt = detect(src)
        raw = _read(a.input)
        out = a.output or str(src.with_suffix(".bpp"))
        text = dumps(loads(raw, fmt), "bpp", primer=a.primer, keep_order=fmt == "csv")
        _write(out, text)
        if out != "-":
            print(f"{src} -> {out}{_savings(raw, text)}", file=sys.stderr)
    return 0


def _auto_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="bpp", description="bpp FILE: encode json/yaml/csv/md to FILE.bpp, or decode "
        "FILE.bpp to json. Subcommands: encode, decode, stats (bpp <cmd> -h).")
    p.add_argument("input")
    p.add_argument("-o", "--output", help="output file, '-' for stdout (default: next to input)")
    p.add_argument("--to", choices=["json", "yaml", "csv", "md"], help="decode target format")
    p.add_argument("--primer", action="store_true", help="add a one-line format explanation")
    p.add_argument("-f", "--force", action="store_true", help="overwrite when decoding")
    a = p.parse_args(argv)
    try:
        return cmd_auto(a)
    except (ValueError, OSError) as ex:
        print(f"bpp: error: {ex}", file=sys.stderr)
        return 1


def _utf8_console():
    # Windows consoles default to a legacy code page; Turkish text would crash print().
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] not in ("encode", "decode", "stats", "-h", "--help", "--version"):
        return _auto_main(argv)
    p = argparse.ArgumentParser(prog="bpp", description="Token-efficient data format for LLMs. "
                                "Shortcut: bpp FILE (encode, or decode if FILE is .bpp).")
    p.add_argument("--version", action="version", version=f"bpp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("encode", help="convert json/yaml/csv/md to .bpp")
    e.add_argument("input", help="input file ('-' for stdin with --from)")
    e.add_argument("-o", "--output", help="output .bpp file (default stdout)")
    e.add_argument("--from", dest="from_", choices=[f for f in FORMATS if f != "bpp"])
    e.add_argument("--primer", choices=["none", "short", "long"], default="none",
                   help="prepend a format explanation for LLMs that have not seen bpp")
    e.add_argument("--no-refs", action="store_true", help="disable the &n/*n dictionary")
    e.add_argument("--keep-order", action="store_true",
                   help="never reorder keys (slightly larger output)")
    e.set_defaults(fn=cmd_encode)

    d = sub.add_parser("decode", help="convert .bpp to json/yaml/csv/md")
    d.add_argument("input", help="input .bpp file ('-' for stdin)")
    d.add_argument("-o", "--output", help="output file (default stdout)")
    d.add_argument("--to", choices=["json", "yaml", "csv", "md"],
                   help="output format (default: from -o extension, else json)")
    d.add_argument("--indent", type=int, default=2, help="JSON indent; -1 = minified")
    d.set_defaults(fn=cmd_decode, from_=None)

    s = sub.add_parser("stats", help="compare token counts across formats")
    s.add_argument("input")
    s.add_argument("--from", dest="from_", choices=list(FORMATS))
    s.add_argument("--markdown", action="store_true", help="print a Markdown table")
    s.set_defaults(fn=cmd_stats)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (ValueError, OSError) as ex:
        print(f"bpp: error: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
