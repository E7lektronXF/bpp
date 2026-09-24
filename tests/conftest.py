import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))

import pytest  # noqa: E402

from bpp import decode, encode  # noqa: E402


def canon(v):
    """JSON text with key order, for order-sensitive comparisons."""
    return json.dumps(v, ensure_ascii=False)


def roundtrip(x, **kw):
    text = encode(x, **kw)
    back = decode(text)
    assert back == x, text
    # == treats 1 == 1.0 == True; check exact types through JSON text too
    assert json.dumps(back, sort_keys=True) == json.dumps(x, sort_keys=True), text
    return text


@pytest.fixture
def rt():
    return roundtrip
