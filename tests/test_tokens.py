"""Token counters and the deterministic estimator."""

import base64

from bpp import tokens
from bpp.estimate import est_tokens


def test_available_counters_count_something():
    counters = tokens.available_counters()
    assert counters
    for fn in counters.values():
        assert fn("hello world") >= 2
        assert fn("") == 0


def test_fallback_when_nothing_available(monkeypatch):
    def boom():
        raise RuntimeError

    monkeypatch.setattr(tokens, "_o200k", boom)
    monkeypatch.setattr(tokens, "_claude2", boom)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert list(tokens.available_counters()) == ["estimate"]


def test_expand_js_tiktoken_ranks():
    b64 = [base64.b64encode(x).decode() for x in (b"a", b"b", b"ab")]
    text = 'export default {"bpe_ranks": "! 0 %s %s\\n! 5 %s"};' % tuple(b64)
    d = tokens._parse_js_ranks(text)
    assert tokens._expand_ranks(d["bpe_ranks"]) == {b"a": 0, b"b": 1, b"ab": 5}


def test_estimator_orders_like_real_tokenizers():
    counters = tokens.available_counters()
    a = '{"id": 1, "name": "Ayşe"}\n' * 20
    b = "1 Ayşe\n" * 20
    assert est_tokens(a) > est_tokens(b)
    for fn in counters.values():
        assert fn(a) > fn(b)
