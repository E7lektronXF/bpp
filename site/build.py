"""Build the playground page.

    python site/build.py [--artifact PATH]

Writes docs/index.html (a complete page for GitHub Pages) from
site/playground.html, inlining js/bpp.js and the example files. With
--artifact it also writes the page body without the <html>/<head> wrapper.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = [
    ("Orders (JSON)", "quickstart.json", "json"),
    ("Employee table (CSV)", "employees.csv", "csv"),
    ("Service config (YAML)", "config.yaml", "yaml"),
    ("Project plan (JSON)", "plan.json", "json"),
    ("Project plan (Markdown)", "project_plan.md", "md"),
    ("API response (JSON)", "orders.json", "json"),
    ("Repetitive logs (JSON)", "logs.json", "json"),
]


def section(text: str, name: str) -> str:
    m = re.search(rf"<!--{name}-->\n(.*?)<!--/{name}-->", text, re.S)
    assert m, name
    return m.group(1)


def build() -> tuple[str, str]:
    tpl = (ROOT / "site/playground.html").read_text(encoding="utf-8")
    examples = [{"label": label, "fmt": fmt, "text": (ROOT / "examples" / f).read_text(encoding="utf-8")}
                for label, f, fmt in EXAMPLES]
    ex_json = json.dumps(examples, ensure_ascii=False).replace("</", "<\\/")
    js = (ROOT / "js/bpp.js").read_text(encoding="utf-8")
    assert "</script" not in js
    body = section(tpl, "BODY").replace("/*EXAMPLES*/", ex_json).replace("/*BPP_JS*/", js)
    head = section(tpl, "HEAD")
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="description" content="Convert JSON, YAML, CSV or Markdown to bpp and compare token counts.">\n'
            f'{head}</head>\n<body>\n{body}</body>\n</html>\n')
    return full, head + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", help="also write the wrapper-less page body here")
    a = ap.parse_args()
    full, fragment = build()
    out = ROOT / "docs/index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(full, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(full.encode()) // 1024} KB)")
    if a.artifact:
        Path(a.artifact).write_text(fragment, encoding="utf-8")
        print(f"wrote {a.artifact}")


if __name__ == "__main__":
    main()
