"""The benchmark scripts' own logic (no API calls)."""

import run_qa
from make_examples import EXAMPLES, load


def test_every_example_has_ten_questions_with_answers():
    for name in EXAMPLES:
        data, _ = load(name)
        qs = run_qa.QUESTIONS[name](data)
        assert len(qs) == 10
        assert all(e is not None for _, e, _ in qs)


def test_grading():
    g = run_qa.grade
    assert g("8080", 8080, "num") and g("8,080.", 8080, "num") and not g("808", 8080, "num")
    assert g("No", False, "bool") and g("yes", True, "bool") and not g("yes", False, "bool")
    assert g("DE, TR,NL", ["TR", "DE", "NL"], "list") and not g("TR, DE", ["TR", "DE", "NL"], "list")
    assert g("`Şule Chen`.", "Şule Chen", "str") and g("İNCELEME", "i̇nceleme", "str")
    assert g("RPO is 1 saat", "1 saat", "contains")
    assert not g(None, 1, "num")


def test_parse_answers():
    text = "1: a\n**2**: b\n3) c\nnoise\n10. last\n11: ignored"
    assert run_qa.parse_answers(text, 10) == ["a", "b", "c"] + [None] * 6 + ["last"]
