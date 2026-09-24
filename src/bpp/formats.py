"""Readers and writers for the formats bpp converts from and to."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path

from .lexer import NUM_RE

FORMATS = ("json", "yaml", "csv", "md", "bpp")
_EXT = {".json": "json", ".yaml": "yaml", ".yml": "yaml", ".csv": "csv",
        ".md": "md", ".markdown": "md", ".bpp": "bpp"}


def detect(path: str | Path) -> str:
    fmt = _EXT.get(Path(path).suffix.lower())
    if not fmt:
        raise ValueError(f"cannot infer format from {path!s}; pass --from/--to")
    return fmt


# ----------------------------------------------------------------------- YAML

def _yaml_loader():
    import yaml

    class Loader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            # Stringify keys before they meet in a dict: YAML `1:` and `true:`
            # are different keys but equal (and same-hash) in Python.
            if not isinstance(node, yaml.MappingNode):
                raise yaml.constructor.ConstructorError(
                    None, None, "expected a mapping", node.start_mark)
            self.flatten_mapping(node)
            out = {}
            for key_node, value_node in node.value:
                key = _key_str(self.construct_object(key_node, deep=deep))
                out[key] = self.construct_object(value_node, deep=deep)
            return out

    # Keep dates/times as the strings they were written as: JSON has no date
    # type, and turning them into datetime objects would not round-trip.
    Loader.yaml_implicit_resolvers = {
        ch: [(tag, rx) for tag, rx in rs if tag != "tag:yaml.org,2002:timestamp"]
        for ch, rs in Loader.yaml_implicit_resolvers.items()
    }
    return Loader


def _key_str(k) -> str:
    """YAML allows non-string keys; the JSON data model does not."""
    if isinstance(k, str):
        return k
    if isinstance(k, (bool, int, float)) or k is None:
        return json.dumps(k)
    if isinstance(k, (list, tuple, dict)):
        raise ValueError("YAML keys must be scalars")
    return str(k)


def _json_keys(v):
    if isinstance(v, dict):
        return {_key_str(k): _json_keys(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json_keys(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    raise ValueError(f"unsupported YAML value of type {type(v).__name__}")


def load_yaml(text: str):
    import yaml

    return _json_keys(yaml.load(text, Loader=_yaml_loader()))


def dump_yaml(data) -> str:
    import yaml

    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=10**9)


# ------------------------------------------------------------------------ CSV

def _infer(cell: str):
    """CSV cell -> typed value, only when writing it back yields the same text."""
    if cell == "":
        return None
    if cell in ("true", "false"):
        return cell == "true"
    if NUM_RE.fullmatch(cell):
        if re.fullmatch(r"-?(?:0|[1-9]\d*)", cell):
            return int(cell) if cell != "-0" else cell
        f = float(cell)
        if math.isfinite(f) and repr(f) == cell:
            return f
    return cell


def _cell_text(v) -> str:
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (int, str)):
        return str(v)
    raise ValueError("CSV cells must be scalars")


def _no_nul(text: str):
    # Python < 3.11's csv module cannot read or write NUL; reject it everywhere
    # so behaviour does not depend on the Python version.
    if "\x00" in text:
        raise ValueError("CSV cells cannot contain NUL (\\x00) characters")


def load_csv(text: str) -> list[dict]:
    _no_nul(text)
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return []
    header = rows[0]
    if len(set(header)) != len(header):
        raise ValueError("CSV header has duplicate column names")
    out = []
    for i, r in enumerate(rows[1:], 2):
        if len(r) != len(header):
            raise ValueError(f"CSV row {i} has {len(r)} cells, header has {len(header)}")
        out.append({k: _infer(c) for k, c in zip(header, r)})
    return out


def dump_csv(data) -> str:
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ValueError("CSV output needs a list of flat objects")
    cols: list[str] = []
    for r in data:
        for k in r:
            if k not in cols:
                cols.append(k)
    _no_nul("".join(cols))
    for r in data:
        for v in r.values():
            if isinstance(v, str):
                _no_nul(v)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in data:
        w.writerow([_cell_text(r.get(c)) for c in cols])
    return buf.getvalue()


# ----------------------------------------------------------------------- JSON

def load_json(text: str):
    return json.loads(text)


def dump_json(data, indent: int | None = 2) -> str:
    if indent is None:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=indent) + "\n"


# --------------------------------------------------------------------- facade

def loads(text: str, fmt: str):
    if fmt == "json":
        return load_json(text)
    if fmt == "yaml":
        return load_yaml(text)
    if fmt == "csv":
        return load_csv(text)
    if fmt == "md":
        from .markdown import md_to_tree
        return md_to_tree(text)
    if fmt == "bpp":
        from .decoder import decode
        return decode(text)
    raise ValueError(f"unknown format {fmt!r}")


def dumps(data, fmt: str, **kw) -> str:
    if fmt == "json":
        return dump_json(data, kw.get("indent", 2))
    if fmt == "yaml":
        return dump_yaml(data)
    if fmt == "csv":
        return dump_csv(data)
    if fmt == "md":
        from .markdown import tree_to_md
        return tree_to_md(data)
    if fmt == "bpp":
        from .encoder import encode
        return encode(data, **{k: v for k, v in kw.items() if k in ("primer", "refs", "keep_order")})
    raise ValueError(f"unknown format {fmt!r}")
