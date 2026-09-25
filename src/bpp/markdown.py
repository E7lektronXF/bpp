r"""Markdown plans <-> tree (SPEC §7).

Headings and nested lists become a tree of steps:

    {"title": "...", "note": "...", "steps": [
        {"title": "...", "status": "done", "note": "...", "steps": [...]}]}

* A single level-1 heading becomes the document title.
* `- [ ]`, `- [x]`, `- [/]`, `- [-]` set status todo / done / doing / cancelled
  (also allowed right after the `#`s of a heading).
* Paragraphs, code blocks and other text go to the `note` of the heading or
  list item they belong to.
* Soft line breaks are not kept: the wrapped lines of a list item's first
  paragraph are joined into its title, and the wrapped lines of plain
  paragraphs in a note are joined with a space.  Hard breaks (two trailing
  spaces or `\`), code, tables, block quotes, HTML and math are left alone.

The conversion keeps structure, not formatting: `tree_to_md` writes a
normalized Markdown document (top-level steps as `##`, deeper steps as `-`
lists) which parses back to the same tree.
"""

from __future__ import annotations

import re

_HEADING = re.compile(r"(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM = re.compile(r"( *)([-*+]|\d{1,9}[.)])(?: +(.*))?$")
_BOX = re.compile(r"\[([ xX/-])\] +")
_FENCE = re.compile(r"(```|~~~)")
# Lines that start (or may start) a block of their own; they are never joined.
_BLOCKISH = re.compile(r"(```|~~~|>|<|\$\$|\[[^\]]*\]:|[-*+](?: |$)|\d{1,9}[.)](?: |$)|#)")
_RULE = re.compile(r"[-=*_ ]+")  # thematic break or setext underline
# HTML blocks that run to an end marker (CommonMark types 1-5); other HTML runs to a blank line.
_HTML_RAW = [(re.compile(r"<(?:pre|script|style|textarea)(?:[ >]|$)", re.I),
              re.compile(r"</(?:pre|script|style|textarea)>", re.I)),
             (re.compile(r"<!--"), re.compile(r"-->")),
             (re.compile(r"<\?"), re.compile(r"\?>")),
             (re.compile(r"<!\[CDATA\["), re.compile(r"\]\]>")),
             (re.compile(r"<![A-Za-z]"), re.compile(r">"))]
STATUS = {" ": "todo", "x": "done", "X": "done", "/": "doing", "-": "cancelled"}
BOX = {"todo": " ", "done": "x", "doing": "/", "cancelled": "-"}


def _node(text: str) -> dict:
    m = _BOX.match(text)
    node: dict = {"title": (text[m.end():] if m else text).strip()}
    if m:
        node["status"] = STATUS[m.group(1)]
    return node


def _add_note(node: dict, line: str):
    node.setdefault("_note", []).append(line)


def _hard_break(line: str) -> bool:
    return line.endswith("  ") or line.endswith("\\")


def _plain(line: str) -> bool:
    """A line that can only be paragraph text (so joining it keeps the structure)."""
    s = line.strip()
    return bool(s) and "|" not in s and not _BLOCKISH.match(s) and not _RULE.fullmatch(s)


def _join_soft(lines: list[str]) -> list[str]:
    """Join the soft-wrapped lines of plain paragraphs in a note with a space."""
    out: list[str] = []
    fence = None      # open ``` / ~~~ / $$ / front-matter marker
    html = None       # "blank": HTML block until a blank line; else the regex that ends it
    joinable = False  # out[-1] is paragraph text that the next line may continue
    for i, ln in enumerate(lines):
        s = ln.lstrip(" ")
        out.append(ln)
        if fence:
            if s.startswith(fence) or (fence == "---" and s.rstrip() == "..."):
                fence = None
        elif html:
            if (html == "blank" and not s) or (html != "blank" and html.search(ln)):
                html = None
        elif i == 0 and s.rstrip() == "---":
            fence = "---"  # YAML front matter
        elif re.match(r"```|~~~|\$\$", s):
            fence = s[:3] if s[0] != "$" else "$$"
            if fence == "$$" and len(s.rstrip()) > 2 and s.rstrip().endswith("$$"):
                fence = None  # $$ ... $$ on one line
        elif s.startswith("<"):
            html = "blank"
            for start, end in _HTML_RAW:
                m = start.match(s)
                if m:
                    html = None if end.search(s, m.end()) else end
                    break
        elif joinable and ln == s and _plain(ln):
            out.pop()
            out[-1] = out[-1].rstrip() + " " + ln
        joinable = not fence and not html and ln == s and _plain(ln) and not _hard_break(ln)
    return out


def md_to_tree(text: str, *, join: bool = True) -> dict:
    """Parse a Markdown document into a plan tree.

    join=False keeps every soft line break (no title or note joining, as in bpp3).
    """
    root: dict = {"steps": []}
    headings: list[tuple[int, dict]] = [(0, root)]
    items: list[tuple[int, int, dict]] = []  # (indent, content column, node)
    fence = None  # (marker, target node, strip column)
    h1_nodes: list[dict] = []
    para = None  # list item whose first paragraph (its title) is still open

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.expandtabs(4)
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)

        if fence:
            marker, node, col = fence
            _add_note(node, line[min(col, indent):] if stripped else "")
            if stripped.startswith(marker):
                fence = None
            continue

        if not stripped:
            para = None
            target = items[-1][2] if items else headings[-1][1]
            if target.get("_note") and target["_note"][-1] != "":
                _add_note(target, "")
            continue

        m = _HEADING.match(stripped) if indent < 4 else None
        if m:
            level = len(m.group(1))
            node = _node(m.group(2))
            if level == 1:
                h1_nodes.append(node)
            while headings[-1][0] >= level:
                headings.pop()
            headings[-1][1].setdefault("steps", []).append(node)
            headings.append((level, node))
            items = []
            para = None
            continue

        m = _ITEM.match(line)
        if m:
            while items and items[-1][0] >= indent:
                items.pop()
            node = _node(m.group(3) or "")
            parent = items[-1][2] if items else headings[-1][1]
            parent.setdefault("steps", []).append(node)
            items.append((indent, indent + len(m.group(2)) + 1, node))
            para = node if join and node["title"] and not _hard_break(line) else None
            continue

        if para is not None and stripped.strip() and not _BLOCKISH.match(stripped) \
                and "|" not in stripped and not _RULE.fullmatch(stripped.rstrip()):
            # a wrapped (possibly lazy) line of the item's first paragraph
            para["title"] += " " + stripped.strip()
            if _hard_break(line):
                para = None
            continue
        para = None

        # text: goes to the innermost list item it is indented under
        while items and indent < items[-1][1] and indent <= items[-1][0]:
            items.pop()
        if items:
            node, col = items[-1][2], items[-1][1]
        else:
            node, col = headings[-1][1], 0
        f = _FENCE.match(stripped)
        if f:
            fence = (f.group(1), node, col)
        _add_note(node, line[min(col, indent):])

    def finish(node: dict):
        note = node.pop("_note", None)
        while note and note[-1] == "":
            note.pop()
        if note:
            node["note"] = "\n".join(_join_soft(note) if join else note)
        for child in node.get("steps", []):
            finish(child)
        return node

    finish(root)
    doc: dict = {}
    top = root.get("steps", [])
    if len(h1_nodes) == 1 and "status" not in h1_nodes[0]:
        # The only '# ' heading is the document title.  Anything that came
        # before it (text, list items, lower headings) stays in front.
        t = h1_nodes[0]
        doc["title"] = t["title"]
        notes = [n for n in (root.get("note"), t.get("note")) if n]
        if notes:
            doc["note"] = "\n\n".join(notes)
        doc["steps"] = [n for n in top if n is not t] + t.get("steps", [])
        return doc
    if root.get("note"):
        doc["note"] = root["note"]
    doc["steps"] = top
    return doc


def tree_to_md(doc: dict) -> str:
    if not isinstance(doc, dict) or not isinstance(doc.get("steps", []), list):
        raise ValueError("Markdown output needs a plan tree: {title?, note?, steps: [...]}")
    out: list[str] = []
    if doc.get("title") is not None:
        out += [f"# {doc['title']}", ""]
    if doc.get("note"):
        out += [doc["note"], ""]
    for node in doc.get("steps", []):
        box = f"[{BOX[node['status']]}] " if node.get("status") in BOX else ""
        out.append(f"## {box}{node.get('title', '')}")
        out.append("")
        if node.get("note"):
            out += [node["note"], ""]
        _items(node.get("steps", []), 0, out)
        if node.get("steps"):
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def _items(nodes, depth, out):
    pad = "  " * depth
    for node in nodes:
        box = f"[{BOX[node['status']]}] " if node.get("status") in BOX else ""
        out.append(f"{pad}- {box}{node.get('title', '')}".rstrip())
        if node.get("note"):
            out.append("")  # so the note does not continue the title paragraph
            for ln in str(node["note"]).split("\n"):
                out.append(f"{pad}  {ln}" if ln else "")
        _items(node.get("steps", []), depth + 1, out)
