"""bpp - a token-efficient text format for feeding structured data to LLMs.

    import bpp
    text = bpp.dumps({"users": [{"id": 1, "name": "Ayşe"}]})   # -> .bpp text
    data = bpp.loads(text)                                      # -> Python objects
    data = bpp.load("config.yaml")          # any supported file (.json .yaml .csv .md .bpp)
    bpp.dump(data, "config.bpp")            # format from the extension
"""

from pathlib import Path

from .decoder import decode
from .encoder import encode
from .lexer import BppError

__version__ = "0.1.0"
__all__ = ["encode", "decode", "dumps", "loads", "load", "dump", "BppError", "__version__"]

dumps = encode
loads = decode


def load(path):
    """Read a .json/.yaml/.csv/.md/.bpp file into Python objects."""
    from .formats import detect, loads as _loads

    return _loads(Path(path).read_text(encoding="utf-8"), detect(path))


def dump(data, path, **options):
    """Write data to a file; the extension picks the format (.bpp by default)."""
    from .formats import detect, dumps as _dumps

    fmt = detect(path) if Path(path).suffix else "bpp"
    Path(path).write_text(_dumps(data, fmt, **options), encoding="utf-8", newline="\n")
