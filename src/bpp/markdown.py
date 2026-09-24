"""Markdown plans <-> tree (SPEC §7).

Headings and nested lists become a tree of steps:

    {"title": "...", "note": "...", "steps": [
        {"title": "...", "status": "done", "note": "...", "steps": [...]}]}

* A single level-1 heading becomes the document title.
* `- [ ]`, `- [x]`, `- [/]`, `- [-]` set status todo / done / doing / cancelled
  (also allowed right after the `#`s of a heading).
* Paragraphs, code blocks and other text go to the `note` of the heading or
  list item they belong to.

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


def md_to_tree(text: str) -> dict:
    root: dict = {"steps": []}
    headings: list[tuple[int, dict]] = [(0, root)]
    items: list[tuple[int, int, dict]] = []  # (indent, content column, node)
    fence = None  # (marker, target node, strip column)
    h1_nodes: list[dict] = []

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
            continue

        m = _ITEM.match(line)
        if m:
            while items and items[-1][0] >= indent:
                items.pop()
            node = _node(m.group(3) or "")
            parent = items[-1][2] if items else headings[-1][1]
            parent.setdefault("steps", []).append(node)
            items.append((indent, indent + len(m.group(2)) + 1, node))
            continue

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
            node["note"] = "\n".join(note)
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
            for ln in str(node["note"]).split("\n"):
                out.append(f"{pad}  {ln}" if ln else "")
        _items(node.get("steps", []), depth + 1, out)
