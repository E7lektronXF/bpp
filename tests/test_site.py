"""docs/index.html must be the current build of site/ + js/bpp.js + examples/."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))

from build import build  # noqa: E402


def test_playground_is_up_to_date():
    full, _ = build()
    assert (ROOT / "docs/index.html").read_text(encoding="utf-8") == full, \
        "run: python site/build.py"
